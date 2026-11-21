"""Simulação em sequência com reinício: acerta o concurso 1 -> tenta o 2 -> acerta -> tenta o 3...
Qualquer erro volta para o concurso 1. Mede até onde a sequência chega em N tentativas.

Uso: python3 sequencia_com_reinicio.py [n_tentativas]
"""
import json
import sys
import time

import numpy as np
from numba import njit, prange

from common import RESULTS, draws_matrix, load


@njit(parallel=True, cache=True)
def roda(W, eh, n_por_fio):
    T = W.shape[0]
    chegou = np.zeros((4, 8), np.int64)          # chegou[f, k] = vezes em que acertou k concursos seguidos
    bolas = np.zeros(4, np.int64)
    for f in prange(4):
        s = np.uint64((f + 1) * 0x9E3779B97F4A7C15 + 0x77777)
        disp = np.empty(60, np.float64)
        t = 0                                    # concurso que está tentando acertar (0 = o primeiro)
        for _ in range(n_por_fio):
            tot = 0.0
            for i in range(60):
                disp[i] = W[t, i]
                tot += W[t, i]
            ok = True
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
                bolas[f] += 1
                if eh[t, j] == 0:                # bola fora do resultado real: o sorteio já errou
                    ok = False
                    break
                tot -= disp[j]
                disp[j] = 0.0
            if ok:
                t += 1
                chegou[f, min(t, 7)] += 1
                if t == T:
                    t = 0
            else:
                t = 0
    return chegou.sum(0), bolas.sum()


def main():
    n = int(float(sys.argv[1])) if len(sys.argv) > 1 else 10_000_000_000
    m = draws_matrix(load())
    P = np.load(RESULTS / "historico_probabilidades.npy").astype(np.float64)
    W = P / (1 - P)
    t0 = time.time()
    chegou, bolas = roda(W, m.astype(np.int64), n // 4)
    dt = time.time() - t0
    vel = n / dt
    out = {"tentativas": int(n), "tempo_s": round(dt), "tentativas_por_segundo": round(vel),
           "acertou_o_concurso_1": int(chegou[1]), "acertou_1_e_2_seguidos": int(chegou[2]),
           "acertou_1_2_e_3_seguidos": int(chegou[3]), "maior_sequencia": int(np.flatnonzero(chegou).max()) if chegou.any() else 0,
           "tentativas_esperadas": {"1_concurso": 50_063_860, "2_seguidos": 50_063_860 ** 2, "3_seguidos": 50_063_860 ** 3},
           "tempo_estimado_nesta_maquina": {"2_seguidos_anos": round(50_063_860 ** 2 / vel / 3.15e7, 1),
                                            "3_seguidos_anos": float(f"{50_063_860 ** 3 / vel / 3.15e7:.1e}")}}
    (RESULTS / "sequencia_com_reinicio.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
