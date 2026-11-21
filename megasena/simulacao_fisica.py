"""Simulador físico determinístico de um sorteio: 60 bolas em um globo giratório.

Parte da premissa "nada é acaso": dado o estado inicial, o resultado é uma conta. O modelo inclui
  * peso de cada bola (massa individual) e gravidade;
  * colisão bola-bola e bola-parede (mola + amortecimento, coeficiente de restituição ~0,8);
  * atrito nos contatos, que faz cada bola girar (rotação própria), e força de Magnus;
  * rotação do globo e 4 pás internas que arrastam as bolas;
  * ar: arrasto quadrático, corrente do ar-condicionado e densidade do ar pela temperatura.
A cada extração sai a bola mais próxima da boca de saída, no fundo do globo.

IMPORTANTE: as medidas (raio do globo, massa das bolas, rotação, pás) são valores plausíveis escolhidos
por mim. Não são as especificações do equipamento da Caixa, que não são públicas nos dados que temos.
O que o simulador mostra é o comportamento desse tipo de sistema, não o próximo resultado real.

Experimentos:
  A  100 sorteios, bolas idênticas, estado inicial com incerteza de 1 mm
  B  caos: 20 pares de sorteios idênticos, exceto uma bola deslocada 1 nanômetro
  C  peso: 100 sorteios com 5 bolas 10% mais leves e 5 bolas 10% mais pesadas
"""
import json
import sys
from multiprocessing import Pool

import numpy as np

from common import RESULTS

R, RB = 0.30, 0.025                 # raio do globo e da bola (m)
M0 = 0.004                          # massa nominal da bola (kg)
G = np.array([0.0, 0.0, -9.81])
K, E_REST = 400.0, 0.8              # rigidez do contato (N/m) e restituição
MU_BB, MU_BW, GAMMA_T = 0.3, 0.5, 0.4
OMEGA = np.array([2 * np.pi * 0.75, 0.0, 0.0])   # globo a 45 rpm em torno do eixo x
N_PAS, C_PA = 4, 0.08               # pás internas e força de arrasto delas
CD, AREA = 0.47, np.pi * RB ** 2
DT, T0, T1 = 3.5e-4, 4.0, 1.2       # passo, mistura inicial e intervalo entre extrações (s)
SAIDA = np.array([0.0, 0.0, -(R - RB)])
ZETA = -np.log(E_REST) / np.sqrt(np.pi ** 2 + np.log(E_REST) ** 2)
LEVES, PESADAS = [7, 19, 28, 41, 53], [4, 16, 33, 45, 58]


def estado_inicial(rng):
    """Bolas carregadas em ordem numérica numa grade na metade de baixo do globo, com folga de 1 mm."""
    pts = []
    passo = 2 * RB + 0.004
    for z in np.arange(-R + 2 * RB, R, passo):
        for y in np.arange(-R, R, passo):
            for x in np.arange(-R, R, passo):
                if x * x + y * y + z * z < (R - 1.5 * RB) ** 2:
                    pts.append((x, y, z))
    pos = np.array(pts[:60]) + rng.normal(0, 0.001, (60, 3))
    return pos


