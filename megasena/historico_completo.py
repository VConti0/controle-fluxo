"""Aplica o modelo de combinacoes.py do 2º ao último concurso, sempre só com informação anterior.

Em cada concurso t:
  * calcula as fontes (comitê M1-M5, viés em 3 escalas, emulador) com os concursos < t;
  * ajusta os pesos na janela dos até 200 concursos anteriores (refeito a cada 10);
  * aposta nas 6 dezenas de maior probabilidade e mede: acertos, e em que percentil das 50 milhões de
    combinações o resultado real ficou (100 = o modelo colocou o real em 1º; 50 = meio da lista).
Enquanto não há histórico suficiente, as fontes que ainda não podem ser calculadas ficam neutras
(comitê a partir do concurso 31, XGBoost/LSTM a partir do 151, pesos a partir do 21).
"""
import json
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from combinacoes import FONTES, norm, vies
from common import RESULTS, draws_matrix, load
from ensemble import M5, features_ml, m1_hipergeometrica, m2_auditoria, m3_monte_carlo, m4_arima_fft, minmax

JANELA, MC, RETREINO = 200, 20_000, 50


def main():
    df = load()
    m = draws_matrix(df)
    n = len(m)
    emu_tab = pd.read_csv(RESULTS / "emulador_5000.csv")
    emu = norm(np.bincount(emu_tab[[f"d{i}" for i in range(1, 7)]].values.ravel(), minlength=61)[1:] / len(emu_tab))
    rng = np.random.default_rng(2026)
    amostra = np.argsort(rng.random((20_000, 60)), axis=1)[:, :6]
    m5 = M5(m, features_ml(m))
    neutro = np.full(60, 0.5)
    X, linhas, modelo, m5_ok = {}, [], None, False
    probs = np.full((n, 60), 0.1)

    for t in range(1, n):
        hist = m[:t]
        if t >= 30:
            s = [minmax(m1_hipergeometrica(hist)[0]), minmax(m2_auditoria(hist)[0]),
                 minmax(m3_monte_carlo(hist, rng, MC)[0]), minmax(m4_arima_fft(hist)[0])]
        else:
            s = [neutro] * 4
        if t >= 150:
            if (t - 150) % RETREINO == 0:
                m5.treinar(t)
                m5_ok = True
            s.append(minmax(m5.prever(t)[0]) if m5_ok else neutro)
        else:
            s.append(neutro)
        X[t] = np.c_[np.column_stack(s), norm(vies(hist, 100)), norm(vies(hist, 300)), norm(vies(hist, 1000)), emu]

        if t >= 21 and (t - 21) % 10 == 0:
            ini = max(1, t - JANELA)
            modelo = LogisticRegression(C=1.0, max_iter=2000).fit(
                np.concatenate([X[u] for u in range(ini, t)]), m[ini:t].reshape(-1))
        p = modelo.predict_proba(X[t])[:, 1] if modelo is not None else rng.random(60) * 1e-6 + 0.1
        probs[t] = p
        lg = np.log(p / (1 - p))
        ordem24 = np.lexsort((rng.random(60), -p))[:24]
        aposta = np.sort(ordem24[:6])
        real = m[t].astype(bool)
        jogos4 = [np.sort(ordem24[k * 6:(k + 1) * 6]) for k in range(4)]   # 4 jogos sem dezena repetida
        ac4 = [int(real[j].sum()) for j in jogos4]
        linhas.append({"concurso": int(df.concurso[t]), "ano": int(df.data[t].year),
                       "aposta": " ".join(f"{x + 1:02d}" for x in aposta),
                       "real": " ".join(f"{x + 1:02d}" for x in np.flatnonzero(real)),
                       "acertos": int(real[aposta].sum()),
                       **{f"jogo{k + 1}": " ".join(f"{x + 1:02d}" for x in jogos4[k]) for k in range(4)},
                       **{f"acertos_jogo{k + 1}": ac4[k] for k in range(4)},
                       "melhor_dos_4": max(ac4), "soma_dos_4": sum(ac4),
                       "percentil_do_real": round(float((lg[amostra].sum(1) < lg[real].sum()).mean() * 100), 2)})
        if t % 250 == 0:
            print(f"concurso {t + 1}", file=sys.stderr, flush=True)

    np.save(RESULTS / "historico_probabilidades.npy", probs.astype(np.float32))
    d = pd.DataFrame(linhas)
    d.to_csv(RESULTS / "historico_completo.csv", index=False)
    g = d.groupby("ano")
    ano = pd.DataFrame({"concursos": g.size(), "acertos_medios": g.acertos.mean().round(3),
                        "pct_acerto": (g.acertos.mean() / 6 * 100).round(2),
                        "melhor_acerto": g.acertos.max(),
                        "real_nos_10pct_melhores": g.percentil_do_real.apply(lambda v: int((v >= 90).sum())),
                        "percentil_medio_do_real": g.percentil_do_real.mean().round(1)})
    ano.to_csv(RESULTS / "historico_completo_por_ano.csv")
    k = int((d.percentil_do_real >= 90).sum())
    out = {"concursos_previstos": len(d), "acertos_medios": round(float(d.acertos.mean()), 4),
           "pct_acerto": round(float(d.acertos.mean() / 6 * 100), 2), "referencia_acertos": 0.6,
           "distribuicao_de_acertos": {str(h): int((d.acertos == h).sum()) for h in range(7)},
           "esperado_ao_acaso": {"0": round(len(d) * .5159), "1": round(len(d) * .3790), "2": round(len(d) * .0948),
                                 "3": round(len(d) * .00991, 1), "4": round(len(d) * .000429, 2)},
           "real_nos_10pct_melhores": k, "pct": round(k / len(d) * 100, 2),
           "percentil_medio_do_real": round(float(d.percentil_do_real.mean()), 2),
           "melhores_concursos": d.nlargest(8, "acertos")[["concurso", "aposta", "real", "acertos"]].to_dict("records")}
    ano4 = pd.DataFrame({"concursos": g.size(), "jogos": g.size() * 4,
                         "acertos_por_jogo": (g.soma_dos_4.mean() / 4).round(3),
                         "pct_acerto": (g.soma_dos_4.mean() / 24 * 100).round(2),
                         "dezenas_cobertas_por_concurso": g.soma_dos_4.mean().round(2),
                         "ternos": g.melhor_dos_4.apply(lambda v: int((v == 3).sum())),
                         "quadras": g.melhor_dos_4.apply(lambda v: int((v == 4).sum())),
                         "quinas": g.melhor_dos_4.apply(lambda v: int((v == 5).sum())),
                         "senas": g.melhor_dos_4.apply(lambda v: int((v == 6).sum())),
                         "melhor_acerto": g.melhor_dos_4.max()})
    ano4.to_csv(RESULTS / "historico_4_jogos_por_ano.csv")
    todos = d[[f"acertos_jogo{k}" for k in range(1, 5)]].values.ravel()
    nj = len(todos)
    out["quatro_jogos_por_concurso"] = {
        "jogos": nj, "acertos_por_jogo": round(float(todos.mean()), 4),
        "dezenas_cobertas_por_concurso": round(float(d.soma_dos_4.mean()), 3), "referencia_cobertas": 2.4,
        "distribuicao_por_jogo": {str(h): int((todos == h).sum()) for h in range(7)},
        "esperado_ao_acaso": {"3": round(nj * .00991, 1), "4": round(nj * .000429, 2), "5": round(nj * 6.47e-6, 3)},
        "por_posicao_do_jogo": {f"jogo{k}": round(float(d[f"acertos_jogo{k}"].mean()), 3) for k in range(1, 5)},
        "concursos_com_quadra_ou_mais": d[d.melhor_dos_4 >= 4][["concurso", "real", "jogo1", "jogo2", "jogo3", "jogo4",
                                                                 "melhor_dos_4"]].to_dict("records")}
    print(ano4.to_string())
    (RESULTS / "historico_completo.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    pd.set_option("display.width", 200)
    print(ano.to_string())
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
