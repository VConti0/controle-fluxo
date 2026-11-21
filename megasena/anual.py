"""Percentual de acerto por ano, com previsão walk-forward em todo o histórico.

Para cada ano Y (a partir do 2º ano de sorteios):
  * gradient boosting e LLM são treinados só com concursos anteriores a 01/01/Y;
  * para cada concurso de Y, cada modelo escolhe 6 dezenas usando apenas concursos anteriores
    (as regras simples e as features se atualizam a cada sorteio; os modelos treinados ficam
    congelados até o ano seguinte).

Percentual de acerto = dezenas acertadas / dezenas apostadas (6 por concurso). Acaso = 10%.
"""
import json
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.ensemble import HistGradientBoostingClassifier

import llm
from classicos import features
from common import RESULTS, draw_order, draws_matrix, load

MIN_HIST = 25      # primeiros concursos usados só como histórico das features
N_SAMPLES = 128    # sorteios simulados pelo LLM por concurso
CHUNK = 2048


@torch.no_grad()
def llm_marginais(model, tokens, alvo_ids):
    """Frequência de cada número em N_SAMPLES sorteios simulados, para cada concurso em alvo_ids."""
    model.eval()
    ctx = torch.stack([tokens[(i - llm.CTX_DRAWS) * 7:i * 7] for i in alvo_ids])
    x = ctx.repeat_interleave(N_SAMPLES, 0)
    out = []
    for s in range(0, len(x), CHUNK):
        xb = torch.cat([x[s:s + CHUNK], torch.full((len(x[s:s + CHUNK]), 1), llm.SEP)], 1)
        used = torch.zeros(len(xb), llm.VOCAB, dtype=torch.bool)
        used[:, llm.SEP] = True
        for _ in range(6):
            logits = model(xb)[:, -1].masked_fill(used, -1e9)
            nxt = torch.multinomial(F.softmax(logits, -1), 1)
            used.scatter_(1, nxt, True)
            xb = torch.cat([xb, nxt], 1)
        out.append(used[:, 1:].float())
    return torch.cat(out).reshape(len(alvo_ids), N_SAMPLES, 60).mean(1).numpy()


def main():
    df = load()
    m = draws_matrix(df)
    tokens = llm.to_tokens(draw_order(df))
    n = len(m)
    anos = df.data.dt.year.values
    rng = np.random.default_rng(7)
    best_ep = json.loads((RESULTS / "llm.json").read_text())["melhor_epoca_validacao"]

    feats = {t: features(m, t) for t in range(MIN_HIST, n)}
    rank = lambda s: np.argsort(np.argsort(s)) / 59
    top6 = lambda s: np.lexsort((rng.random(60), -s))[:6]

    linhas = []
    for ano in sorted(set(anos))[1:]:
        idx = np.where(anos == ano)[0]
        ini = idx[0]
        X = np.concatenate([feats[t] for t in range(MIN_HIST, ini)])
        y = m[MIN_HIST:ini].reshape(-1)
        gb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                            random_state=0).fit(X, y)
        model, _, _ = llm.train(tokens, np.arange(llm.CTX_DRAWS, ini), [], epochs=best_ep + 1, log=False)
        marg = llm_marginais(model, tokens, idx)

        for j, t in enumerate(idx):
            hist = m[:t]
            p_gb = gb.predict_proba(feats[t])[:, 1]
            scores = {
                "aleatorio": rng.random(60),
                "mais_frequentes_historico": hist.mean(0),
                "quentes_ultimos_25": hist[-25:].mean(0),
                "atrasados_maior_jejum": feats[t][:, -2],
                "frequentes_ultimos_1000": hist[-1000:].mean(0),
                "gradient_boosting": p_gb,
                "llm_transformer": marg[j],
                "consenso_modelos": rank(p_gb) + rank(marg[j]) + rank(hist.mean(0)) + rank(hist[-25:].mean(0)),
            }
            linhas.append({"concurso": int(df.concurso[t]), "ano": int(ano),
                           **{k: int(m[t][top6(s)].sum()) for k, s in scores.items()}})
        print(f"{ano}: {len(idx)} concursos (treino: {ini})", file=sys.stderr, flush=True)

    det = pd.DataFrame(linhas)
    det.to_csv(RESULTS / "acertos_por_concurso.csv", index=False)
    modelos = [c for c in det.columns if c not in ("concurso", "ano")]

    g = det.groupby("ano")
    pct = (g[modelos].mean() / 6 * 100).round(2)
    pct.insert(0, "concursos", g.size())
    total = (det[modelos].mean() / 6 * 100).round(2)
    total["concursos"] = len(det)
    pct.loc["TOTAL"] = total
    pct["concursos"] = pct["concursos"].astype(int)
    pct.to_csv(RESULTS / "acerto_anual_pct.csv")

    # percentual acumulado conforme as previsões avançam
    acum = (det[modelos].cumsum().div(np.arange(1, len(det) + 1), axis=0) / 6 * 100)
    acum.insert(0, "ano", det.ano)
    acum.groupby("ano").last().round(2).to_csv(RESULTS / "acerto_acumulado_pct.csv")

    faixas = {k: {str(h): int((det[k] == h).sum()) for h in range(7)} for k in modelos}
    (RESULTS / "acerto_anual_faixas.json").write_text(json.dumps(
        {"concursos_previstos": len(det), "acaso_pct": 10.0, "distribuicao_acertos": faixas}, indent=2))

    pd.set_option("display.width", 250)
    print(pct.to_string())
    print(json.dumps(faixas, indent=1))


if __name__ == "__main__":
    main()
