#!/usr/bin/env python3
"""Comitê preditivo multi-modelo (ensemble) para a Mega-Sena.

Etapa 1 - cinco modelos base, cada um devolve um score para cada número de 1 a 60:
  M1  Hipergeométrica + regressão à média (frequência histórica encolhida para 10%)
  M2  Auditoria: qui-quadrado e entropia de Shannon em janelas móveis (10, 50, 100), atraso e volante
  M3  Monte Carlo de máxima entropia: 100.000 sorteios ponderados pelos desvios recentes
  M4  Séries temporais: ARIMA(3,0,0) por número + extrapolação de Fourier (FFT)
  M5  Machine learning não-linear: XGBoost com features de engenharia + rede LSTM
Etapa 2 - meta-modelo: scores normalizados (0 a 1), soft voting + stacking (regressão logística
  treinada só em previsões passadas) e filtro combinatório (soma, pares, linhas e colunas).
Etapa 3 - backtest walk-forward nos últimos N concursos contra palpites aleatórios e Top 5 jogos.

Todo score do concurso t usa apenas os concursos anteriores a t.

Uso:
    python3 ensemble.py --csv data/megasena.csv --backtest 20
O arquivo pode ser CSV ou Excel com 6 colunas de dezenas (d1..d6, Bola1..Bola6 ou Dezena1..Dezena6).
Sem arquivo, o script gera um histórico simulado só para demonstrar o fluxo.
"""
import argparse
import json
import re
import sys
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats
from sklearn.linear_model import LogisticRegression
from statsmodels.regression.linear_model import yule_walker

try:
    import torch
    import torch.nn as nn
except ImportError:  # a LSTM é opcional; sem torch o M5 usa só o XGBoost
    torch = None

warnings.filterwarnings("ignore")

NUMS = np.arange(1, 61)
P0 = 6 / 60                                   # probabilidade base de cada número por sorteio
LINHA, COLUNA = (NUMS - 1) // 10, (NUMS - 1) % 10   # volante: 6 linhas x 10 colunas
QUAD = (LINHA >= 3) * 2 + (COLUNA >= 5)
PAR = NUMS % 2 == 0
PRIMO = np.isin(NUMS, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59])
HIPER = stats.hypergeom(60, 6, 6).pmf(np.arange(7))   # P(X = k), N=60, K=6, n=6
MODELOS = ["M1_hipergeometrica", "M2_auditoria", "M3_monte_carlo", "M4_arima_fft", "M5_xgboost_lstm"]


# ----------------------------------------------------------------------------- dados
def carregar(caminho):
    """Lê CSV/Excel e devolve (nº dos concursos, matriz binária n x 60)."""
    p = Path(caminho) if caminho else None
    if p is None or not p.exists():
        print("AVISO: arquivo de resultados não encontrado; usando histórico SIMULADO.", file=sys.stderr)
        rng = np.random.default_rng(0)
        dez = np.argsort(rng.random((3000, 60)), axis=1)[:, :6] + 1
        conc = np.arange(1, 3001)
    else:
        df = pd.read_excel(p) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p, sep=None, engine="python")
        cols = [c for c in df.columns if re.fullmatch(r"(d|bola|dezena)[ _]?\d", str(c).strip().lower())][:6]
        if len(cols) != 6:
            sys.exit("Não encontrei 6 colunas de dezenas (d1..d6, Bola1..Bola6 ou Dezena1..Dezena6).")
        ccol = next((c for c in df.columns if "concurso" in str(c).lower()), None)
        if ccol:
            df = df.sort_values(ccol)
        dez = df[cols].astype(int).values
        conc = df[ccol].astype(int).values if ccol else np.arange(1, len(df) + 1)
    m = np.zeros((len(dez), 60), dtype=np.int8)
    m[np.arange(len(dez))[:, None], dez - 1] = 1
    assert (m.sum(1) == 6).all(), "há concursos sem 6 dezenas distintas entre 1 e 60"
    return conc, m


def minmax(v):
    v = np.asarray(v, float)
    r = v.max() - v.min()
    return (v - v.min()) / r if r > 0 else np.full(len(v), 0.5)


