"""'LLM' da Mega-Sena: um Transformer decoder (estilo GPT) treinado como modelo de linguagem.

Cada concurso vira uma "frase" de 7 tokens: <SEP> b1 b2 b3 b4 b5 b6 (bolas na ORDEM REAL do sorteio).
O modelo lê os últimos CTX_DRAWS concursos e aprende a prever o próximo token. Para gerar um
concurso, amostramos 6 tokens com máscara para não repetir números.

Avaliação honesta:
  * entropia cruzada (nats/bola) nos concursos de teste vs. o acaso sem reposição
    (média de ln60, ln59, ..., ln55 ≈ 4.051);
  * acertos médios do top-6 (marginais estimadas por amostragem) vs. 0,6.
"""
import json
import math
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from common import RESULTS, TEST_SIZE, draw_order, load, summarize_hits

SEP = 0  # tokens 1..60 = números
VOCAB = 61
CTX_DRAWS = 12
BLOCK = CTX_DRAWS * 7 + 7
torch.manual_seed(0)
torch.set_num_threads(4)
DEV = "cpu"


class GPT(nn.Module):
    def __init__(self, d=96, layers=3, heads=4, drop=0.2):
        super().__init__()
        self.tok = nn.Embedding(VOCAB, d)
        self.pos = nn.Embedding(BLOCK, d)
        layer = nn.TransformerEncoderLayer(d, heads, 4 * d, drop, batch_first=True, norm_first=True)
        self.blocks = nn.TransformerEncoder(layer, layers)
        self.ln = nn.LayerNorm(d)
        self.head = nn.Linear(d, VOCAB)

    def forward(self, x):
        T = x.shape[1]
        h = self.tok(x) + self.pos(torch.arange(T, device=x.device))
        mask = nn.Transformer.generate_square_subsequent_mask(T, device=x.device)
        return self.head(self.ln(self.blocks(h, mask=mask, is_causal=True)))


def to_tokens(order):
    seq = np.concatenate([np.full((len(order), 1), SEP), order], 1)  # (n, 7)
    return torch.tensor(seq.reshape(-1), dtype=torch.long)


def windows(tokens, draw_ids):
    """Para cada concurso alvo i: CTX_DRAWS concursos anteriores + o alvo -> sequência de BLOCK tokens."""
    return torch.stack([tokens[(i - CTX_DRAWS) * 7:(i + 1) * 7] for i in draw_ids])


def target_loss(model, xb):
    """Entropia cruzada apenas nas 6 bolas do concurso alvo (com máscara anti-repetição)."""
    logits = model(xb[:, :-1])[:, -6:]  # previsões das posições das 6 bolas do alvo
    tgt = xb[:, -6:]
    # máscara: SEP e números já sorteados no mesmo concurso não são permitidos
    mask = torch.zeros_like(logits, dtype=torch.bool)
    mask[..., SEP] = True
    for k in range(1, 6):
        mask[:, k].scatter_(1, tgt[:, :k], True)
    logits = logits.masked_fill(mask, -1e9)
    return F.cross_entropy(logits.reshape(-1, VOCAB), tgt.reshape(-1))


def train(tokens, train_ids, val_ids, epochs=60, bs=64, lr=3e-4, log=True):
    model = GPT().to(DEV)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.1)
    Xtr, Xva = windows(tokens, train_ids), windows(tokens, val_ids) if len(val_ids) else None
    best, best_state, best_ep, hist = 1e9, None, 0, []
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr))
        tl = []
        for i in range(0, len(Xtr), bs):
            loss = target_loss(model, Xtr[perm[i:i + bs]])
            opt.zero_grad(); loss.backward(); opt.step()
            tl.append(loss.item())
        if Xva is not None:
            model.eval()
            with torch.no_grad():
                vl = target_loss(model, Xva).item()
            hist.append((ep, float(np.mean(tl)), vl))
            if log:
                print(f"época {ep:3d}  treino {np.mean(tl):.4f}  validação {vl:.4f}", file=sys.stderr)
            if vl < best:
                best, best_ep = vl, ep
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_ep, hist


@torch.no_grad()
def sample_marginals(model, ctx, n_samples=512, temp=1.0):
    """Gera n_samples concursos a partir do contexto; retorna frequência de cada número (60,)."""
    model.eval()
    x = ctx.unsqueeze(0).repeat(n_samples, 1)
    x = torch.cat([x, torch.full((n_samples, 1), SEP)], 1)
    used = torch.zeros(n_samples, VOCAB, dtype=torch.bool)
    used[:, SEP] = True
    for _ in range(6):
        logits = model(x)[:, -1] / temp
        logits = logits.masked_fill(used, -1e9)
        nxt = torch.multinomial(F.softmax(logits, -1), 1)
        used.scatter_(1, nxt, True)
        x = torch.cat([x, nxt], 1)
    counts = used[:, 1:].float().mean(0).numpy()
    return counts, x[:, -6:].numpy()


def main():
    df = load()
    order = draw_order(df)
    tokens = to_tokens(order)
    n = len(order)
    t0 = n - TEST_SIZE
    ids = np.arange(CTX_DRAWS, n)
    train_ids = ids[ids < t0 - 300]
    val_ids = ids[(ids >= t0 - 300) & (ids < t0)]
    test_ids = ids[ids >= t0]

    model, best_ep, hist = train(tokens, train_ids, val_ids)
    with torch.no_grad():
        model.eval()
        test_ce = target_loss(model, windows(tokens, test_ids)).item()
        train_ce = target_loss(model, windows(tokens, train_ids)).item()
    uniform_ce = float(np.mean([math.log(60 - k) for k in range(6)]))

    rng = np.random.default_rng(0)
    hits = []
    for i in test_ids:
        ctx = tokens[(i - CTX_DRAWS) * 7:i * 7]
        marg, _ = sample_marginals(model, ctx, 256)
        pick = np.lexsort((rng.random(60), -marg))[:6]
        hits.append(int(np.isin(pick + 1, order[i]).sum()))

    res = {"arquitetura": "GPT decoder 3 camadas, d=96, 4 cabeças, contexto 12 concursos (91 tokens)",
           "parametros": sum(p.numel() for p in model.parameters()),
           "melhor_epoca_validacao": best_ep,
           "entropia_cruzada_nats_por_bola": {"acaso_sem_reposicao": round(uniform_ce, 4),
                                              "llm_treino": round(train_ce, 4), "llm_teste": round(test_ce, 4)},
           "curva": [{"epoca": e, "treino": round(a, 4), "validacao": round(b, 4)} for e, a, b in hist],
           "backtest": summarize_hits(hits, "llm_transformer")}
    (RESULTS / "llm.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    out = {k: v for k, v in res.items() if k != "curva"}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
