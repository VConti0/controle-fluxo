"""Gera os palpites para o concurso seguinte ao histórico informado, com todos os modelos.

Uso:
    python3 prever.py              # treina em todo o histórico, palpites para o próximo concurso
    python3 prever.py --ate 3082   # treina só com os concursos 1..3082 (para comparar com o que veio depois)
"""
import argparse
import json

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import llm
from classicos import build_dataset, features
from common import RESULTS, draw_order, draws_matrix, load


def fmt(idx0):
    return sorted(int(i) + 1 for i in idx0)


def gerar_palpites(df):
    """Treina todos os modelos usando apenas os concursos em df e devolve os palpites do concurso seguinte."""
    m = draws_matrix(df)
    order = draw_order(df)
    n = len(m)
    rng = np.random.default_rng(int(df.concurso.iloc[-1]))

    palpites = {
        "surpresinha_aleatoria": fmt(rng.choice(60, 6, replace=False)),
        "mais_frequentes_historico": fmt(np.argsort(-m.mean(0), kind="stable")[:6]),
        "quentes_ultimos_25": fmt(np.lexsort((rng.random(60), -m[-25:].mean(0)))[:6]),
        "atrasados_maior_jejum": fmt(np.argsort(-features(m, n)[:, -2], kind="stable")[:6]),
        # exploratório: única janela com z>2 no walk-forward, mas não sobrevive à correção por múltiplos testes
        "exploratorio_frequentes_ultimos_1000": fmt(np.argsort(-m[-1000:].mean(0), kind="stable")[:6]),
    }

    X, y = build_dataset(m, 300, n)
    gb = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, random_state=0).fit(X, y)
    p_gb = gb.predict_proba(features(m, n))[:, 1]
    palpites["gradient_boosting"] = fmt(np.argsort(-p_gb)[:6])

    # LLM: re-treina no histórico pelo nº de épocas que minimizou a validação no backtest
    # (validação feita nos concursos 2289–2588, sempre anteriores a qualquer corte usado aqui)
    best_ep = json.loads((RESULTS / "llm.json").read_text())["melhor_epoca_validacao"]
    tokens = llm.to_tokens(order)
    ids = np.arange(llm.CTX_DRAWS, n)
    model, _, _ = llm.train(tokens, ids, [], epochs=best_ep + 1, log=False)
    ctx = tokens[(n - llm.CTX_DRAWS) * 7:n * 7]
    marg, samples = llm.sample_marginals(model, ctx, n_samples=20000)
    palpites["llm_transformer_top6_marginal"] = fmt(np.argsort(-marg)[:6])
    games, counts = np.unique(np.sort(samples, 1), axis=0, return_counts=True)
    palpites["llm_transformer_jogo_mais_gerado"] = [int(v) for v in games[counts.argmax()]]

    # Consenso: soma de rankings normalizados dos modelos com pontuação
    def rank(s):
        return np.argsort(np.argsort(s)) / 59
    cons = rank(p_gb) + rank(marg) + rank(m.mean(0)) + rank(m[-25:].mean(0))
    palpites["consenso_modelos"] = fmt(np.argsort(-cons)[:6])

    llm_top10 = [(int(i) + 1, round(float(marg[i]), 4)) for i in np.argsort(-marg)[:10]]
    return palpites, llm_top10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ate", type=int, help="usa apenas os concursos 1..ATE no treino")
    args = ap.parse_args()

    df = load()
    if args.ate:
        df = df[df.concurso <= args.ate].reset_index(drop=True)
    palpites, llm_top10 = gerar_palpites(df)
    out = {"treinado_ate_concurso": int(df.concurso.iloc[-1]),
           "treinado_ate_data": df.data.iloc[-1].strftime("%d/%m/%Y"),
           "proximo_concurso": int(df.concurso.iloc[-1]) + 1,
           "probabilidade_sena_qualquer_jogo": "1 em 50.063.860",
           "palpites": palpites,
           "llm_prob_marginal_top10": llm_top10,
           "llm_prob_marginal_esperada_se_aleatorio": 0.1}
    nome = f"previsao_ate_{args.ate}.json" if args.ate else "previsao.json"
    (RESULTS / nome).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
