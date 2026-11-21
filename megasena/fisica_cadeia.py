"""Cadeia física: reproduz os concursos reais em sequência, sempre continuando do estado em que acertou.

"Estado" = posição, velocidade e rotação das 60 bolas + condições da simulação (fase das pás, densidade
do ar, corrente de ar, relógio). A física é a do emulador.py (bola de 66 g, colisões, atrito, pás, ar).

Para cada concurso real, em ordem:
  * o globo mistura (4 s antes da 1ª bola, 1,2 s entre as seguintes);
  * a cada extração, o estado atual é ramificado em N cópias, cada uma com as bolas deslocadas em até
    1 micrômetro; cada ramo é simulado até a extração e sai a bola mais próxima da boca;
  * continua o primeiro ramo em que saiu uma dezena do concurso-alvo que ainda faltava;
  * depois das 6 dezenas, as 6 bolas voltam para o topo do globo e a simulação segue para o próximo concurso.
Depois do último concurso real, a simulação segue sem ramificar (um ramo só) até o concurso 4000.

Progresso em results/fisica_cadeia.csv e estado em results/fisica_cadeia_estado.npz (retoma de onde parou).
Uso: python3 fisica_cadeia.py [minutos]
"""
import sys
import time

import numpy as np
import pandas as pd
from numba import njit, prange

import emulador as E
from common import RESULTS, load

R, RB, K, ZETA = E.R, E.RB, E.K, E.ZETA
MU_BB, MU_BW, GAMMA_T, W_GLOBO, N_PAS, C_PA, CD, DT = E.MU_BB, E.MU_BW, E.GAMMA_T, E.W_GLOBO, E.N_PAS, E.C_PA, E.CD, E.DT
P0, P1 = int(round(E.T0 / DT)), int(round(E.T1 / DT))
SIGMA = 1e-6
ULTIMO = 4000
CSV, NPZ = RESULTS / "fisica_cadeia.csv", RESULTS / "fisica_cadeia_estado.npz"
VAGAS = np.array([[0.0, 0.12 * np.cos(a), 0.12 + 0.0 * a] for a in np.arange(6) * np.pi / 3]) + \
        np.array([[0.12 * np.sin(a), 0.0, 0.0] for a in np.arange(6) * np.pi / 3])


@njit(cache=True, fastmath=True)
def avanca(pos, vel, w, ativo, m, fase, rho, vento_y, t0, n_passos):
    n = 60
    F = np.zeros((n, 3))
    Tq = np.zeros((n, 3))
    area = np.pi * RB * RB
    for passo in range(n_passos):
        t = t0 + passo * DT
        for i in range(n):
            if not ativo[i]:
                continue
            x, y, z = pos[i, 0], pos[i, 1], pos[i, 2]
            F[i, 0] = 0.0; F[i, 1] = 0.0; F[i, 2] = -9.81 * m[i]
            Tq[i, 0] = 0.0; Tq[i, 1] = 0.0; Tq[i, 2] = 0.0
            ux, uy, uz = 0.0, vento_y - 0.3 * W_GLOBO * z, 0.3 * W_GLOBO * y
            rx, ry, rz = vel[i, 0] - ux, vel[i, 1] - uy, vel[i, 2] - uz
            vr = np.sqrt(rx * rx + ry * ry + rz * rz)
            c = 0.5 * rho * CD * area * vr
            F[i, 0] -= c * rx; F[i, 1] -= c * ry; F[i, 2] -= c * rz
            s = 0.5 * rho * np.pi * RB ** 3
            F[i, 0] += s * (w[i, 1] * rz - w[i, 2] * ry)
            F[i, 1] += s * (w[i, 2] * rx - w[i, 0] * rz)
            F[i, 2] += s * (w[i, 0] * ry - w[i, 1] * rx)
            rad = np.sqrt(x * x + y * y + z * z)
            if rad > R - RB:
                nx, ny, nz = x / rad, y / rad, z / rad
                ax, ay, az = vel[i, 0], vel[i, 1] + W_GLOBO * z, vel[i, 2] - W_GLOBO * y
                vn = ax * nx + ay * ny + az * nz
                fn = K * (rad - (R - RB)) + 2 * ZETA * np.sqrt(K * m[i]) * vn
                if fn < 0:
                    fn = 0.0
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
            if rad > R - 0.07:
                ang = np.arctan2(z, y) - (fase + W_GLOBO * t)
                if abs(np.sin(N_PAS * ang / 2)) < 0.2:
                    F[i, 0] += C_PA * (0.0 - vel[i, 0])
                    F[i, 1] += C_PA * (-W_GLOBO * z - vel[i, 1])
                    F[i, 2] += C_PA * (W_GLOBO * y - vel[i, 2])
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
                if d2 >= 4 * RB * RB or d2 == 0.0:
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
                gx, gy, gz = -ft * tx, -ft * ty, -ft * tz
                qx = -RB * (ny * gz - nz * gy)
                qy = -RB * (nz * gx - nx * gz)
                qz = -RB * (nx * gy - ny * gx)
                Tq[j, 0] += qx; Tq[j, 1] += qy; Tq[j, 2] += qz
                Tq[i, 0] += qx; Tq[i, 1] += qy; Tq[i, 2] += qz
        for i in range(n):
            if not ativo[i]:
                continue
            ine = 0.4 * m[i] * RB * RB
            for a in range(3):
                vel[i, a] += F[i, a] / m[i] * DT
                w[i, a] += Tq[i, a] / ine * DT
                pos[i, a] += vel[i, a] * DT
    melhor, dmin = -1, 1e9
    zs = -(R - RB)
    for i in range(n):
        if ativo[i]:
            dd = np.sqrt(pos[i, 0] ** 2 + pos[i, 1] ** 2 + (pos[i, 2] - zs) ** 2)
            if dd < dmin:
                dmin, melhor = dd, i
    return melhor