# ----------------------------------------------------------------------------- M1
def m1_hipergeometrica(hist):
    """Âncora: cada número tem 10% por sorteio (contagem ~ Binomial(n, 0.1)). A regressão à média entra
    como encolhimento (Bayes empírico): só a parte do desvio que excede o ruído esperado é mantida."""
    n = len(hist)
    c = hist.sum(0)
    z = (c - n * P0) / np.sqrt(n * P0 * (1 - P0))
    chi2 = ((c - n * P0) ** 2 / (n * P0)).sum()          # E[chi2] = 54 sob sorteio honesto
    b = max(0.0, 1 - 54 / chi2)
    return P0 + b * (c / n - P0), {"z": z, "chi2": chi2, "encolhimento": b}


# ----------------------------------------------------------------------------- M2
def m2_auditoria(hist):
    """Janelas móveis: desvios de frequência ponderados pelo quão anômala a janela é (1 - p do qui²),
    mais atraso (ciclo) e distribuição espacial no volante."""
    t = len(hist)
    comp, soma_a, diag = np.zeros(60), 0.0, {}
    for w in (10, 50, 100):
        j = hist[-w:]
        k = len(j)
        c = j.sum(0)
        chi2 = ((c - k * P0) ** 2 / (k * P0)).sum()
        p = stats.chi2.sf(chi2 * 59 / 54, 59)
        q = c[c > 0] / c.sum()
        ent = float(-(q * np.log2(q)).sum() / np.log2(60))
        a = 1 - p
        comp += a * (c - k * P0) / np.sqrt(k * P0 * (1 - P0))
        soma_a += a
        diag[w] = {"chi2": round(float(chi2), 1), "p": round(float(p), 3), "entropia_rel": round(ent, 4)}
    anomalia = comp / max(soma_a, 1e-9)
    atraso = np.where(hist.sum(0) == 0, t, hist[::-1].argmax(0))
    ciclo = 1 - (1 - P0) ** atraso                           # P(já ter saído) pela geométrica
    j = hist[-50:]
    k = len(j)
    zl = (np.array([j[:, LINHA == r].sum() for r in range(6)]) - k) / np.sqrt(k * 0.7627)
    zc = (np.array([j[:, COLUNA == c].sum() for c in range(10)]) - 0.6 * k) / np.sqrt(k * 0.4942)
    volante = (zl[LINHA] + zc[COLUNA]) / 2
    return (minmax(anomalia) + minmax(ciclo) + minmax(volante)) / 3, {"janelas": diag, "atraso": atraso}


# ----------------------------------------------------------------------------- M3
def m3_monte_carlo(hist, rng, n_sim):
    """Máxima entropia com médias-alvo = frequência recente (meia-vida de 300 concursos) encolhida.
    A distribuição de máxima entropia é exponencial (peso = odds do alvo); simulamos n_sim sorteios
    sem reposição com esses pesos e medimos em quantos cada número aparece."""
    t = len(hist)
    w = 0.5 ** ((t - 1 - np.arange(t)) / 300)
    ew = (w[:, None] * hist).sum(0) / w.sum()
    n_ef = w.sum() ** 2 / (w ** 2).sum()
    chi2 = ((ew - P0) ** 2).sum() * n_ef / P0
    alvo = P0 + max(0.0, 1 - 54 / chi2) * (ew - P0)
    logw = np.log(alvo / (1 - alvo))
    gumbel = -np.log(-np.log(rng.random((n_sim, 60), dtype=np.float32) + 1e-12) + 1e-12)
    jogos = np.argpartition(-(logw + gumbel), 6, axis=1)[:, :6]
    return np.bincount(jogos.ravel(), minlength=60) / n_sim, {"jogos": jogos, "n_efetivo": n_ef}


