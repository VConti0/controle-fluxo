"""Cadeia física com registro das variáveis: reproduz todos os concursos reais em sequência, numa máquina só.

Mesma cadeia do fisica_cadeia.py (cada concurso continua do estado em que o anterior foi acertado; a cada
extração o estado é ramificado em cópias deslocadas em até 1 micrômetro e segue um ramo em que saiu uma
dezena do concurso-alvo). A diferença é que aqui tudo fica guardado, para analisar depois:

  results/cadeia_variaveis.npz   (um registro por concurso)
    concurso                      número do concurso
    ini_pos, ini_vel, ini_w       posição (m), velocidade (m/s) e rotação (rad/s) das 60 bolas no começo
    t_ini                         relógio da simulação no começo (s)
    bola[k]                       dezena que saiu na extração k (1..6)
    ext_pos, ext_vel, ext_w       posição, velocidade e rotação da bola extraída, no instante em que sai
    ext_t                         relógio no instante da extração (s)
    ext_fase_pa                   ângulo das pás no instante da extração (rad, 0 a 2*pi/4)
    ext_ramos, ext_ok             ramos simulados até achar a dezena e quantos ramos do último lote serviam
    ext_semente, ext_ramo         semente do lote e ramo escolhido (permitem refazer a extração)
    ext_energia                   energia cinética total das bolas no globo no instante da extração (J)
    ext_altura                    altura média das bolas no globo no instante da extração (m)
    ext_momento                   momento angular total em torno do eixo do globo (kg m2/s)
    ext_dist2                     distância até a boca da 2ª bola mais próxima (m): folga da extração
    ramos_total, reinicios        esforço total do concurso
  results/cadeia_variaveis_estado.npz   estado para retomar de onde parou

Uso: python3 -u fisica_cadeia_variaveis.py [minutos] [último concurso]
"""
import sys
import time

import numpy as np

import emulador as E
from common import RESULTS, load
from fisica_cadeia import DT, P0, P1, R, RB, SIGMA, VAGAS, ramos

ARQ, EST = RESULTS / "cadeia_variaveis.npz", RESULTS / "cadeia_variaveis_estado.npz"
SAIDA = np.array([0.0, 0.0, -(R - RB)])
CAMPOS = ["concurso", "ini_pos", "ini_vel", "ini_w", "t_ini", "bola", "ext_pos", "ext_vel", "ext_w", "ext_t",
          "ext_fase_pa", "ext_ramos", "ext_ok", "ext_semente", "ext_ramo", "ext_energia", "ext_altura",
          "ext_momento", "ext_dist2", "ramos_total", "reinicios"]
F32 = {"ini_pos", "ini_vel", "ini_w", "ext_pos", "ext_vel", "ext_w", "ext_energia", "ext_altura", "ext_momento",
       "ext_dist2", "ext_fase_pa"}


def grava(reg, pos, vel, w, t, prox, semente):
    np.savez_compressed(ARQ, **{c: np.array(reg[c], dtype=np.float32 if c in F32 else None) for c in CAMPOS})
    np.savez(EST, pos=pos, vel=vel, w=w, t=t, prox=prox, semente=semente)


