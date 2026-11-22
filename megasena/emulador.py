"""Emulador físico do sorteio, versão compilada (numba), com a bola real da Caixa.

Bola: 66 g, 50 mm, borracha maciça (dado divulgado pela Caixa).
Cenário estimado (não verificado em vídeo): globo de 60 cm a 45 rpm em eixo horizontal, 4 pás internas,
saída por baixo, 4 s de mistura antes da 1ª bola e 1,2 s entre as seguintes.

O conjunto de bolas é fixo: cada bola tem uma massa própria (variação de fabricação com desvio de 0,3%),
a mesma em todos os sorteios. O que muda de um sorteio para outro é o estado inicial: posição das bolas
(folga de 1 mm), fase das pás, temperatura e corrente de ar.

Uso: python3 emulador.py [n_sorteios]   ->  results/emulador_<n>.csv e results/emulador_massas.csv
"""
import sys
import time
from multiprocessing import Pool

import numpy as np
from numba import njit

from common import RESULTS

R, RB = 0.30, 0.025
M0 = 0.066
K, E_REST = 6600.0, 0.7
MU_BB, MU_BW, GAMMA_T = 0.3, 0.5, 6.6
W_GLOBO = 2 * np.pi * 0.75
N_PAS, C_PA = 4, 1.3
CD = 0.47
DT, T0, T1 = 3.5e-4, 4.0, 1.2
ZETA = -np.log(E_REST) / np.sqrt(np.pi ** 2 + np.log(E_REST) ** 2)
DESVIO_MASSA = 0.003
SEMENTE_BOLAS = 2026


def massas():
    """Massa de cada bola do conjunto (kg). Fixa para todos os sorteios."""
    return M0 * (1 + np.random.default_rng(SEMENTE_BOLAS).normal(0, DESVIO_MASSA, 60))


def grade():
    pts = []
    passo = 2 * RB + 0.004
    for z in np.arange(-R + 2 * RB, R, passo):
        for y in np.arange(-R, R, passo):
            for x in np.arange(-R, R, passo):
                if x * x + y * y + z * z < (R - 1.5 * RB) ** 2:
                    pts.append((x, y, z))
    return np.array(pts[:60])