# ----------------------------------------------------------------------------- M4
def m4_arima_fft(hist, janela=512):
    """Cada número é um sinal 0/1. ARIMA(3,0,0) por Yule-Walker prevê t+1; a FFT reconstrói o sinal
    com os 3 picos mais fortes do espectro e o estende um passo (extensão periódica)."""
    x = hist[-janela:].astype(float)
    W = len(x)
    mu = x.mean(0)
    ar, phi1 = np.empty(60), np.zeros(60)
    for i in range(60):
        try:
            rho, _ = yule_walker(x[:, i], order=3, method="mle", demean=True)
            ar[i] = mu[i] + rho @ (x[-1:-4:-1, i] - mu[i])
            phi1[i] = rho[0]
        except Exception:
            ar[i] = mu[i]
    X = np.fft.rfft(x - mu, axis=0)[1:]
    pot = np.abs(X) ** 2
    top = np.argsort(-pot, axis=0)[:3]
    fft = mu + (2 / W) * np.take_along_axis(X, top, 0).real.sum(0)   # valor no instante W (= fase em 0)
    periodo = W / (top[0] + 1)
    g = pot.max(0) / pot.sum(0)                                      # teste g de Fisher por número
    p_fisher = np.minimum(1, len(pot) * (1 - g) ** (len(pot) - 1))
    return (minmax(ar) + minmax(fft)) / 2, {"phi1": phi1, "periodo": periodo, "p_fisher": p_fisher}


# ----------------------------------------------------------------------------- M5
FEATURES = ["freq_10", "freq_25", "freq_50", "freq_100", "freq_300", "freq_total", "atraso", "media_movel_atraso",
            "atraso_sobre_media", "saiu_no_ultimo", "soma_ultimo", "soma_mm10", "pares_ultimo", "primos_ultimo",
            "quadrante_proprio_ultimo", "linha_propria_10", "coluna_propria_10",
            "numero", "par", "primo", "quadrante", "linha", "coluna"]


def features_ml(m):
    """Tensor (n+1, 60, n_features): a fatia t usa só m[:t]. A fatia n descreve o próximo concurso."""
    n = len(m)
    T = n + 1
    idx = np.arange(T)
    cs = np.vstack([np.zeros((1, 60)), np.cumsum(m, 0)])
    f = [(cs[idx] - cs[np.maximum(idx - w, 0)]) / w for w in (10, 25, 50, 100, 300)]
    f.append(cs[idx] / np.maximum(idx, 1)[:, None])
    atraso, media = np.zeros((T, 60)), np.full((T, 60), 9.0)
    ult, gaps = np.full(60, -1), np.full((60, 5), np.nan)
    for t in range(T):
        atraso[t] = t - ult - 1
        cnt = (~np.isnan(gaps)).sum(1)
        media[t] = np.where(cnt > 0, np.nansum(gaps, 1) / np.maximum(cnt, 1), 9.0)
        if t < n:
            s = np.flatnonzero(m[t])
            gaps[s] = np.roll(gaps[s], 1, axis=1)
            gaps[s, 0] = t - ult[s] - 1
            ult[s] = t
    f += [atraso, media, atraso / (media + 1)]
    f.append(np.vstack([np.zeros((1, 60)), m]))                       # saiu no último concurso
    rep = lambda v: np.repeat(np.asarray(v, float)[:, None], 60, 1)
    soma = m @ NUMS
    cs_s = np.concatenate([[0], np.cumsum(soma)])
    mm10 = np.where(idx > 0, (cs_s[idx] - cs_s[np.maximum(idx - 10, 0)]) / np.maximum(np.minimum(idx, 10), 1), 183)
    f += [rep(np.concatenate([[183], soma])), rep(mm10),
          rep(np.concatenate([[3], m[:, PAR].sum(1)])), rep(np.concatenate([[1.7], m[:, PRIMO].sum(1)]))]
    qc = np.vstack([np.full((1, 4), 1.5), np.stack([m[:, QUAD == q].sum(1) for q in range(4)], 1)])
    f.append(qc[:, QUAD])
    for grupo, k in ((LINHA, 6), (COLUNA, 10)):
        g = np.stack([m[:, grupo == r].sum(1) for r in range(k)], 1)
        cg = np.vstack([np.zeros((1, k)), np.cumsum(g, 0)])
        f.append((cg[idx] - cg[np.maximum(idx - 10, 0)])[:, grupo])
    f += [np.tile(v, (T, 1)).astype(float) for v in (NUMS / 60, PAR, PRIMO, QUAD, LINHA, COLUNA)]
    return np.stack(f, 2)


if torch is not None:
    class RedeLSTM(nn.Module):
        def __init__(self, h=48):
            super().__init__()
            self.lstm = nn.LSTM(60, h, batch_first=True)
            self.drop = nn.Dropout(0.3)
            self.saida = nn.Linear(h, 60)
            nn.init.constant_(self.saida.bias, float(np.log(P0 / (1 - P0))))

        def forward(self, x):
            y, _ = self.lstm(x)
            return self.saida(self.drop(y[:, -1]))


