"""Procura ligação entre as variáveis da cadeia física (cadeia_variaveis.npz) e os resultados.

Três perguntas, cada uma comparada com o acaso por permutação:

A. Estado inicial x bola sorteada: para cada concurso, as 6 bolas que saem diferem das outras 54 em alguma
   variável do estado inicial (distância até a boca, altura, raio, velocidade, rotação, massa, se a bola
   saiu no concurso anterior)? Medida: AUC (0,5 = sem ligação). O acaso é estimado sorteando 6 bolas
   quaisquer no lugar das reais.
B. Variáveis da extração x dezena: o número da bola que sai tem correlação com alguma variável no instante
   da extração (ângulo das pás, energia, altura média, momento angular, velocidade e rotação da bola)?
C. Ligação entre concursos seguidos: cada variável resumida por concurso tem autocorrelação de um concurso
   para o seguinte? E ela se liga ao resultado (soma das dezenas, pares, repetidas do anterior)?

Uso: python3 cadeia_analise.py   ->  results/cadeia_analise.json
"""
import json

import numpy as np

import emulador as E
from common import RESULTS
from fisica_cadeia import R, RB

RNG = np.random.default_rng(7)
SAIDA = np.array([0.0, 0.0, -(R - RB)])
N_PERM = 2000


def auc(score, y):
    """Área sob a curva ROC de score para o rótulo y (postos médios nos empates)."""
    o = np.argsort(score, kind="stable")
    r = np.empty(len(score)); r[o] = np.arange(1, len(score) + 1)
    s = np.asarray(score)[o]
    i = 0
    while i < len(s):                       # postos médios
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = (i + j + 2) / 2
        i = j + 1
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def p_perm(obs, nulos, centro):
    nulos = np.asarray(nulos)
    return float(((np.abs(nulos - centro) >= abs(obs - centro)).sum() + 1) / (len(nulos) + 1))


