"""Testes estatísticos: os sorteios da Mega-Sena se comportam como aleatórios?"""
import json

import numpy as np
from scipy import stats

from common import N_NUM, RESULTS, draws_matrix, draw_order, load


def main():
    df = load()
    m = draws_matrix(df)
    n = len(df)
    out = {"concursos": n, "primeiro": str(df.data.iloc[0].date()), "ultimo": str(df.data.iloc[-1].date())}

    # 1) Uniformidade das frequências (qui-quadrado)
    freq = m.sum(0)
    exp = n * 6 / N_NUM
    chi2, p = stats.chisquare(freq, np.full(N_NUM, exp))
    order = np.argsort(-freq)
    out["frequencia"] = {
        "esperado_por_numero": round(exp, 1),
        "mais_sorteados": [(int(i + 1), int(freq[i])) for i in order[:10]],
        "menos_sorteados": [(int(i + 1), int(freq[i])) for i in order[-10:][::-1]],
        "qui2": round(float(chi2), 2), "gl": N_NUM - 1, "p_valor": round(float(p), 4),
    }

    # 2) Dependência entre concursos consecutivos: quantos números se repetem do concurso anterior?
    rep = (m[1:] & m[:-1]).sum(1)
    out["repeticao_concurso_anterior"] = {"media_observada": round(float(rep.mean()), 4), "media_se_aleatorio": 0.6}

    # 3) Autocorrelação lag-1 por número (média dos 60) — deveria ser ~0
    ac = [np.corrcoef(m[1:, j], m[:-1, j])[0, 1] for j in range(N_NUM)]
    out["autocorrelacao_lag1"] = {"media": round(float(np.mean(ac)), 5), "max_abs": round(float(np.max(np.abs(ac))), 4),
                                  "limite_95pct_ruido": round(1.96 / np.sqrt(n), 4)}

    # 4) Soma das dezenas vs. distribuição teórica (amostragem sem reposição de 1..60)
    s = m @ np.arange(1, 61)
    mu = 6 * 30.5
    var = 6 * (60 ** 2 - 1) / 12 * (60 - 6) / (60 - 1)
    out["soma_dezenas"] = {"media_obs": round(float(s.mean()), 2), "media_teorica": mu,
                           "dp_obs": round(float(s.std()), 2), "dp_teorico": round(float(np.sqrt(var)), 2)}

    # 5) Primeira bola sorteada é uniforme?
    first = draw_order(df)[:, 0]
    c1, p1 = stats.chisquare(np.bincount(first, minlength=61)[1:])
    out["primeira_bola_uniforme_p"] = round(float(p1), 4)

    # 6) Pares/ímpares
    even = (m[:, 1::2]).sum(1)  # índices 1,3,.. => números 2,4,..
    out["pares_por_concurso_media"] = round(float(even.mean()), 3)

    (RESULTS / "analise.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