class M5:
    """XGBoost (features tabulares) + LSTM (sequência dos últimos 20 concursos), treinados só em < ate."""
    L = 20

    def __init__(self, m, F):
        self.m, self.F = m, F

    def treinar(self, ate):
        X = self.F[100:ate].reshape(-1, self.F.shape[2])
        y = self.m[100:ate].reshape(-1)
        self.xgb = xgb.XGBClassifier(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
                                     colsample_bytree=0.8, min_child_weight=20, reg_lambda=5.0,
                                     tree_method="hist", n_jobs=4, random_state=0).fit(X, y)
        self.lstm = None
        if torch is not None:
            torch.manual_seed(0)
            torch.set_num_threads(2)
            d = torch.tensor(self.m[:ate], dtype=torch.float32)
            Xs = d.unfold(0, self.L, 1).permute(0, 2, 1)[:-1]         # janelas que terminam antes do alvo
            ys = d[self.L:]
            rede = RedeLSTM()
            opt = torch.optim.Adam(rede.parameters(), lr=2e-3, weight_decay=1e-4)
            perda = nn.BCEWithLogitsLoss()
            for _ in range(6):
                for b in torch.randperm(len(Xs)).split(64):
                    opt.zero_grad()
                    perda(rede(Xs[b]), ys[b]).backward()
                    opt.step()
            self.lstm = rede.eval()

    def prever(self, t):
        p = self.xgb.predict_proba(self.F[t])[:, 1]
        if self.lstm is None:
            return p, {"xgb": p}
        with torch.no_grad():
            x = torch.tensor(self.m[t - self.L:t], dtype=torch.float32).unsqueeze(0)
            pl = torch.sigmoid(self.lstm(x))[0].numpy()
        return (p + pl) / 2, {"xgb": p, "lstm": pl}


# ----------------------------------------------------------------------------- camada base
def camada_base(m, t_ini, n_sim, retreino, log=True):
    """Scores normalizados (60 x 5) para cada concurso t em [t_ini, n]; t = n é o próximo sorteio."""
    n = len(m)
    rng = np.random.default_rng(2026)
    m5 = M5(m, features_ml(m))
    S, diag = {}, {}
    for t in range(t_ini, n + 1):
        if (t - t_ini) % retreino == 0 or t == n:
            m5.treinar(t)
        hist = m[:t]
        s1, d1 = m1_hipergeometrica(hist)
        s2, d2 = m2_auditoria(hist)
        s3, d3 = m3_monte_carlo(hist, rng, n_sim)
        s4, d4 = m4_arima_fft(hist)
        s5, d5 = m5.prever(t)
        S[t] = np.c_[minmax(s1), minmax(s2), minmax(s3), minmax(s4), minmax(s5)]
        if t == n:
            diag = {"m1": d1, "m2": d2, "m3": d3, "m4": d4, "m5": d5, "bruto": np.c_[s1, s2, s3, s4, s5],
                    "importancia_xgb": dict(zip(FEATURES, m5.xgb.feature_importances_))}
        if log and (t - t_ini) % 20 == 0:
            print(f"  camada base: {t - t_ini + 1}/{n + 1 - t_ini}", file=sys.stderr, flush=True)
    return S, diag


# ----------------------------------------------------------------------------- meta-modelo
def meta_modelo(S, m, t, janela):
    """Soft voting (média dos 5 scores) + stacking (logística treinada nos scores dos `janela` concursos
    anteriores a t, que já eram previsões fora da amostra). Score final = média dos dois, normalizados."""
    X = np.concatenate([S[u] for u in range(t - janela, t)])
    y = m[t - janela:t].reshape(-1)
    meta = LogisticRegression(C=1.0, max_iter=1000).fit(X, y)
    stack = meta.predict_proba(S[t])[:, 1]
    voto = S[t].mean(1)
    return {"voto": voto, "stack": stack, "final": (minmax(voto) + minmax(stack)) / 2, "coef": meta.coef_[0]}


