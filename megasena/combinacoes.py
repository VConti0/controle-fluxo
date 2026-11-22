"""Ranqueia todas as 50.063.860 combinações e guarda as 5.006.386 melhores (10%).

Probabilidade de cada número = regressão logística sobre três famílias de sinais:
  * os 5 modelos do comitê (ensemble.py): hipergeométrica, auditoria, Monte Carlo, ARIMA+FFT, XGBoost+LSTM;
  * viés nos dados reais: frequência com decaimento no tempo (meias-vidas de 100, 300 e 1000 concursos);
  * emulador físico: frequência de cada bola nos 5.000 sorteios emulados.
Os pesos são reajustados a cada 10 concursos usando só os 200 concursos anteriores (walk-forward).
Score de uma combinação = soma dos log-odds dos seus 6 números.

Uso:
  python3 combinacoes.py base    # calcula e guarda os scores do comitê para os últimos 500 concursos (demorado)
  python3 combinacoes.py         # teste walk-forward, ranking completo e arquivos de saída
"""
import json
import sys
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from common import RESULTS, draws_matrix, load

TESTE, JANELA = 300, 200
N_TOTAL = 50_063_860
N_TOP = 5_006_386
BASE = RESULTS / "combinacoes_base.npz"
FONTES = ["M1_hipergeometrica", "M2_auditoria", "M3_monte_carlo", "M4_arima_fft", "M5_xgboost_lstm",
          "vies_meia_vida_100", "vies_meia_vida_300", "vies_meia_vida_1000", "emulador"]


def norm(v):
    r = v.max() - v.min()
    return (v - v.min()) / r if r > 0 else np.full(len(v), 0.5)


def vies(hist, meia_vida):
    t = len(hist)
    w = 0.5 ** ((t - 1 - np.arange(t)) / meia_vida)
    return (w[:, None] * hist).sum(0) / w.sum()


def calcula_base():
    from ensemble import camada_base
    m = draws_matrix(load())
    n = len(m)
    S, _ = camada_base(m, n - TESTE - JANELA, 100_000, 10)
    ts = np.array(sorted(S))
    np.savez_compressed(BASE, t=ts, S=np.stack([S[t] for t in ts]))
    print("salvo", BASE, len(ts))


def matriz_fontes(m, emu):
    b = np.load(BASE)
    X = {}
    for t, S in zip(b["t"], b["S"]):
        hist = m[:t]
        X[int(t)] = np.c_[S, norm(vies(hist, 100)), norm(vies(hist, 300)), norm(vies(hist, 1000)), emu]
    return X


def enumera(logit, n_top):
    """Devolve as n_top combinações de maior soma de log-odds, em ordem decrescente."""
    c4 = np.array(list(combinations(range(58), 4)), dtype=np.uint8)
    mx = c4[:, 3]

    def blocos():
        for b in range(1, 56):
            k = 59 - b                                   # números disponíveis depois de b
            sel = c4[mx < k]
            resto = sel.astype(np.int64) + b + 1
            s4 = logit[resto].sum(1).astype(np.float32)
            for a in range(b):
                yield a, b, resto, s4 + np.float32(logit[a] + logit[b])

    lo, hi = np.sort(logit)[:6].sum() - 1e-6, np.sort(logit)[-6:].sum() + 1e-6
    bins = np.linspace(lo, hi, 400_001)
    hist = np.zeros(400_000, dtype=np.int64)
    total = 0
    for _, _, _, s in blocos():
        hist += np.bincount(np.minimum(((s - lo) / (hi - lo) * 400_000).astype(np.int64), 399_999), minlength=400_000)
        total += len(s)
    assert total == N_TOTAL, total
    acima = np.cumsum(hist[::-1])[::-1]
    corte = bins[np.flatnonzero(acima >= n_top)[-1]]
    jogos, scores = [], []
    for a, b, resto, s in blocos():
        ok = s >= corte
        if ok.any():
            r = resto[ok]
            jogos.append(np.c_[np.full(len(r), a), np.full(len(r), b), r].astype(np.uint8))
            scores.append(s[ok])
    jogos, scores = np.concatenate(jogos), np.concatenate(scores)
    o = np.argsort(-scores, kind="stable")[:n_top]
    return jogos[o] + 1, scores[o], total