def simular(args):
    """Devolve as 6 bolas extraídas (1..60) e, se pedido, a trajetória durante a mistura inicial."""
    semente, eps_massa, perturbacao, gravar = args
    rng = np.random.default_rng(semente)
    pos = estado_inicial(rng)
    fase = rng.uniform(0, 2 * np.pi)                    # posição inicial das pás
    temp = 295.0 + rng.normal(0, 1.0)                   # temperatura da sala (K)
    vento = np.array([0.0, 0.30 + rng.normal(0, 0.05), 0.0])   # corrente do ar-condicionado (m/s)
    pos[0, 0] += perturbacao
    rho = 1.2 * 293.0 / temp
    m = M0 * (1 + np.asarray(eps_massa, float))
    inercia = (2 / 3) * m * RB ** 2
    vel, w = np.zeros((60, 3)), np.zeros((60, 3))
    ativo = np.ones(60, bool)
    iu = np.triu_indices(60, 1)
    extraidas, traj = [], []
    t_ext = [T0 + k * T1 for k in range(6)]
    passo, n_passos = 0, int(round(t_ext[-1] / DT)) + 1
    while len(extraidas) < 6:
        t = passo * DT
        F = m[:, None] * G
        Tq = np.zeros((60, 3))
        # ar: arrasto + Magnus, com o ar girando um pouco junto com o globo
        u = vento + 0.3 * np.cross(OMEGA, pos)
        vr = vel - u
        F += -0.5 * rho * CD * AREA * np.linalg.norm(vr, axis=1)[:, None] * vr
        F += 0.5 * rho * np.pi * RB ** 3 * np.cross(w, vr)
        # bola-bola
        d = pos[iu[1]] - pos[iu[0]]
        dist = np.linalg.norm(d, axis=1)
        c = np.flatnonzero((dist < 2 * RB) & ativo[iu[0]] & ativo[iu[1]])
        if len(c):
            i, j = iu[0][c], iu[1][c]
            nrm = d[c] / dist[c, None]
            mef = m[i] * m[j] / (m[i] + m[j])
            vrel = vel[j] - vel[i]
            vn = (vrel * nrm).sum(1)
            fn = np.maximum(K * (2 * RB - dist[c]) - 2 * ZETA * np.sqrt(K * mef) * vn, 0)
            vt = vrel - vn[:, None] * nrm - RB * np.cross(w[i] + w[j], nrm)
            vtn = np.linalg.norm(vt, axis=1) + 1e-12
            ft = -np.minimum(MU_BB * fn, GAMMA_T * vtn)[:, None] * vt / vtn[:, None]
            fj = fn[:, None] * nrm + ft
            np.add.at(F, j, fj)
            np.add.at(F, i, -fj)
            tq = RB * np.cross(-nrm, ft)
            np.add.at(Tq, j, tq)
            np.add.at(Tq, i, tq)
        # bola-parede (globo girando)
        rad = np.linalg.norm(pos, axis=1)
        c = np.flatnonzero((rad > R - RB) & ativo)
        if len(c):
            nrm = pos[c] / rad[c, None]                       # aponta para fora
            vrel = vel[c] - np.cross(OMEGA, pos[c])
            vn = (vrel * nrm).sum(1)
            fn = np.maximum(K * (rad[c] - (R - RB)) + 2 * ZETA * np.sqrt(K * m[c]) * vn, 0)
            vt = vrel - vn[:, None] * nrm + RB * np.cross(w[c], nrm)
            vtn = np.linalg.norm(vt, axis=1) + 1e-12
            ft = -np.minimum(MU_BW * fn, GAMMA_T * vtn)[:, None] * vt / vtn[:, None]
            F[c] += -fn[:, None] * nrm + ft
            Tq[c] += RB * np.cross(nrm, ft)
        # pás: bolas perto da parede e alinhadas com uma pá são arrastadas na velocidade do globo
        ang = np.arctan2(pos[:, 2], pos[:, 1]) - (fase + OMEGA[0] * t)
        perto = (rad > R - 0.07) & (np.abs(np.sin(N_PAS * ang / 2)) < 0.2) & ativo
        F[perto] += C_PA * (np.cross(OMEGA, pos[perto]) - vel[perto])
        # integração
        vel[ativo] += F[ativo] / m[ativo, None] * DT
        w[ativo] += Tq[ativo] / inercia[ativo, None] * DT
        pos[ativo] += vel[ativo] * DT
        passo += 1
        if gravar and t < T0 and passo % 100 == 0:
            traj.append(pos.copy())
        if passo * DT >= t_ext[len(extraidas)] or passo > n_passos:
            dsai = np.where(ativo, np.linalg.norm(pos - SAIDA, axis=1), np.inf)
            b = int(dsai.argmin())
            extraidas.append(b + 1)
            ativo[b] = False
            pos[b] = 1e3 + 10.0 * b
    return extraidas, (np.array(traj) if gravar else None)


