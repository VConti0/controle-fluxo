"""Modelos clássicos de 'predição' com backtest walk-forward nos últimos TEST_SIZE concursos.

Cada modelo gera, para o concurso t, uma pontuação para cada número usando SÓ concursos < t.
O jogo é o top-6 da pontuação. Métrica: acertos médios vs. acaso (0,6).
"""
import json

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

from common import N_NUM, RESULTS, TEST_SIZE, draws_matrix, load, summarize_hits

WINDOWS = (5, 10, 25, 50, 100, 300)


def features(m, t):
    """Features para os 60 números usando o histórico m[:t]."""
    hist = m[:t]
    f = [hist[-w:].mean(0) for w in WINDOWS]
    f.append(hist.mean(0))
    seen = hist[::-1].argmax(0).astype(float)  # concursos desde a última aparição
    seen[hist.sum(0) == 0] = t
    f.append(np.log1p(seen))
    f.append(np.arange(1, 61) / 60)
    return np.stack(f, 1)


def build_dataset(m, start, end):
    X = np.concatenate([features(m, t) for t in range(start, end)])
    y = m[start:end].reshape(-1)
    return X, y


def top6(scores, rng):
    # desempate aleatório para não favorecer números baixos
    return np.lexsort((rng.random(N_NUM), -scores))[:6]


def main():
    df = load()
    m = draws_matrix(df)
    n = len(m)
    t0 = n - TEST_SIZE
    rng = np.random.default_rng(42)

    heuristics = {
        "aleatorio": lambda t: rng.random(N_NUM),
        "mais_frequentes_historico": lambda t: m[:t].mean(0),
        "quentes_ultimos_25": lambda t: m[t - 25:t].mean(0),
        "frios_menos_frequentes": lambda t: -m[:t].mean(0),
        "atrasados_maior_jejum": lambda t: features(m, t)[:, -2],
    }
    hits = {k: [] for k in heuristics}

    # Modelos de ML: treinados em concursos [300, t0) e re-treinados a cada 100 concursos de teste.
    ml = {"regressao_logistica": lambda: LogisticRegression(max_iter=2000, C=0.1),
          "gradient_boosting": lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                                                                       max_leaf_nodes=15, random_state=0)}
    for k in ml:
        hits[k] = []
    probs = {k: [] for k in ml}
    fitted = {}

    for t in range(t0, n):
        actual = m[t]
        for k, fn in heuristics.items():
            hits[k].append(int(actual[top6(fn(t), rng)].sum()))
        if (t - t0) % 100 == 0:
            X, y = build_dataset(m, 300, t)
            fitted = {k: mk().fit(X, y) for k, mk in ml.items()}
        Xt = features(m, t)
        for k, mdl in fitted.items():
            p = mdl.predict_proba(Xt)[:, 1]
            probs[k].append(p)
            hits[k].append(int(actual[top6(p, rng)].sum()))

    y_test = m[t0:].reshape(-1)
    base_ll = log_loss(y_test, np.full(len(y_test), 0.1))
    res = {"periodo_teste": f"concursos {int(df.concurso[t0])}–{int(df.concurso.iloc[-1])}",
           "modelos": [summarize_hits(h, k) for k, h in hits.items()],
           "log_loss": {"acaso_p=0.1": round(base_ll, 5),
                        **{k: round(log_loss(y_test, np.concatenate(v)), 5) for k, v in probs.items()}}}
    (RESULTS / "classicos.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
