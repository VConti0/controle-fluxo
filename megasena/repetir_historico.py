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

from common import RESULTS, draw_order, draws_matrix, load

N_COMB = 50_063_860


@njit(parallel=True, cache=True)
def conta(W, alvo, ordem, n_sim):
    T = W.shape[0]
    exato = np.zeros(T, np.int64)
    na_ordem = np.zeros(T, np.int64)
    rodadas = np.full((T, 32), -1, np.int64)      # em quais rodadas saiu a sena exata
    acertos = np.zeros((T, 7), np.int64)
    for t in prange(T):
        s = np.uint64((t + 1) * 0x9E3779B97F4A7C15 + 0xABCDEF)
        disp = np.empty(60, np.float64)
        eh = np.zeros(60, np.int64)
        for k in range(6):
            eh[alvo[t, k]] = 1
        for r in range(n_sim):
            tot = 0.0
            for i in range(60):
                disp[i] = W[t, i]
                tot += W[t, i]
            h = 0
            seq = 1
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
                if j != ordem[t, k]:
                    seq = 0
            acertos[t, h] += 1
            if h == 6:
                if exato[t] < 32:
                    rodadas[t, exato[t]] = r
                exato[t] += 1
                na_ordem[t] += seq
    return exato, acertos, na_ordem, rodadas


def main():
    n_sim = int(float(sys.argv[1])) if len(sys.argv) > 1 else 3_000_000
    df = load()
    m = draws_matrix(df)
    P = np.load(RESULTS / "historico_probabilidades.npy").astype(np.float64)[1:]     # concursos 2..3088
    alvo = np.argsort(-m[1:], axis=1, kind="stable")[:, :6].astype(np.int64)
    ordem = (draw_order(df)[1:] - 1).astype(np.int64)
    T = len(P)
    t0 = time.time()
    ex_mod, ac_mod, or_mod, rd_mod = conta(P / (1 - P), alvo, ordem, n_sim)
    ex_uni, ac_uni, or_uni, rd_uni = conta(np.full_like(P, 1.0), alvo, ordem, n_sim)

    def seguidos(rd):
        """Maior sequência de concursos consecutivos acertados na MESMA rodada e nº de pares seguidos."""
        pares, maior = 0, 1 if (rd >= 0).any() else 0
        vivos = {}
        for t in range(len(rd)):
            atuais = {int(r) for r in rd[t] if r >= 0}
            novo = {r: vivos.get(r, 0) + 1 for r in atuais}
            pares += sum(1 for r in atuais if r in vivos)
            if novo:
                maior = max(maior, max(novo.values()))
            vivos = novo
        return pares, maior

    par_mod, seq_mod = seguidos(rd_mod)
    par_uni, seq_uni = seguidos(rd_uni)
    esperado = n_sim / N_COMB
    d = pd.DataFrame({"concurso": df.concurso.values[1:], "ano": df.data.dt.year.values[1:],
                      "real": [" ".join(f"{x + 1:02d}" for x in a) for a in alvo],
                      "vezes_modelo": ex_mod, "vezes_uniforme": ex_uni,
                      "na_ordem_modelo": or_mod, "na_ordem_uniforme": or_uni})
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
           "mesma_ordem_das_bolas": {"modelo": int(or_mod.sum()), "uniforme": int(or_uni.sum()),
                                     "esperado_teorico": round(T * esperado / 720, 3)},
           "concursos_seguidos_na_mesma_rodada": {
               "pares_seguidos": {"modelo": par_mod, "uniforme": par_uni},
               "maior_sequencia": {"modelo": seq_mod, "uniforme": seq_uni},
               "esperado_teorico_de_pares": float(f"{(T - 1) * n_sim / N_COMB ** 2:.2e}")},
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
