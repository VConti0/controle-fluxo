"""Simula 2 bilhões de sorteios do próximo concurso a partir das probabilidades do modelo.

Cada sorteio tira 6 bolas sem reposição; a chance de cada bola sair é proporcional ao peso que o modelo
(combinacoes.py) deu a ela para o próximo concurso. Conta quantas vezes saiu cada número e cada uma das
50.063.860 combinações.

Uso: python3 simular_2bi.py [n_sorteios]
"""
import json
import sys
import time
from math import comb

import numpy as np
from numba import njit, prange

from common import RESULTS

N_COMB = 50_063_860
BIN = np.array([[comb(n, k) for k in range(7)] for n in range(61)], dtype=np.int64)


@njit(cache=True)
def bloco(w, n, semente, cont_num, cont_comb, binom):
    s = np.uint64(semente * 0x9E3779B97F4A7C15 + 0x1234567)
    disp = np.empty(60, np.float64)
    esc = np.empty(6, np.int64)
    for _ in range(n):
        tot = 0.0
        for i in range(60):
            disp[i] = w[i]
            tot += w[i]
        for k in range(6):
            s ^= s >> np.uint64(12); s ^= s << np.uint64(25); s ^= s >> np.uint64(27)      # xorshift64*
            u = (np.float64((s * np.uint64(0x2545F4914F6CDD1D)) >> np.uint64(11)) / 9007199254740992.0) * tot
            acc, j = 0.0, 0
            for i in range(60):
                acc += disp[i]
                if u < acc:
                    j = i
                    break
                j = i
            while disp[j] == 0.0:           # arredondamento na borda: volta para uma bola disponível
                j -= 1
            tot -= disp[j]
            disp[j] = 0.0
            esc[k] = j
            cont_num[j] += 1
        for a in range(1, 6):               # ordena as 6
            v = esc[a]; b = a - 1
            while b >= 0 and esc[b] > v:
                esc[b + 1] = esc[b]; b -= 1
            esc[b + 1] = v
        r = 0
        for k in range(6):
            r += binom[esc[k], k + 1]
        if cont_comb[r] < 65535:
            cont_comb[r] += 1


@njit(parallel=True, cache=True)
def simula(w, n_por_bloco, binom):
    cn = np.zeros((4, 60), np.int64)
    cc = np.zeros((4, N_COMB), np.uint16)
    for b in prange(4):
        bloco(w, n_por_bloco, b + 1, cn[b], cc[b], binom)
    return cn.sum(0), cc


def desfaz_rank(r):
    jogo = []
    for k in range(6, 0, -1):
        c = k - 1
        while comb(c + 1, k) <= r:
            c += 1
        jogo.append(c + 1)
        r -= comb(c, k)
    return sorted(jogo)


def main():
    n = int(float(sys.argv[1])) if len(sys.argv) > 1 else 2_000_000_000
    mod = json.loads((RESULTS / "combinacoes.json").read_text())
    p = np.array([mod["probabilidade_por_numero_pct"][str(i)] for i in range(1, 61)]) / 100
    w = p / (1 - p)
    t = time.time()
    cn, cc = simula(w, n // 4, BIN)
    total = (n // 4) * 4
    cc_tot = cc[0].astype(np.uint32) + cc[1] + cc[2] + cc[3]
    del cc
    freq = cn / total
    top = np.argpartition(cc_tot, -20)[-20:]
    top = top[np.argsort(-cc_tot[top].astype(np.int64))]
    media = total / N_COMB
    out = {"concurso": mod["proximo_concurso"], "sorteios_simulados": int(total),
           "tempo_s": round(time.time() - t), "media_de_vezes_por_combinacao": round(media, 2),
           "numeros": [{"numero": int(i + 1), "saiu_em_pct_dos_sorteios": round(float(freq[i] * 100), 4),
                        "peso_do_modelo_pct": round(float(p[i] * 100), 2)} for i in np.argsort(-freq)],
           "combinacoes_mais_sorteadas": [{"jogo": desfaz_rank(int(r)), "vezes": int(cc_tot[r]),
                                           "vezes_sobre_a_media": round(float(cc_tot[r] / media), 2)} for r in top],
           "combinacao_menos_sorteada": {"jogo": desfaz_rank(int(cc_tot.argmin())), "vezes": int(cc_tot.min())},
           "combinacoes_nunca_sorteadas": int((cc_tot == 0).sum())}
    (RESULTS / "simulacao_2bi.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"{total:,} sorteios em {out['tempo_s']} s; média por combinação {media:.1f}")
    print("números:", [(d["numero"], d["saiu_em_pct_dos_sorteios"]) for d in out["numeros"][:12]])
    for c in out["combinacoes_mais_sorteadas"][:10]:
        print(" ".join(f"{x:02d}" for x in c["jogo"]), c["vezes"], c["vezes_sobre_a_media"])
    print("menos:", out["combinacao_menos_sorteada"], "nunca:", out["combinacoes_nunca_sorteadas"])


if __name__ == "__main__":
    main()
