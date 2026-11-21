"""Aprendizado online: prevê cada concurso usando só os anteriores, compara com o real e se ajusta.

Para cada concurso t (do 2º em diante):
  1. PREVÊ: cada modelo escolhe 6 dezenas usando apenas os concursos 1..t-1;
  2. COMPARA: conta os acertos contra o resultado real de t;
  3. AJUSTA: os modelos que aprendem são corrigidos com o erro desse concurso antes de seguir para t+1:
       * regressão logística online: um passo de gradiente nos pesos;
       * LLM online: um passo de gradiente no Transformer (concurso novo + replay de anteriores);
       * ensemble adaptativo: aumenta o peso das estratégias que foram melhor (pesos multiplicativos).
     As regras simples (frequentes, quentes, atrasados) se atualizam sozinhas com o novo histórico.

Percentual de acerto = dezenas acertadas / dezenas apostadas (6 por concurso). Acaso = 10%.

Uso: python3 online.py [--limite N]
"""
import argparse
import json
import math
import sys

import numpy as np
import pandas as pd
import torch

import llm
from classicos import features
from common import RESULTS, draw_order, draws_matrix, load

N_SAMPLES = 128   # sorteios simulados pelo LLM a cada previsão
REPLAY = 15       # concursos anteriores revistos a cada ajuste do LLM
LR_LLM = 1e-4
LR_LOG = 0.05
ETA = 0.05        # taxa de ajuste dos pesos do ensemble
CE_ACASO = float(np.mean([math.log(60 - k) for k in range(6)]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, help="processa só os N primeiros concursos (teste rápido)")
    args = ap.parse_args()

    df = load()
    if args.limite:
        df = df.iloc[:args.limite].reset_index(drop=True)
    m = draws_matrix(df)
    n = len(m)
    rng = np.random.default_rng(7)
    torch.manual_seed(0)

    # LLM: sequência precedida de concursos "vazios" para existir contexto desde o 1º sorteio
    C = llm.CTX_DRAWS
    tokens = torch.cat([torch.zeros(C * 7, dtype=torch.long), llm.to_tokens(draw_order(df))])
    janela = lambda i: tokens[i * 7:(i + C + 1) * 7]   # contexto + concurso i (alvo)
    contexto = lambda i: tokens[i * 7:(i + C) * 7]
    model = llm.GPT()
    opt = torch.optim.AdamW(model.parameters(), lr=LR_LLM, weight_decay=0.1)

    def ajusta_llm(i):
        model.train()
        ant = rng.choice(i, min(i, REPLAY), replace=False) if i else []
        xb = torch.stack([janela(i)] + [janela(int(j)) for j in ant])
        loss = llm.target_loss(model, xb)
        opt.zero_grad(); loss.backward(); opt.step()

    # Regressão logística online (9 features + viés), começa prevendo 10% para todos
    w = np.zeros(10)
    w[-1] = math.log(0.1 / 0.9)

    especialistas = ["mais_frequentes_historico", "quentes_ultimos_25", "atrasados_maior_jejum",
                     "frequentes_ultimos_1000", "logistica_online", "llm_online"]
    pesos = np.ones(len(especialistas)) / len(especialistas)
    rank = lambda s: np.argsort(np.argsort(s)) / 59
    top6 = lambda s: np.lexsort((rng.random(60), -s))[:6]

    ajusta_llm(0)  # o 1º concurso não tem histórico: só entra como aprendizado
    linhas, pesos_hist = [], []
    for t in range(1, n):
        hist, real = m[:t], m[t]

        # 1. PREVÊ (só com concursos < t)
        X = np.c_[features(m, t), np.ones(60)]
        p_log = 1 / (1 + np.exp(-X @ w))
        with torch.no_grad():
            model.eval()
            ce = llm.target_loss(model, janela(t).unsqueeze(0)).item()  # erro do LLM antes do ajuste
        marg, _ = llm.sample_marginals(model, contexto(t), N_SAMPLES)
        scores = {"mais_frequentes_historico": hist.mean(0), "quentes_ultimos_25": hist[-25:].mean(0),
                  "atrasados_maior_jejum": X[:, 7], "frequentes_ultimos_1000": hist[-1000:].mean(0),
                  "logistica_online": p_log, "llm_online": marg}
        ranks = np.stack([rank(scores[k]) for k in especialistas])
        scores["ensemble_adaptativo"] = pesos @ ranks
        scores["aleatorio"] = rng.random(60)

        # 2. COMPARA
        linhas.append({"concurso": int(df.concurso[t]), "ano": int(df.data[t].year),
                       **{k: int(real[top6(s)].sum()) for k, s in scores.items()}, "llm_ce": ce})

        # 3. AJUSTA
        w -= LR_LOG * X.T @ (p_log - real) / 60
        ajusta_llm(t)
        ganho = ranks[:, real.astype(bool)].sum(1) - 3.0   # 3.0 = esperado ao acaso
        pesos = pesos * np.exp(ETA * ganho)
        pesos /= pesos.sum()
        pesos_hist.append(pesos.copy())

        if t % 250 == 0:
            print(f"concurso {int(df.concurso[t])} ({df.data[t].year})", file=sys.stderr, flush=True)

    det = pd.DataFrame(linhas)
    det.to_csv(RESULTS / "online_acertos_por_concurso.csv", index=False)
    modelos = [c for c in det.columns if c not in ("concurso", "ano", "llm_ce")]

    g = det.groupby("ano")
    pct = (g[modelos].mean() / 6 * 100).round(2)
    pct.insert(0, "concursos", g.size())
    pct.loc["TOTAL"] = [len(det)] + list((det[modelos].mean() / 6 * 100).round(2))
    pct["concursos"] = pct["concursos"].astype(int)
    pct.to_csv(RESULTS / "online_acerto_anual_pct.csv")

    acum = det[modelos].cumsum().div(np.arange(1, len(det) + 1), axis=0) / 6 * 100
    acum.insert(0, "ano", det.ano)
    acum = acum.groupby("ano").last().round(2)
    acum.to_csv(RESULTS / "online_acerto_acumulado_pct.csv")

    ph = pd.DataFrame(pesos_hist, columns=especialistas)
    ph.insert(0, "ano", det.ano)
    resumo = {
        "concursos_previstos": len(det), "acaso_pct": 10.0,
        "distribuicao_acertos": {k: {str(h): int((det[k] == h).sum()) for h in range(7)} for k in modelos},
        "llm_erro_antes_do_ajuste_nats_por_bola": {"acaso": round(CE_ACASO, 4),
                                                    "media_geral": round(float(det.llm_ce.mean()), 4),
                                                    "por_ano": {str(a): round(float(v), 4) for a, v in g.llm_ce.mean().items()}},
        "pesos_ensemble_fim_de_cada_ano": {str(a): {k: round(float(v), 3) for k, v in r.items()}
                                            for a, r in ph.groupby("ano").last().iterrows()},
        "logistica_pesos_finais": [round(float(v), 4) for v in w],
    }
    (RESULTS / "online_resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))

    pd.set_option("display.width", 250)
    print("PERCENTUAL DE ACERTO POR ANO (acaso = 10%)")
    print(pct.to_string())
    print("\nPERCENTUAL ACUMULADO ATÉ O FIM DE CADA ANO")
    print(acum.to_string())
    print(json.dumps({k: resumo[k] for k in ("distribuicao_acertos", "llm_erro_antes_do_ajuste_nats_por_bola")}, indent=1))


if __name__ == "__main__":
    main()