def main():
    a = np.load(RESULTS / "cadeia_variaveis.npz")
    n = len(a["concurso"])
    bola = a["bola"].astype(int)                                  # (n, 6) na ordem de saída
    m = E.massas()
    saiu = np.zeros((n, 60), bool)
    saiu[np.arange(n)[:, None], bola - 1] = True
    anterior = np.zeros((n, 60), bool); anterior[1:] = saiu[:-1]
    pos, vel, w = a["ini_pos"].astype(float), a["ini_vel"].astype(float), a["ini_w"].astype(float)

    # ---------------- A: estado inicial de cada bola x sair no concurso
    feats = {"distancia_ate_a_boca": np.linalg.norm(pos - SAIDA, axis=2),
             "altura_z": pos[:, :, 2], "posicao_x_eixo": pos[:, :, 0], "posicao_y": pos[:, :, 1],
             "raio_ao_centro": np.linalg.norm(pos, axis=2),
             "velocidade": np.linalg.norm(vel, axis=2), "velocidade_vertical": vel[:, :, 2],
             "rotacao": np.linalg.norm(w, axis=2),
             "massa_da_bola": np.broadcast_to(m, (n, 60)),
             "saiu_no_concurso_anterior": anterior.astype(float),
             "numero_da_bola": np.broadcast_to(np.arange(1, 61.0), (n, 60))}
    idx = np.arange(1, n)                                          # o 1º concurso não tem "anterior"
    A = {}
    for nome, f in feats.items():
        obs = auc(f[idx].ravel(), saiu[idx].ravel())
        nulos = []
        for _ in range(200):                                       # 6 bolas ao acaso em cada concurso
            y = np.zeros((len(idx), 60), bool)
            y[np.arange(len(idx))[:, None], np.argsort(RNG.random((len(idx), 60)), 1)[:, :6]] = True
            nulos.append(auc(f[idx].ravel(), y.ravel()))
        A[nome] = {"auc": round(obs, 4), "acaso_media": round(float(np.mean(nulos)), 4),
                   "acaso_desvio": round(float(np.std(nulos)), 4),
                   "z": round(float((obs - np.mean(nulos)) / (np.std(nulos) + 1e-12)), 2),
                   "p": round(p_perm(obs, nulos, float(np.mean(nulos))), 4)}
    # o mesmo, sem as 6 bolas recolocadas no topo (isola o efeito de ter saído no anterior)
    A_sem = {}
    for nome in ("distancia_ate_a_boca", "altura_z", "massa_da_bola", "raio_ao_centro", "velocidade", "rotacao"):
        f = feats[nome][idx]; mask = ~anterior[idx]
        obs = auc(f[mask], saiu[idx][mask])
        nulos = []
        for _ in range(200):
            y = np.zeros((len(idx), 60), bool)
            y[np.arange(len(idx))[:, None], np.argsort(RNG.random((len(idx), 60)), 1)[:, :6]] = True
            nulos.append(auc(f[mask], y[mask]))
        A_sem[nome] = {"auc": round(obs, 4), "acaso_desvio": round(float(np.std(nulos)), 4),
                       "z": round(float((obs - np.mean(nulos)) / (np.std(nulos) + 1e-12)), 2),
                       "p": round(p_perm(obs, nulos, float(np.mean(nulos))), 4)}

    # ---------------- B: variáveis no instante da extração x dezena que sai
    ext = {"angulo_das_pas": a["ext_fase_pa"], "energia_cinetica": a["ext_energia"], "altura_media": a["ext_altura"],
           "momento_angular": a["ext_momento"], "folga_2a_bola": a["ext_dist2"],
           "ramos_gastos": a["ext_ramos"], "ramos_que_serviam": a["ext_ok"],
           "bola_x": a["ext_pos"][:, :, 0], "bola_y": a["ext_pos"][:, :, 1],
           "bola_velocidade": np.linalg.norm(a["ext_vel"], axis=2), "bola_rotacao": np.linalg.norm(a["ext_w"], axis=2)}
    alvos = {"numero_da_dezena": bola.astype(float), "massa_da_bola": m[bola - 1]}
    B = {}
    for nome, v in ext.items():
        v = np.asarray(v, float)
        linha = {}
        for an, y in alvos.items():
            obs = corr(v.ravel(), y.ravel())
            nulos = [corr(v.ravel(), RNG.permutation(y.ravel())) for _ in range(N_PERM)]
            linha[an] = {"r": round(obs, 4), "p": round(p_perm(obs, nulos, 0.0), 4)}
        B[nome] = linha

    # ---------------- C: resumo por concurso, autocorrelação e ligação com o resultado
    por = {"energia_media": a["ext_energia"].mean(1), "altura_media": a["ext_altura"].mean(1),
           "momento_angular_medio": a["ext_momento"].mean(1), "angulo_das_pas_1a_bola": a["ext_fase_pa"][:, 0],
           "ramos_total": a["ramos_total"].astype(float), "folga_media": a["ext_dist2"].mean(1),
           "energia_inicial": (0.5 * m[None, :, None] * vel ** 2).sum((1, 2)),
           "altura_inicial_media": pos[:, :, 2].mean(1),
           "rotacao_inicial_media": np.linalg.norm(w, axis=2).mean(1)}
    res = {"soma_das_dezenas": bola.sum(1).astype(float), "qtd_pares": (bola % 2 == 0).sum(1).astype(float),
           "repetidas_do_anterior": np.r_[0, (saiu[1:] & saiu[:-1]).sum(1)].astype(float),
           "massa_media_das_6": m[bola - 1].mean(1), "maior_dezena": bola.max(1).astype(float)}
    C = {}
    for nome, v in por.items():
        v = np.asarray(v, float)
        ac = corr(v[:-1], v[1:])
        nulos = []
        for _ in range(N_PERM):
            q = RNG.permutation(v); nulos.append(corr(q[:-1], q[1:]))
        linha = {"autocorrelacao_lag1": round(ac, 4), "p_autocorrelacao": round(p_perm(ac, nulos, 0.0), 4), "x_resultado": {}}
        for rn, y in res.items():
            obs = corr(v, y)
            nulos = [corr(v, RNG.permutation(y)) for _ in range(N_PERM)]
            linha["x_resultado"][rn] = {"r": round(obs, 4), "p": round(p_perm(obs, nulos, 0.0), 4)}
        C[nome] = linha
    res_auto = {rn: round(corr(y[:-1], y[1:]), 4) for rn, y in res.items()}

    n_testes = len(A) + len(A_sem) + 2 * len(B) + len(C) * (1 + len(res))
    out = {"concursos_na_cadeia": int(n), "ramos_simulados": int(a["ramos_total"].sum()),
           "reinicios": int(a["reinicios"].sum()), "relogio_final_s": round(float(a["ext_t"][-1, -1]), 1),
           "ramos_medios_por_extracao": [round(float(x), 1) for x in a["ext_ramos"].mean(0)],
           "testes_feitos": n_testes, "p_necessario_bonferroni": round(0.05 / n_testes, 5),
           "A_estado_inicial_x_bola_sorteada": A, "A_sem_as_bolas_recolocadas": A_sem,
           "B_extracao_x_dezena": B, "C_por_concurso": C, "autocorrelacao_dos_resultados_reais": res_auto}
    (RESULTS / "cadeia_analise.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