@njit(cache=True, fastmath=True)
def nucleo(pos, m, fase, rho, vento_y):
    n = 60
    vel = np.zeros((n, 3))
    w = np.zeros((n, 3))
    F = np.zeros((n, 3))
    Tq = np.zeros((n, 3))
    ativo = np.ones(n, np.bool_)
    saida = np.zeros(6, np.int64)
    area = np.pi * RB * RB
    zs = -(R - RB)
    t_prox, k_ext, passo = T0, 0, 0
    while k_ext < 6:
        t = passo * DT
        for i in range(n):
            if not ativo[i]:
                continue
            x, y, z = pos[i, 0], pos[i, 1], pos[i, 2]
            # gravidade
            F[i, 0] = 0.0; F[i, 1] = 0.0; F[i, 2] = -9.81 * m[i]
            Tq[i, 0] = 0.0; Tq[i, 1] = 0.0; Tq[i, 2] = 0.0
            # ar: corrente + ar girando com o globo (velocidade W x r, eixo x)
            ux, uy, uz = 0.0, vento_y - 0.3 * W_GLOBO * z, 0.3 * W_GLOBO * y
            rx, ry, rz = vel[i, 0] - ux, vel[i, 1] - uy, vel[i, 2] - uz
            vr = np.sqrt(rx * rx + ry * ry + rz * rz)
            c = 0.5 * rho * CD * area * vr
            F[i, 0] -= c * rx; F[i, 1] -= c * ry; F[i, 2] -= c * rz
            s = 0.5 * rho * np.pi * RB ** 3                      # Magnus: s * (w x v_rel)
            F[i, 0] += s * (w[i, 1] * rz - w[i, 2] * ry)
            F[i, 1] += s * (w[i, 2] * rx - w[i, 0] * rz)
            F[i, 2] += s * (w[i, 0] * ry - w[i, 1] * rx)
            # parede do globo
            rad = np.sqrt(x * x + y * y + z * z)
            if rad > R - RB:
                nx, ny, nz = x / rad, y / rad, z / rad
                wx_, wy_, wz_ = 0.0, -W_GLOBO * z, W_GLOBO * y      # velocidade da parede
                ax, ay, az = vel[i, 0] - wx_, vel[i, 1] - wy_, vel[i, 2] - wz_
                vn = ax * nx + ay * ny + az * nz
                fn = K * (rad - (R - RB)) + 2 * ZETA * np.sqrt(K * m[i]) * vn
                if fn < 0:
                    fn = 0.0
                # velocidade tangencial no ponto de contato: v - vn n + RB (w x n)
                tx = ax - vn * nx + RB * (w[i, 1] * nz - w[i, 2] * ny)
                ty = ay - vn * ny + RB * (w[i, 2] * nx - w[i, 0] * nz)
                tz = az - vn * nz + RB * (w[i, 0] * ny - w[i, 1] * nx)
                vt = np.sqrt(tx * tx + ty * ty + tz * tz) + 1e-12
                ft = min(MU_BW * fn, GAMMA_T * vt) / vt
                fx, fy, fz = -ft * tx, -ft * ty, -ft * tz
                F[i, 0] += -fn * nx + fx; F[i, 1] += -fn * ny + fy; F[i, 2] += -fn * nz + fz
                Tq[i, 0] += RB * (ny * fz - nz * fy)
                Tq[i, 1] += RB * (nz * fx - nx * fz)
                Tq[i, 2] += RB * (nx * fy - ny * fx)
            # pás
            if rad > R - 0.07:
                ang = np.arctan2(z, y) - (fase + W_GLOBO * t)
                if abs(np.sin(N_PAS * ang / 2)) < 0.2:
                    F[i, 1] += C_PA * (-W_GLOBO * z - vel[i, 1])
                    F[i, 2] += C_PA * (W_GLOBO * y - vel[i, 2])
                    F[i, 0] += C_PA * (0.0 - vel[i, 0])
        # bola-bola
        for i in range(n - 1):
            if not ativo[i]:
                continue
            for j in range(i + 1, n):
                if not ativo[j]:
                    continue
                dx = pos[j, 0] - pos[i, 0]
                if dx > 2 * RB or dx < -2 * RB:
                    continue
                dy = pos[j, 1] - pos[i, 1]
                dz = pos[j, 2] - pos[i, 2]
                d2 = dx * dx + dy * dy + dz * dz
                if d2 >= 4 * RB * RB:
                    continue
                d = np.sqrt(d2)
                nx, ny, nz = dx / d, dy / d, dz / d
                mef = m[i] * m[j] / (m[i] + m[j])
                ax, ay, az = vel[j, 0] - vel[i, 0], vel[j, 1] - vel[i, 1], vel[j, 2] - vel[i, 2]
                vn = ax * nx + ay * ny + az * nz
                fn = K * (2 * RB - d) - 2 * ZETA * np.sqrt(K * mef) * vn
                if fn < 0:
                    fn = 0.0
                sx, sy, sz = w[i, 0] + w[j, 0], w[i, 1] + w[j, 1], w[i, 2] + w[j, 2]
                tx = ax - vn * nx - RB * (sy * nz - sz * ny)
                ty = ay - vn * ny - RB * (sz * nx - sx * nz)
                tz = az - vn * nz - RB * (sx * ny - sy * nx)
                vt = np.sqrt(tx * tx + ty * ty + tz * tz) + 1e-12
                ft = min(MU_BB * fn, GAMMA_T * vt) / vt
                fx, fy, fz = fn * nx - ft * tx, fn * ny - ft * ty, fn * nz - ft * tz
                F[j, 0] += fx; F[j, 1] += fy; F[j, 2] += fz
                F[i, 0] -= fx; F[i, 1] -= fy; F[i, 2] -= fz
                gx, gy, gz = -ft * tx, -ft * ty, -ft * tz          # força tangencial em j
                qx = RB * (-(ny * gz - nz * gy))
                qy = RB * (-(nz * gx - nx * gz))
                qz = RB * (-(nx * gy - ny * gx))
                Tq[j, 0] += qx; Tq[j, 1] += qy; Tq[j, 2] += qz
                Tq[i, 0] += qx; Tq[i, 1] += qy; Tq[i, 2] += qz
        # integração
        for i in range(n):
            if not ativo[i]:
                continue
            ine = 0.4 * m[i] * RB * RB
            for a in range(3):
                vel[i, a] += F[i, a] / m[i] * DT
                w[i, a] += Tq[i, a] / ine * DT
                pos[i, a] += vel[i, a] * DT
        passo += 1
        if passo * DT >= t_prox:
            melhor, dmin = -1, 1e9
            for i in range(n):
                if ativo[i]:
                    dd = np.sqrt(pos[i, 0] ** 2 + pos[i, 1] ** 2 + (pos[i, 2] - zs) ** 2)
                    if dd < dmin:
                        dmin, melhor = dd, i
            saida[k_ext] = melhor + 1
            ativo[melhor] = False
            k_ext += 1
            t_prox += T1
    return saida


GRADE = grade()
MASSAS = massas()


def sorteio(semente):
    rng = np.random.default_rng(semente)
    pos = GRADE + rng.normal(0, 0.001, (60, 3))
    fase = rng.uniform(0, 2 * np.pi)
    rho = 1.2 * 293.0 / (295.0 + rng.normal(0, 1.0))
    vento = 0.30 + rng.normal(0, 0.05)
    return nucleo(pos, MASSAS, fase, rho, vento)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    sorteio(0)                                   # compila antes de abrir os processos
    t = time.time()
    with Pool(4) as pool:
        res = np.array(pool.map(sorteio, range(n), chunksize=25))
    assert all(len(set(r)) == 6 for r in res)
    cab = "sorteio,o1,o2,o3,o4,o5,o6,d1,d2,d3,d4,d5,d6"
    tab = np.c_[np.arange(1, n + 1), res, np.sort(res, 1)]
    np.savetxt(RESULTS / f"emulador_{n}.csv", tab, fmt="%d", delimiter=",", header=cab, comments="")
    np.savetxt(RESULTS / "emulador_massas.csv", np.c_[np.arange(1, 61), MASSAS * 1000], fmt=["%d", "%.4f"],
               delimiter=",", header="numero,massa_g", comments="")
    print(f"{n} sorteios em {time.time() - t:.0f} s; salvo em results/emulador_{n}.csv")


if __name__ == "__main__":
    main()
