"""Investigação da anomalia de frequência (alguns números saem mais que outros).

Perguntas:
  1. Quando começa?            varredura de ponto de mudança + qui² por blocos
  2. É real ou garimpo?        p global por simulação, repetindo a MESMA varredura em históricos honestos
  3. Quais números carregam?   desvios no período anômalo, com correção de múltiplos testes
  4. É persistente?            metade ímpar x metade par dos concursos, e terços consecutivos
  5. Coincide com equipamento? qui² por tipo de local e correlação dos desvios entre locais
  6. Aparece na ordem do sorteio? 1ª bola x 6ª bola
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

from common import RESULTS, ROOT, draw_order, draws_matrix, load

P0 = 0.1
PASSO = 50


def qui2(c, n):
    """qui² das contagens e p-valor corrigido (sem reposição: E[qui²] = 54, não 59)."""
    x = ((c - n * P0) ** 2 / (n * P0)).sum(-1)
    return x, stats.chi2.sf(x * 59 / 54, 59)


def varredura(m):
    """Para cada ponto de corte s, qui² do trecho [s, fim). Devolve cortes, qui² e p de cada um."""
    n = len(m)
    cs = np.vstack([np.zeros(60), np.cumsum(m, 0)])
    cortes = np.arange(0, n - 300, PASSO)
    x, p = qui2(cs[n] - cs[cortes], (n - cortes)[:, None] * np.ones(1))
    return cortes, x, p


def metades(m):
    """Correlação entre os desvios de frequência dos concursos pares e dos ímpares do mesmo período."""
    a, b = m[::2].mean(0), m[1::2].mean(0)
    return float(np.corrcoef(a, b)[0, 1])


def main():
    df = load()
    m = draws_matrix(df).astype(float)
    n = len(m)
    comp = pd.read_csv(ROOT / "data" / "megasena_completo.csv")
    rng = np.random.default_rng(11)
    out = {"concursos": n}

    # ---------- 1. quando começa
    cortes, x, p = varredura(m)
    k = int(p.argmin())
    s0 = int(cortes[k])
    out["ponto_de_mudanca"] = {"concurso": int(df.concurso[s0]), "data": str(df.data[s0].date()),
                               "qui2_depois": round(float(x[k]), 1), "p_depois": float(p[k]),
                               "concursos_depois": n - s0}
    xa, pa = qui2(m[:s0].sum(0), s0)
    out["antes_do_ponto"] = {"concursos": s0, "qui2": round(float(xa), 1), "p": round(float(pa), 4)}
    blocos = []
    for i in range(0, n, 250):
        j = min(i + 250, n)
        if j - i < 100:
            break
        xb, pb = qui2(m[i:j].sum(0), j - i)
        blocos.append({"concursos": f"{int(df.concurso[i])}-{int(df.concurso[j - 1])}",
                       "anos": f"{df.data[i].year}-{df.data[j - 1].year}",
                       "qui2": round(float(xb), 1), "p": round(float(pb), 4)})
    out["blocos_de_250"] = blocos

    # ---------- 2. real ou garimpo: mesma varredura em 3000 históricos honestos
    S = 3000
    minp, chi_tot = np.empty(S), np.empty(S)
    for i in range(S):
        sim = np.zeros((n, 60))
        sim[np.arange(n)[:, None], np.argsort(rng.random((n, 60)), 1)[:, :6]] = 1
        _, xs, ps = varredura(sim)
        minp[i], chi_tot[i] = ps.min(), xs[0]
    out["significancia_global"] = {
        "simulacoes": S,
        "p_historico_inteiro": round(float((chi_tot >= x[0]).mean()), 4),
        "p_global_da_varredura": round(float((minp <= p[k]).mean()), 4),
        "leitura": "fração de históricos honestos em que a melhor janela é tão extrema quanto a real"}

    # ---------- 3. quais números
    d = m[s0:]
    nd = len(d)
    z = (d.sum(0) - nd * P0) / np.sqrt(nd * P0 * (1 - P0))
    pz = 2 * stats.norm.sf(np.abs(z))
    o = np.argsort(pz)
    q = np.empty(60)
    q[o] = np.minimum.accumulate((pz[o] * 60 / (np.arange(60) + 1))[::-1])[::-1]
    out["numeros_no_periodo_anomalo"] = [
        {"numero": int(i + 1), "vezes": int(d[:, i].sum()), "esperado": round(nd * P0, 1),
         "z": round(float(z[i]), 2), "q": round(float(q[i]), 4)} for i in np.argsort(-np.abs(z))[:12]]
    out["numeros_significativos_q<0.05"] = [int(i + 1) for i in np.flatnonzero(q < 0.05)]
    sem = np.delete(np.arange(60), np.argsort(-np.abs(z))[:2])
    xs_, ps_ = qui2(d[:, sem].sum(0), nd)
    out["sem_os_2_mais_extremos"] = {"removidos": [int(i + 1) for i in np.argsort(-np.abs(z))[:2]],
                                     "qui2_restantes_58": round(float(((d[:, sem].sum(0) - nd * P0) ** 2 / (nd * P0)).sum()), 1),
                                     "esperado": round(54 * 58 / 60, 1)}

    # ---------- 4. persistência
    nulo = np.array([metades((np.argsort(rng.random((nd, 60)), 1) < 6).astype(float)) for _ in range(2000)])
    r_dep, r_ant = metades(d), metades(m[:s0])
    t3 = np.array_split(np.arange(nd), 3)
    f3 = [d[i].mean(0) for i in t3]
    out["persistencia"] = {
        "pares_x_impares_depois": round(r_dep, 3), "p": round(float((nulo >= r_dep).mean()), 4),
        "pares_x_impares_antes": round(r_ant, 3),
        "nulo_media_e_p95": [round(float(nulo.mean()), 3), round(float(np.percentile(nulo, 95)), 3)],
        "tercos_consecutivos_depois": {"1x2": round(float(np.corrcoef(f3[0], f3[1])[0, 1]), 3),
                                       "2x3": round(float(np.corrcoef(f3[1], f3[2])[0, 1]), 3),
                                       "1x3": round(float(np.corrcoef(f3[0], f3[2])[0, 1]), 3)},
        "antes_x_depois": round(float(np.corrcoef(m[:s0].mean(0), d.mean(0))[0, 1]), 3)}
    # tamanho do viés: variância real das probabilidades (método dos momentos)
    tau2 = max(0.0, (x[k] - 54) * P0 / nd / 60)
    out["tamanho_do_vies"] = {"desvio_padrao_real_das_probabilidades_pct": round(float(np.sqrt(tau2) * 100), 3),
                              "leitura": "quanto a chance real de cada número se afasta de 10%, em pontos percentuais"}

    # ---------- 5. equipamento / local
    loc = comp["tipo_local"].values
    por_local = {}
    for L in pd.unique(loc):
        for nome, mask in (("antes", np.arange(n) < s0), ("depois", np.arange(n) >= s0)):
            sel = (loc == L) & mask
            if sel.sum() >= 150:
                xl, pl = qui2(m[sel].sum(0), sel.sum())
                por_local[f"{L} ({nome})"] = {"concursos": int(sel.sum()), "qui2": round(float(xl), 1),
                                              "p": round(float(pl), 4),
                                              "anos": f"{df.data[sel].min().year}-{df.data[sel].max().year}"}
    out["por_tipo_de_local"] = por_local
    dep = np.arange(n) >= s0
    locs = [L for L in pd.unique(loc[dep]) if ((loc == L) & dep).sum() >= 150]
    out["correlacao_dos_desvios_entre_locais_depois"] = {
        f"{a} x {b}": round(float(np.corrcoef(m[(loc == a) & dep].mean(0), m[(loc == b) & dep].mean(0))[0, 1]), 3)
        for i, a in enumerate(locs) for b in locs[i + 1:]}
    ch = np.flatnonzero(loc[1:] != loc[:-1]) + 1
    perto = [(int(df.concurso[c]), str(df.data[c].date()), f"{loc[c - 1]} -> {loc[c]}") for c in ch if abs(c - s0) <= 150]
    out["mudancas_de_local_perto_do_ponto"] = perto[:8]

    # ---------- 6. ordem do sorteio
    ordem = draw_order(df)[s0:]
    c1 = np.bincount(ordem[:, 0], minlength=61)[1:]
    c6 = np.bincount(ordem[:, 5], minlength=61)[1:]
    out["ordem_do_sorteio_depois"] = {
        "primeira_bola_qui2_p": round(float(stats.chisquare(c1)[1]), 4),
        "sexta_bola_qui2_p": round(float(stats.chisquare(c6)[1]), 4),
        "correlacao_1a_x_6a": round(float(np.corrcoef(c1, c6)[0, 1]), 3)}

    (RESULTS / "anomalia.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
