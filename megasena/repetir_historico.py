"""Para cada concurso passado, simula N sorteios com as probabilidades que o modelo tinha antes dele e
conta quantas vezes sai exatamente a combinação que foi sorteada de verdade.

Uso: python3 repetir_historico.py [n_por_concurso]   (padrão: 3.000.000)
"""
import json
import sys
import time

import numpy as np
import pandas as pd
from numba import njit, prange

from common import RESULTS, draws_matrix, load

N_COMB = 50_063_860


@njit(parallel=True, cache=True)
def conta(W, alvo, n_sim):
    T = W.shape[0]
    exato = np.zeros(T, np.int64)
    acertos = np.zeros((T, 7), np.int64)
    for t in prange(T):
        s = np.uint64((t + 1) * 0x9E3779B97F4A7C15 + 0xABCDEF)
        disp = np.empty(60, np.float64)
        eh = np.zeros(60, np.int64)
        for k in range(6):
            eh[alvo[t, k]] = 1
        for _ in range(n_sim):
            tot = 0.0
            for i in range(60):
                disp[i] = W[t, i]
                tot += W[t, i]
            h = 0
            for k in range(6):
                s ^= s >> np.uint64(12); s ^= s << np.uint64(25); s ^= s >> np.uint64(27)
                u = (np.float64((s * np.uint64(0x2545F4914F6CDD1D)) >> np.uint64(11)) / 9007199254740992.0) * tot
                acc, j = 0.0, 0
                for i in range(60):
                    acc += disp[i]
                    if u < acc:
                        j = i
                        break
                    j = i
                while disp[j] == 0.0:
                    j -= 1
                tot -= disp[j]
                disp[j] = 0.0
                h += eh[j]
            acertos[t, h] += 1
            if h == 6:
                exato[t] += 1
    return exato, acertos


def main():
    n_sim = int(float(sys.argv[1])) if len(sys.argv) > 1 else 3_000_000
    df = load()
    m = draws_matrix(df)
    P = np.load(RESULTS / "historico_probabilidades.npy").astype(np.float64)[1:]     # concursos 2..3088
    alvo = np.argsort(-m[1:], axis=1, kind="stable")[:, :6].astype(np.int64)
    T = len(P)
    t0 = time.time()
    ex_mod, ac_mod = conta(P / (1 - P), alvo, n_sim)
    ex_uni, ac_uni = conta(np.full_like(P, 1.0), alvo, n_sim)
    esperado = n_sim / N_COMB
    d = pd.DataFrame({"concurso": df.concurso.values[1:], "ano": df.data.dt.year.values[1:],
                      "real": [" ".join(f"{x + 1:02d}" for x in a) for a in alvo],
                      "vezes_modelo": ex_mod, "vezes_uniforme": ex_uni})
    d.to_csv(RESULTS / "repetir_historico.csv", index=False)
    g = d.groupby("ano")
    ano = pd.DataFrame({"concursos": g.size(), "vezes_modelo": g.vezes_modelo.sum(), "vezes_uniforme": g.vezes_uniforme.sum(),
                        "esperado_teorico": (g.size() * esperado).round(1)})
    ano.to_csv(RESULTS / "repetir_historico_por_ano.csv")
    tot_sim = T * n_sim
    out = {"concursos": T, "simulacoes_por_concurso": n_sim, "simulacoes_no_total": int(tot_sim),
           "tempo_s": round(time.time() - t0),
           "esperado_teorico_por_concurso": round(esperado, 4), "esperado_teorico_total": round(T * esperado, 1),
           "sena_repetida_modelo": int(ex_mod.sum()), "sena_repetida_uniforme": int(ex_uni.sum()),
           "razao_modelo_sobre_esperado": round(float(ex_mod.sum() / (T * esperado)), 3),
           "concursos_em_que_o_real_saiu_ao_menos_1_vez": {"modelo": int((ex_mod > 0).sum()), "uniforme": int((ex_uni > 0).sum())},
           "maximo_de_vezes_num_concurso": {"modelo": int(ex_mod.max()), "uniforme": int(ex_uni.max())},
           "distribuicao_de_acertos_pct": {
               "modelo": {str(h): round(float(ac_mod[:, h].sum() / tot_sim * 100), 5) for h in range(7)},
               "uniforme": {str(h): round(float(ac_uni[:, h].sum() / tot_sim * 100), 5) for h in range(7)}},
           "acertos_medios": {"modelo": round(float((ac_mod * np.arange(7)).sum() / tot_sim), 4),
                              "uniforme": round(float((ac_uni * np.arange(7)).sum() / tot_sim), 4)},
           "concursos_mais_repetidos_pelo_modelo": d.nlargest(8, "vezes_modelo")[["concurso", "real", "vezes_modelo"]].to_dict("records")}
    (RESULTS / "repetir_historico.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(ano.to_string())


if __name__ == "__main__":
    main()