def passa_filtro(jogos):
    """Filtro combinatório: soma entre 150 e 210, de 2 a 4 pares, no máximo 2 dezenas por linha e por coluna."""
    jogos = np.asarray(jogos)
    soma = (jogos + 1).sum(1)
    pares = PAR[jogos].sum(1)
    lin = np.stack([(LINHA[jogos] == r).sum(1) for r in range(6)], 1).max(1)
    col = np.stack([(COLUNA[jogos] == c).sum(1) for c in range(10)], 1).max(1)
    return (soma >= 150) & (soma <= 210) & (pares >= 2) & (pares <= 4) & (lin <= 2) & (col <= 2)


def montar_jogos(final, k=5, top=20, max_comum=3):
    """Entre as combinações dos `top` números mais bem ranqueados que passam no filtro, pega as de maior
    score conjunto (soma dos scores), exigindo no máximo `max_comum` dezenas em comum entre os jogos."""
    cand = np.sort(np.argsort(-final)[:top])
    jogos = np.array(list(combinations(cand, 6)))
    jogos = jogos[passa_filtro(jogos)]
    ordem = np.argsort(-final[jogos].sum(1))
    escolhidos = []
    for j in jogos[ordem]:
        if all(len(set(j) & set(e)) <= max_comum for e in escolhidos):
            escolhidos.append(j)
        if len(escolhidos) == k:
            break
    return [np.sort(e) for e in escolhidos]