def main():
    minutos = float(sys.argv[1]) if len(sys.argv) > 1 else 110
    dez = load()[[f"d{i}" for i in range(1, 7)]].values
    ultimo = min(int(sys.argv[2]), len(dez)) if len(sys.argv) > 2 else len(dez)
    m = E.massas()
    fase, rho, vento = 0.0, 1.2 * 293.0 / 295.0, 0.30
    if EST.exists():
        z = np.load(EST)
        pos, vel, w, t, prox, semente = z["pos"], z["vel"], z["w"], float(z["t"]), int(z["prox"]), int(z["semente"])
        a = np.load(ARQ)
        reg = {c: list(a[c]) for c in CAMPOS}
    else:
        pos = E.grade() + np.random.default_rng(0).normal(0, 0.001, (60, 3))
        vel, w, t, prox, semente = np.zeros((60, 3)), np.zeros((60, 3)), 0.0, 1, 1000
        reg = {c: [] for c in CAMPOS}
    fim, t0 = time.time() + minutos * 60, time.time()
    while prox <= ultimo and time.time() < fim:
        alvo = set(int(x) for x in dez[prox - 1])
        ini = (pos.copy(), vel.copy(), w.copy(), t)
        tentados, reinicios = 0, 0
        while True:
            pos, vel, w, t = ini[0].copy(), ini[1].copy(), ini[2].copy(), ini[3]
            ativo = np.ones(60, np.bool_)
            saiu, travou = [], False
            x = {c: [] for c in CAMPOS if c.startswith("ext_")}
            for k in range(6):
                n_passos = P0 if k == 0 else P1
                falta = alvo - set(saiu)
                gastos = 0
                while True:
                    semente += 1
                    bola, Pn, Vn, Wn = ramos(pos, vel, w, ativo, m, fase, rho, vento, t, n_passos, 48, semente, SIGMA)
                    tentados += 48
                    gastos += 48
                    ok = np.flatnonzero(np.isin(bola + 1, list(falta)))
                    if len(ok) or gastos >= 1440:
                        break
                if not len(ok):
                    travou = True
                    break
                if len(falta) == 1:
                    b = int(ok[0])
                else:                                      # ramo em que as dezenas que faltam estão mais perto da saída
                    custo = [np.linalg.norm(Pn[c][[v - 1 for v in falta if v != bola[c] + 1]] - SAIDA, axis=1).max()
                             for c in ok]
                    b = int(ok[int(np.argmin(custo))])
                j = int(bola[b])
                t += n_passos * DT
                dist = np.sort(np.linalg.norm(Pn[b][ativo] - SAIDA, axis=1))
                x["ext_pos"].append(Pn[b][j]); x["ext_vel"].append(Vn[b][j]); x["ext_w"].append(Wn[b][j])
                x["ext_t"].append(t)
                x["ext_fase_pa"].append((fase + E.W_GLOBO * t) % (2 * np.pi / E.N_PAS))
                x["ext_ramos"].append(gastos); x["ext_ok"].append(len(ok))
                x["ext_semente"].append(semente); x["ext_ramo"].append(b)
                x["ext_energia"].append(float((0.5 * m[ativo, None] * Vn[b][ativo] ** 2).sum()
                                              + (0.5 * 0.4 * m[ativo, None] * RB * RB * Wn[b][ativo] ** 2).sum()))
                x["ext_altura"].append(float(Pn[b][ativo, 2].mean()))
                x["ext_momento"].append(float((m[ativo] * (Pn[b][ativo, 1] * Vn[b][ativo, 2]
                                                           - Pn[b][ativo, 2] * Vn[b][ativo, 1])).sum()))
                x["ext_dist2"].append(float(dist[1]))
                pos, vel, w = Pn[b].copy(), Vn[b].copy(), Wn[b].copy()
                saiu.append(j + 1)
                ativo[j] = False
            if not travou:
                break
            reinicios += 1
        for q, j in enumerate(saiu):                       # as 6 bolas voltam para o topo do globo
            pos[j - 1], vel[j - 1], w[j - 1] = VAGAS[q], 0.0, 0.0
        assert set(saiu) == alvo
        for c, v in x.items():
            reg[c].append(np.array(v))
        for c, v in (("concurso", prox), ("ini_pos", ini[0]), ("ini_vel", ini[1]), ("ini_w", ini[2]), ("t_ini", ini[3]),
                     ("bola", np.array(saiu)), ("ramos_total", tentados), ("reinicios", reinicios)):
            reg[c].append(v)
        prox += 1
        if prox % 20 == 0:
            grava(reg, pos, vel, w, t, prox, semente)
            print(f"concurso {prox - 1} ok; ramos {tentados}; reinícios {reinicios}; relógio {t:.0f} s; "
                  f"{time.time() - t0:.0f} s de máquina", flush=True)
    grava(reg, pos, vel, w, t, prox, semente)
    print("parou no concurso", prox - 1, "FIM" if prox > ultimo else "", flush=True)


if __name__ == "__main__":
    main()