def main():
    n_sort = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    zeros = [0.0] * 60
    eps_c = np.zeros(60)
    eps_c[np.array(LEVES) - 1], eps_c[np.array(PESADAS) - 1] = -0.10, 0.10
    tarefas = ([(s, zeros, 0.0, False) for s in range(n_sort)] +                       # A
               [(1000 + s, zeros, p, True) for s in range(20) for p in (0.0, 1e-9)] +  # B
               [(2000 + s, list(eps_c), 0.0, False) for s in range(n_sort)])           # C
    with Pool(4) as pool:
        res = pool.map(simular, tarefas, chunksize=2)
    A = [r[0] for r in res[:n_sort]]
    B = res[n_sort:n_sort + 40]
    C = [r[0] for r in res[n_sort + 40:]]

    out = {"aviso": "parâmetros físicos plausíveis, não as especificações reais do equipamento da Caixa",
           "parametros": {"raio_globo_m": R, "raio_bola_m": RB, "massa_bola_g": M0 * 1000, "rpm_globo": 45,
                          "pas": N_PAS, "restituicao": E_REST, "passo_s": DT, "mistura_inicial_s": T0,
                          "intervalo_extracoes_s": T1}}

    # ---- A
    cont = np.bincount(np.concatenate(A), minlength=61)[1:]
    esp = n_sort * 0.1
    qui = float(((cont - esp) ** 2 / esp).sum())
    out["A_sorteios"] = {"n": n_sort, "jogos": [sorted(j) for j in A], "ordem_de_saida": A,
                         "jogos_distintos": len({tuple(sorted(j)) for j in A}),
                         "qui2_uniformidade": round(qui, 1), "qui2_esperado": 54,
                         "mais_sorteados": [(int(i + 1), int(cont[i])) for i in np.argsort(-cont)[:6]],
                         "menos_sorteados": [(int(i + 1), int(cont[i])) for i in np.argsort(cont)[:6]],
                         "correlacao_numero_x_frequencia": round(float(np.corrcoef(np.arange(60), cont)[0, 1]), 3)}

    # ---- B
    iguais, comuns, taxas = 0, [], []
    for k in range(20):
        (j0, t0), (j1, t1) = B[2 * k], B[2 * k + 1]
        iguais += sorted(j0) == sorted(j1)
        comuns.append(len(set(j0) & set(j1)))
        sep = np.linalg.norm(t0 - t1, axis=2).mean(1)
        tt = (np.arange(len(sep)) + 1) * 100 * DT
        ok = (sep > 1e-9) & (sep < 1e-3)
        if ok.sum() > 5:
            taxas.append(np.polyfit(tt[ok], np.log(sep[ok]), 1)[0])
    lam = float(np.median(taxas))
    out["B_caos"] = {"pares": 20, "perturbacao_m": 1e-9, "pares_com_mesmo_resultado": int(iguais),
                     "dezenas_em_comum_media": round(float(np.mean(comuns)), 2), "esperado_se_independentes": 0.6,
                     "expoente_de_lyapunov_por_s": round(lam, 2),
                     "tempo_para_o_erro_dobrar_s": round(float(np.log(2) / lam), 3),
                     "tempo_de_1nm_ate_1cm_s": round(float(np.log(1e-2 / 1e-9) / lam), 2),
                     "precisao_inicial_para_prever_4s_de_mistura_m": float(f"{1e-2 * np.exp(-lam * T0):.1e}")}

    # ---- C
    cc = np.bincount(np.concatenate(C), minlength=61)[1:]
    le, pe = cc[np.array(LEVES) - 1].sum(), cc[np.array(PESADAS) - 1].sum()
    dp = np.sqrt(n_sort * 5 * 0.1 * 0.9)
    out["C_peso"] = {"n": n_sort, "bolas_leves_-10pct": LEVES, "bolas_pesadas_+10pct": PESADAS,
                     "saidas_das_leves": int(le), "saidas_das_pesadas": int(pe),
                     "esperado_por_grupo": n_sort * 0.5, "desvio_padrao_do_acaso": round(float(dp), 1),
                     "z_leves": round(float((le - n_sort * 0.5) / dp), 2),
                     "z_pesadas": round(float((pe - n_sort * 0.5) / dp), 2)}

    (RESULTS / "simulacao_fisica.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    resumo = {k: ({kk: vv for kk, vv in v.items() if kk not in ("jogos", "ordem_de_saida")} if isinstance(v, dict) else v)
              for k, v in out.items()}
    print(json.dumps(resumo, indent=1, ensure_ascii=False))
    print("Primeiros 10 jogos simulados:", [" ".join(f"{x:02d}" for x in sorted(j)) for j in A[:10]])


if __name__ == "__main__":
    main()