def main():
    df = load()
    m = draws_matrix(df)
    n = len(m)
    emu_tab = pd.read_csv(RESULTS / "emulador_5000.csv")
    emu_freq = np.bincount(emu_tab[[f"d{i}" for i in range(1, 7)]].values.ravel(), minlength=61)[1:] / len(emu_tab)
    X = matriz_fontes(m, norm(emu_freq))
    rng = np.random.default_rng(3)
    amostra = np.argsort(rng.random((200_000, 60)), axis=1)[:, :6]      # combinações aleatórias p/ o percentil

    def ajusta(t):
        Xt = np.concatenate([X[u] for u in range(t - JANELA, t)])
        return LogisticRegression(C=1.0, max_iter=2000).fit(Xt, m[t - JANELA:t].reshape(-1))

    # ---------- teste walk-forward: o sorteio real cai nos 10% de maior score?
    dentro, percentis, acertos6, modelo = [], [], [], None
    for t in range(n - TESTE, n):
        if (t - (n - TESTE)) % 10 == 0:
            modelo = ajusta(t)
        p = modelo.predict_proba(X[t])[:, 1]
        lg = np.log(p / (1 - p))
        real = lg[m[t].astype(bool)].sum()
        pct = float((lg[amostra].sum(1) < real).mean())
        percentis.append(pct)
        dentro.append(pct >= 0.9)
        acertos6.append(int(m[t][np.argsort(-p)[:6]].sum()))
    k = int(np.sum(dentro))
    from scipy import stats
    teste = {"concursos": TESTE, "periodo": f"{int(df.concurso[n - TESTE])}-{int(df.concurso.iloc[-1])}",
             "reais_dentro_dos_10pct": k, "pct": round(k / TESTE * 100, 1), "referencia_pct": 10.0,
             "p_binomial": round(float(stats.binomtest(k, TESTE, 0.1).pvalue), 4),
             "percentil_medio_do_real": round(float(np.mean(percentis)) * 100, 1), "referencia_percentil": 50.0,
             "acertos_medios_top6": round(float(np.mean(acertos6)), 3), "referencia_acertos": 0.6}

    # ---------- previsão para o próximo concurso e ranking completo
    modelo = ajusta(n)
    p = modelo.predict_proba(X[n])[:, 1]
    p = p * 6 / p.sum()
    lg = np.log(p / (1 - p))
    jogos, scores, total = enumera(lg, N_TOP)
    assert len(jogos) == N_TOP and len({tuple(j) for j in jogos[:100000]}) == 100000
    np.save(RESULTS / "combinacoes_top.npy", jogos)
    pd.DataFrame(jogos[:1000], columns=[f"d{i}" for i in range(1, 7)]).assign(score=scores[:1000].round(4)) \
        .to_csv(RESULTS / "combinacoes_top1000.csv", index_label="posicao")
    prob_top = float(np.exp(scores.astype(np.float64)).sum())
    # massa de probabilidade do modelo dentro das escolhidas, relativa ao total (amostra aleatória p/ o total)
    media_todas = float(np.exp(lg[amostra].sum(1)).mean())
    presenca = np.bincount(jogos.ravel(), minlength=61)[1:] / N_TOP
    out = {"proximo_concurso": int(df.concurso.iloc[-1]) + 1, "combinacoes_possiveis": total,
           "combinacoes_escolhidas": N_TOP,
           "pesos_das_fontes": dict(zip(FONTES, [round(float(c), 3) for c in modelo.coef_[0]])),
           "probabilidade_por_numero_pct": {int(i + 1): round(float(p[i]) * 100, 2) for i in np.argsort(-p)},
           "teste_walk_forward": teste,
           "massa_do_modelo_nas_escolhidas_pct": round(prob_top / (media_todas * total) * 100, 2),
           "primeiro_jogo": [int(x) for x in jogos[0]], "ultimo_jogo_da_lista": [int(x) for x in jogos[-1]],
           "numeros_mais_presentes_na_lista": [(int(i + 1), round(float(presenca[i]) * 100, 1)) for i in np.argsort(-presenca)[:10]],
           "numeros_menos_presentes_na_lista": [(int(i + 1), round(float(presenca[i]) * 100, 1)) for i in np.argsort(presenca)[:10]]}
    (RESULTS / "combinacoes.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print("10 primeiros:", [" ".join(f"{x:02d}" for x in j) for j in jogos[:10]])


if __name__ == "__main__":
    calcula_base() if len(sys.argv) > 1 and sys.argv[1] == "base" else main()