# ----------------------------------------------------------------------------- backtest
def backtest(S, m, conc, n_bt, janela):
    n = len(m)
    linhas = []
    for t in range(n - n_bt, n):
        r = meta_modelo(S, m, t, janela)
        real = m[t].astype(bool)
        top6 = lambda s: np.argsort(-s)[:6]
        jogos = montar_jogos(r["final"])
        ac5 = [int(real[j].sum()) for j in jogos]
        linhas.append({"concurso": int(conc[t]), "real": " ".join(f"{x:02d}" for x in NUMS[real]),
                       "ensemble_top6": " ".join(f"{x + 1:02d}" for x in np.sort(top6(r["final"]))),
                       "ensemble": int(real[top6(r["final"])].sum()),
                       "soft_voting": int(real[top6(r["voto"])].sum()),
                       "stacking": int(real[top6(r["stack"])].sum()),
                       **{k: int(real[top6(S[t][:, i])].sum()) for i, k in enumerate(MODELOS)},
                       "melhor_dos_5_jogos": max(ac5), "soma_5_jogos": sum(ac5)})
    bt = pd.DataFrame(linhas)
    # Comparação com apostadores aleatórios: 20.000 simulados, 1 jogo (e 5 jogos) por concurso
    rng = np.random.default_rng(1)
    sim1 = rng.choice(7, size=(20000, n_bt), p=HIPER)
    sim5 = rng.choice(7, size=(20000, n_bt, 5), p=HIPER)
    cols = ["ensemble", "soft_voting", "stacking"] + MODELOS
    resumo = {c: {"media_acertos": round(float(bt[c].mean()), 3), "pct_acerto": round(float(bt[c].mean() / 6 * 100), 2),
                  "ternos": int((bt[c] == 3).sum()), "quadras": int((bt[c] == 4).sum()),
                  "quinas": int((bt[c] == 5).sum()), "senas": int((bt[c] == 6).sum()),
                  "pct_aleatorios_com_resultado_igual_ou_melhor":
                      round(float((sim1.mean(1) >= bt[c].mean() - 1e-9).mean() * 100), 1)} for c in cols}
    resumo["aleatorio_teorico"] = {"media_acertos": 0.6, "pct_acerto": 10.0,
                                   "quadras_esperadas": round(float(n_bt * HIPER[4]), 4),
                                   "quinas_esperadas": round(float(n_bt * HIPER[5]), 6),
                                   "senas_esperadas": round(float(n_bt * HIPER[6]), 8),
                                   "faixa_95pct_media": [round(float(np.percentile(sim1.mean(1), 2.5)), 2),
                                                         round(float(np.percentile(sim1.mean(1), 97.5)), 2)]}
    resumo["cinco_jogos_por_concurso"] = {
        "ensemble_media_por_jogo": round(float(bt.soma_5_jogos.mean() / 5), 3),
        "ensemble_melhor_acerto": int(bt.melhor_dos_5_jogos.max()),
        "ensemble_quadras_ou_mais": int((bt.melhor_dos_5_jogos >= 4).sum()),
        "aleatorio_media_por_jogo": 0.6,
        "aleatorio_quadras_esperadas": round(float(n_bt * 5 * HIPER[4:].sum()), 4),
        "pct_aleatorios_com_total_igual_ou_melhor":
            round(float((sim5.sum((1, 2)) >= bt.soma_5_jogos.sum()).mean() * 100), 1)}
    return bt, resumo


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(Path(__file__).parent / "data" / "megasena.csv"))
    ap.add_argument("--backtest", type=int, default=20, help="nº de concursos finais usados no backtest")
    ap.add_argument("--meta-janela", type=int, default=200, help="concursos usados para treinar o stacking")
    ap.add_argument("--mc", type=int, default=100_000, help="simulações de Monte Carlo por previsão")
    ap.add_argument("--retreino", type=int, default=10, help="re-treina XGBoost/LSTM a cada N concursos")
    ap.add_argument("--saida", default=str(Path(__file__).parent / "results"))
    a = ap.parse_args()

    conc, m = carregar(a.csv)
    n = len(m)
    out = Path(a.saida)
    out.mkdir(exist_ok=True)
    sufixo = "" if a.backtest == 20 else f"_bt{a.backtest}"
    f2 = lambda v: " ".join(f"{int(x):02d}" for x in v)
    print(f"Histórico: {n} concursos ({conc[0]} a {conc[-1]}). Próximo: {conc[-1] + 1}.\n")

    S, d = camada_base(m, n - a.backtest - a.meta_janela, a.mc, a.retreino)

    # ---------------- Etapa 1
    print("=== ETAPA 1: MODELOS BASE (para o próximo concurso) ===")
    print("Hipergeométrica (N=60, K=6, n=6): " + "; ".join(
        f"{nome} 1 em {1 / HIPER[k]:,.0f}".replace(",", ".") for k, nome in ((6, "sena"), (5, "quina"), (4, "quadra"))))
    z = d["m1"]["z"]
    print(f"M1: qui² histórico {d['m1']['chi2']:.1f} (esperado 54), encolhimento {d['m1']['encolhimento']:.2f}; "
          f"maiores desvios: " + ", ".join(f"{i + 1:02d} (z={z[i]:+.1f})" for i in np.argsort(-np.abs(z))[:6]))
    print("M2: " + "; ".join(f"janela {w}: qui²={v['chi2']} p={v['p']} entropia={v['entropia_rel']}"
                             for w, v in d["m2"]["janelas"].items()))
    mc = d["bruto"][:, 2]
    print(f"M3: {a.mc} sorteios simulados; mais frequentes: " +
          ", ".join(f"{i + 1:02d} ({mc[i] * 100:.2f}%)" for i in np.argsort(-mc)[:6]) + " (uniforme = 10%)")
    print(f"M4: |phi1| médio do ARIMA {np.abs(d['m4']['phi1']).mean():.3f}; números com pico de Fourier "
          f"significativo (p<0,05): {int((d['m4']['p_fisher'] < 0.05).sum())} de 60 (esperado por acaso: 3)")
    imp = sorted(d["importancia_xgb"].items(), key=lambda kv: -kv[1])[:5]
    print("M5: features mais usadas pelo XGBoost: " + ", ".join(f"{k} ({v:.2f})" for k, v in imp))

    # ---------------- Etapa 2
    r = meta_modelo(S, m, n, a.meta_janela)
    matriz = pd.DataFrame(S[n], columns=MODELOS, index=pd.Index(NUMS, name="numero"))
    matriz["soft_voting"], matriz["stacking_prob"], matriz["score_final"] = r["voto"], r["stack"], r["final"]
    matriz["rank"] = matriz.score_final.rank(ascending=False).astype(int)
    matriz.round(4).to_csv(out / f"ensemble_matriz{sufixo}.csv")
    print("\n=== ETAPA 2: COMITÊ ===")
    print("Pesos do stacking (coeficientes da logística): " +
          ", ".join(f"{k.split('_')[0]}={c:+.2f}" for k, c in zip(MODELOS, r["coef"])))
    print("Top 15 do ranking final (scores normalizados de 0 a 1):")
    print(matriz.sort_values("rank").head(15).round(3).to_string())
    rng = np.random.default_rng(5)
    unif = np.argsort(rng.random((200_000, 60)), axis=1)[:, :6]
    hist_j = np.argsort(-m, axis=1, kind="stable")[:, :6]
    pf, pfh = float(passa_filtro(unif).mean()), float(passa_filtro(hist_j).mean())
    print(f"Filtro combinatório: aprova {pf * 100:.1f}% de todas as combinações possíveis e "
          f"{pfh * 100:.1f}% dos sorteios históricos.")

    # ---------------- Etapa 3
    bt, resumo = backtest(S, m, conc, a.backtest, a.meta_janela)
    bt.to_csv(out / f"ensemble_backtest{sufixo}.csv", index=False)
    print(f"\n=== ETAPA 3: BACKTEST NOS ÚLTIMOS {a.backtest} CONCURSOS ===")
    print(bt[["concurso", "real", "ensemble_top6", "ensemble", "melhor_dos_5_jogos"]].to_string(index=False))
    print("\nAcertos médios por jogo (acaso = 0,60):")
    for k in ["ensemble", "soft_voting", "stacking"] + MODELOS:
        v = resumo[k]
        print(f"  {k:22s} {v['media_acertos']:.3f} ({v['pct_acerto']:.1f}%)  ternos {v['ternos']}  quadras {v['quadras']}  "
              f"quinas {v['quinas']}  senas {v['senas']}  | {v['pct_aleatorios_com_resultado_igual_ou_melhor']:.0f}% "
              f"dos apostadores aleatórios fazem igual ou melhor")
    al, c5 = resumo["aleatorio_teorico"], resumo["cinco_jogos_por_concurso"]
    print(f"  aleatório (teórico)    0.600 (10.0%)  quadras esperadas {al['quadras_esperadas']}  "
          f"faixa de 95% da média: {al['faixa_95pct_media']}")
    print(f"Com os 5 jogos do ensemble por concurso: média {c5['ensemble_media_por_jogo']} por jogo, melhor acerto "
          f"{c5['ensemble_melhor_acerto']}, quadras ou mais {c5['ensemble_quadras_ou_mais']}; "
          f"{c5['pct_aleatorios_com_total_igual_ou_melhor']}% dos aleatórios fazem igual ou melhor.")

    jogos = montar_jogos(r["final"])
    top15 = {k: set(np.argsort(-S[n][:, i])[:15]) for i, k in enumerate(MODELOS)}
    print(f"\n=== TOP 5 JOGOS PARA O CONCURSO {conc[-1] + 1} ===")
    jogos_out = []
    for g, j in enumerate(jogos, 1):
        apoio = {int(x + 1): [k.split("_")[0] for k in MODELOS if x in top15[k]] for x in j}
        info = {"jogo": [int(x + 1) for x in j], "score_conjunto": round(float(r["final"][j].sum()), 3),
                "soma": int((j + 1).sum()), "pares": int(PAR[j].sum()),
                "modelos_que_colocam_no_top15": apoio,
                "rank_final": {int(x + 1): int(matriz["rank"].iloc[x]) for x in j}}
        jogos_out.append(info)
        print(f"Jogo {g}: {f2(j + 1)}  | score {info['score_conjunto']}  soma {info['soma']}  pares {info['pares']}")
        for x in j:
            print(f"    {x + 1:02d}: rank {info['rank_final'][int(x + 1)]:2d}, score {r['final'][x]:.2f}, "
                  f"apoio: {', '.join(apoio[int(x + 1)]) or 'nenhum modelo no top 15'}")

    (out / f"ensemble{sufixo}.json").write_text(json.dumps({
        "proximo_concurso": int(conc[-1] + 1), "concursos_no_historico": n,
        "hipergeometrica": {str(k): float(HIPER[k]) for k in range(7)},
        "pesos_stacking": dict(zip(MODELOS, map(float, r["coef"]))),
        "filtro_aprova_pct": {"todas_as_combinacoes": round(pf * 100, 2), "sorteios_historicos": round(pfh * 100, 2)},
        "backtest": resumo, "jogos": jogos_out}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