@njit(parallel=True, cache=True)
def ramos(pos, vel, w, ativo, m, fase, rho, vento_y, t0, n_passos, n_ramos, semente, sigma):
    Pn = np.empty((n_ramos, 60, 3))
    Vn = np.empty((n_ramos, 60, 3))
    Wn = np.empty((n_ramos, 60, 3))
    bola = np.empty(n_ramos, np.int64)
    for b in prange(n_ramos):
        s = np.uint64((semente * 100003 + b + 1) * 0x9E3779B97F4A7C15 + 0x51ED)
        Pn[b] = pos; Vn[b] = vel; Wn[b] = w
        if sigma > 0:
            for i in range(60):
                for a in range(3):
                    s ^= s >> np.uint64(12); s ^= s << np.uint64(25); s ^= s >> np.uint64(27)
                    u = np.float64((s * np.uint64(0x2545F4914F6CDD1D)) >> np.uint64(11)) / 9007199254740992.0
                    Pn[b, i, a] += (2 * u - 1) * sigma
        bola[b] = avanca(Pn[b], Vn[b], Wn[b], ativo, m, fase, rho, vento_y, t0, n_passos)
    return bola, Pn, Vn, Wn


def main():
    minutos = float(sys.argv[1]) if len(sys.argv) > 1 else 110
    df = load()
    dez = df[[f"d{i}" for i in range(1, 7)]].values
    n_real = len(dez)
    m = E.massas()
    fase, rho, vento = 0.0, 1.2 * 293.0 / 295.0, 0.30
    if NPZ.exists():
        z = np.load(NPZ)
        pos, vel, w, t, prox = z["pos"], z["vel"], z["w"], float(z["t"]), int(z["prox"])
        linhas = pd.read_csv(CSV).to_dict("records")
    else:
        pos = E.grade() + np.random.default_rng(0).normal(0, 0.001, (60, 3))
        vel, w, t, prox, linhas = np.zeros((60, 3)), np.zeros((60, 3)), 0.0, 1, []
    fim = time.time() + minutos * 60
    semente = prox * 1000
    while prox <= ULTIMO and time.time() < fim:
        livre = prox > n_real
        alvo = set() if livre else set(int(x) for x in dez[prox - 1])
        ativo = np.ones(60, np.bool_)
        saiu, tentados = [], 0
        for k in range(6):
            n_passos = P0 if k == 0 else P1
            falta = alvo - set(saiu)
            n_ramos = 1 if livre else 4 * int(np.ceil(60 / max(len(falta), 1) * (60 - k) / 60))
            while True:
                semente += 1
                bola, Pn, Vn, Wn = ramos(pos, vel, w, ativo, m, fase, rho, vento, t, n_passos, n_ramos, semente,
                                         0.0 if livre else SIGMA)
                tentados += n_ramos
                ok = np.arange(n_ramos) if livre else np.flatnonzero(np.isin(bola + 1, list(falta)))
                if len(ok):
                    b = int(ok[0])
                    break
            pos, vel, w = Pn[b].copy(), Vn[b].copy(), Wn[b].copy()
            j = int(bola[b])
            saiu.append(j + 1)
            ativo[j] = False
            t += n_passos * DT
        raio = float(np.linalg.norm(pos[ativo], axis=1).max())
        for q, j in enumerate(saiu):                       # as 6 bolas voltam para o topo do globo
            pos[j - 1], vel[j - 1], w[j - 1] = VAGAS[q], 0.0, 0.0
        linhas.append({"concurso": prox, "tipo": "previsto" if livre else "reproduzido",
                       "ordem_de_saida": " ".join(f"{x:02d}" for x in saiu),
                       "dezenas": " ".join(f"{x:02d}" for x in sorted(saiu)), "ramos_simulados": tentados,
                       "relogio_s": round(t, 2), "raio_max_m": round(raio, 4),
                       "altura_media_m": round(float(pos[:, 2].mean()), 4)})
        prox += 1
        if prox % 20 == 0 or prox > n_real:
            pd.DataFrame(linhas).to_csv(CSV, index=False)
            np.savez(NPZ, pos=pos, vel=vel, w=w, t=t, prox=prox, fase=fase, rho=rho, vento=vento)
            print(f"concurso {prox - 1} ok; ramos no último: {tentados}; relógio {t:.0f} s", flush=True)
    pd.DataFrame(linhas).to_csv(CSV, index=False)
    np.savez(NPZ, pos=pos, vel=vel, w=w, t=t, prox=prox, fase=fase, rho=rho, vento=vento)
    print("parou no concurso", prox - 1)


if __name__ == "__main__":
    main()
