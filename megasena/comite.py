"""Números usados no debate do comitê: hipergeométrica, auditoria (qui², entropia, runs),
Monte Carlo / entropia máxima e séries temporais (ACF, Ljung-Box, ARIMA, FFT)."""
import json
import warnings
from math import comb, log2

import numpy as np
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA

from common import RESULTS, draws_matrix, load

warnings.filterwarnings("ignore")
df = load(); m = draws_matrix(df); n = len(m)
rng = np.random.default_rng(123)
out = {"concursos": n}

# 1) Hipergeométrica N=60, K=6, n=6
T = comb(60, 6)
out["hipergeometrica"] = {str(k): {"combinacoes": comb(6, k) * comb(54, 6 - k),
                                   "prob": comb(6, k) * comb(54, 6 - k) / T,
                                   "um_em": round(T / (comb(6, k) * comb(54, 6 - k)), 1)} for k in range(7)}
out["hipergeometrica"]["total_combinacoes"] = T
out["hipergeometrica"]["media_acertos"] = 0.6

# 2) Auditoria
freq = m.sum(0)
chi2, p_chi = stats.chisquare(freq)
pr = freq / freq.sum()
H = float(-(pr * np.log2(pr)).sum())
def runs_z(b):
    b = np.asarray(b, bool); n1, n0 = b.sum(), (~b).sum()
    r = 1 + (b[1:] != b[:-1]).sum()
    mu = 2 * n1 * n0 / (n1 + n0) + 1
    var = 2 * n1 * n0 * (2 * n1 * n0 - n1 - n0) / ((n1 + n0) ** 2 * (n1 + n0 - 1))
    return (r - mu) / np.sqrt(var)
zs = np.array([runs_z(m[:, j]) for j in range(60)])
soma = (m @ np.arange(1, 61)).astype(float)
z_soma = runs_z(soma > np.median(soma))
pares = m[:, 1::2].sum(1)
z_par = runs_z(pares >= 3.5) if False else runs_z(pares > 3)
out["auditoria"] = {
    "qui2": round(float(chi2), 2), "gl": 59, "p": round(float(p_chi), 4),
    "freq_max": [int(freq.argmax() + 1), int(freq.max())], "freq_min": [int(freq.argmin() + 1), int(freq.min())],
    "entropia_shannon_bits": round(H, 5), "entropia_maxima_bits": round(log2(60), 5),
    "eficiencia_entropia": round(H / log2(60), 6),
    "runs_por_numero": {"rejeitados_5pct": int((np.abs(zs) > 1.96).sum()), "esperado_por_acaso": 3.0,
                        "z_medio": round(float(zs.mean()), 3), "z_dp": round(float(zs.std()), 3),
                        "maior_|z|": [int(np.abs(zs).argmax() + 1), round(float(zs[np.abs(zs).argmax()]), 2)]},
    "runs_soma_acima_mediana": {"z": round(float(z_soma), 3), "p": round(float(2 * stats.norm.sf(abs(z_soma))), 4)},
    "runs_mais_de_3_pares": {"z": round(float(z_par), 3), "p": round(float(2 * stats.norm.sf(abs(z_par))), 4)},
}

# 3) Monte Carlo: 5000 históricos simulados de n concursos, sorteio uniforme sem reposição
S = 5000
sim_chi, sim_max, sim_min, sim_H = [], [], [], []
for _ in range(S // 50):
    picks = np.argsort(rng.random((50, n, 60)), axis=2)[:, :, :6]
    f = np.stack([np.bincount(p.ravel(), minlength=60) for p in picks])
    e = n * 6 / 60
    sim_chi += list(((f - e) ** 2 / e).sum(1)); sim_max += list(f.max(1)); sim_min += list(f.min(1))
    q = f / f.sum(1, keepdims=True); sim_H += list(-(q * np.log2(q)).sum(1))
sim_chi, sim_max, sim_min, sim_H = map(np.array, (sim_chi, sim_max, sim_min, sim_H))
# convergência: desvio máximo relativo da frequência conforme o nº de concursos cresce
conv = {}
for k in (100, 500, 1000, 2000, n):
    real = np.abs(m[:k].mean(0) - 0.1).max() / 0.1
    conv[str(k)] = {"real_desvio_max_pct": round(float(real * 100), 1),
                    "teorico_dp_pct": round(float(np.sqrt(0.1 * 0.9 / k) / 0.1 * 100), 1)}
out["monte_carlo"] = {
    "simulacoes": S, "entropia_max_por_sorteio_bits": round(log2(T), 3),
    "qui2_simulado": {"media": round(float(sim_chi.mean()), 2), "p95": round(float(np.percentile(sim_chi, 95)), 2),
                      "p99": round(float(np.percentile(sim_chi, 99)), 2),
                      "p_empirico_do_real": round(float((sim_chi >= chi2).mean()), 4)},
    "freq_maxima_simulada": {"media": round(float(sim_max.mean()), 1), "p95": int(np.percentile(sim_max, 95)),
                             "prob_max>=real": round(float((sim_max >= freq.max()).mean()), 4)},
    "freq_minima_simulada": {"media": round(float(sim_min.mean()), 1), "p5": int(np.percentile(sim_min, 5)),
                             "prob_min<=real": round(float((sim_min <= freq.min()).mean()), 4)},
    "entropia_simulada": {"media": round(float(sim_H.mean()), 5), "p5": round(float(np.percentile(sim_H, 5)), 5),
                          "prob_H<=real": round(float((sim_H <= H).mean()), 4)},
    "convergencia": conv,
}

# 4) Séries temporais sobre a soma das dezenas (e ACF por número)
x = soma - soma.mean()
lb = acorr_ljungbox(x, lags=[1, 5, 10, 20, 50])
acf = np.array([np.corrcoef(x[:-k], x[k:])[0, 1] for k in range(1, 51)])
aics = {}
for order in [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1), (2, 0, 2)]:
    r = ARIMA(soma, order=order).fit()
    aics[str(order)] = {"aic": round(float(r.aic), 2), "bic": round(float(r.bic), 2)}
ar1 = ARIMA(soma, order=(1, 0, 0)).fit()
P = np.abs(np.fft.rfft(x)[1:]) ** 2
g = P.max() / P.sum(); K = len(P)
p_fisher = min(1.0, K * (1 - g) ** (K - 1))
# ACF por número: fração de |r| fora da banda de 95% em 60 números x 20 lags
banda = 1.96 / np.sqrt(n)
fora = np.mean([abs(np.corrcoef(m[:-k, j], m[k:, j])[0, 1]) > banda for j in range(60) for k in range(1, 21)])
out["series_temporais"] = {
    "ljung_box_p": {str(int(k)): round(float(v), 4) for k, v in zip(lb.index, lb.lb_pvalue)},
    "acf_soma": {"lag1": round(float(acf[0]), 4), "max_abs_50_lags": round(float(np.abs(acf).max()), 4),
                 "banda_95pct": round(float(banda), 4), "lags_fora_da_banda": int((np.abs(acf) > banda).sum()),
                 "esperado_fora": 2.5},
    "arima_soma": aics, "ar1_coef": round(float(ar1.params[1]), 4), "ar1_p": round(float(ar1.pvalues[1]), 4),
    "fft": {"maior_pico_periodo_concursos": round(float(n / (P.argmax() + 1)), 2),
            "fisher_g": round(float(g), 5), "p_fisher": round(float(p_fisher), 4)},
    "acf_por_numero_fracao_fora_banda": round(float(fora), 4), "esperado": 0.05,
}
(RESULTS / "comite.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps(out, indent=1, ensure_ascii=False))
