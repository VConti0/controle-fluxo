"""Refaz as 10 bilhões de tentativas da sequência com reinício (mesmas sementes) e registra cada acerto
do concurso 1: em qual fio e tentativa aconteceu, a ordem em que as 6 bolas saíram e o estado do gerador."""
import json

import numpy as np
import pandas as pd
from numba import njit, prange

from common import RESULTS, draw_order, draws_matrix, load


@njit(parallel=True, cache=True)
def roda(W, eh, n_por_fio):
    T = W.shape[0]
    reg = np.full((4, 400, 8), -1, np.int64)     # tentativa, 6 bolas na ordem, estado do gerador (parte alta)
    n_reg = np.zeros(4, np.int64)
    for f in prange(4):
        s = np.uint64((f + 1) * 0x9E3779B97F4A7C15 + 0x77777)
        disp = np.empty(60, np.float64)
        esc = np.empty(6, np.int64)
        t = 0
        for a in range(n_por_fio):
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
                if eh[t, j] == 0:
                    ok = False
                    break
                esc[k] = j
                tot -= disp[j]
                disp[j] = 0.0
            if ok:
                if t == 0 and n_reg[f] < 400:
                    reg[f, n_reg[f], 0] = a
                    for k in range(6):
                        reg[f, n_reg[f], k + 1] = esc[k] + 1
                    reg[f, n_reg[f], 7] = np.int64(s >> np.uint64(1))
                    n_reg[f] += 1
                t += 1
                if t == T:
                    t = 0
            else:
                t = 0
    return reg, n_reg


def main():
    df = load()
    m = draws_matrix(df).astype(np.int64)
    P = np.load(RESULTS / "historico_probabilidades.npy").astype(np.float64)
    reg, n_reg = roda(P / (1 - P), m, 10_000_000_000 // 4)
    linhas = []
    for f in range(4):
        for r in reg[f, :n_reg[f]]:
            linhas.append({"fio": f + 1, "tentativa_no_fio": int(r[0]), **{f"bola{k}": int(r[k]) for k in range(1, 7)},
                           "estado_gerador": int(r[7])})
    d = pd.DataFrame(linhas).sort_values(["fio", "tentativa_no_fio"]).reset_index(drop=True)
    d["ordem"] = d[[f"bola{k}" for k in range(1, 7)]].astype(str).agg(" ".join, axis=1)
    d["intervalo_desde_o_acerto_anterior"] = d.groupby("fio").tentativa_no_fio.diff()
    d.to_csv(RESULTS / "acertos_concurso1.csv", index=False)
    real = [int(x) for x in draw_order(df)[0]]
    pos = {b: [int((d[f"bola{k}"] == b).sum()) for k in range(1, 7)] for b in sorted(real)}
    out = {"acertos": len(d), "por_fio": d.groupby("fio").size().to_dict(),
           "ordem_real_do_concurso_1": real,
           "acertos_na_ordem_real": int((d.ordem == " ".join(map(str, real))).sum()),
           "ordens_distintas": int(d.ordem.nunique()), "ordens_possiveis": 720,
           "ordem_mais_repetida": [d.ordem.value_counts().index[0], int(d.ordem.value_counts().iloc[0])],
           "vezes_que_cada_bola_saiu_em_cada_posicao": pos,
           "intervalo_medio_entre_acertos": round(float(d.intervalo_desde_o_acerto_anterior.mean())),
           "menor_intervalo": int(d.intervalo_desde_o_acerto_anterior.min()),
           "maior_intervalo": int(d.intervalo_desde_o_acerto_anterior.max())}
    (RESULTS / "acertos_concurso1.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(d.head(8).drop(columns=["estado_gerador"]).to_string(index=False))


if __name__ == "__main__":
    main()
