"""Compara os 5.000 sorteios do emulador físico com os sorteios reais da Mega-Sena."""
import json

import numpy as np
import pandas as pd
from scipy import stats

from common import RESULTS, draw_order, draws_matrix, load

NUMS = np.arange(1, 61)
LINHA, COLUNA = (NUMS - 1) // 10, (NUMS - 1) % 10


def matriz(dez):
    m = np.zeros((len(dez), 60))
    m[np.arange(len(dez))[:, None], dez - 1] = 1
    return m


def perfil(m, ordem):
    n = len(m)
    dez = np.sort(np.argsort(-m, axis=1, kind="stable")[:, :6], 1) + 1
    freq = m.sum(0)
    qui = float(((freq - n * 0.1) ** 2 / (n * 0.1)).sum())
    soma = dez.sum(1)
    c1 = np.bincount(ordem[:, 0], minlength=61)[1:]
    c6 = np.bincount(ordem[:, 5], minlength=61)[1:]
    return {
        "sorteios": n,
        "qui2_frequencias": round(qui, 1), "p_qui2": round(float(stats.chi2.sf(qui * 59 / 54, 59)), 5),
        "freq_max_pct": [int(freq.argmax() + 1), round(float(freq.max() / n * 100), 2)],
        "freq_min_pct": [int(freq.argmin() + 1), round(float(freq.min() / n * 100), 2)],
        "soma_media": round(float(soma.mean()), 1), "soma_dp": round(float(soma.std()), 1),
        "pares_media": round(float((dez % 2 == 0).sum(1).mean()), 3),
        "ate_31_media": round(float((dez <= 31).sum(1).mean()), 3),
        "consecutivas_media": round(float((np.diff(dez, axis=1) == 1).sum(1).mean()), 3),
        "max_mesma_linha_media": round(float(np.mean([np.bincount(LINHA[d - 1], minlength=6).max() for d in dez])), 3),
        "max_mesma_coluna_media": round(float(np.mean([np.bincount(COLUNA[d - 1], minlength=10).max() for d in dez])), 3),
        "repeticao_do_sorteio_anterior": round(float((m[1:] * m[:-1]).sum(1).mean()), 3),
        "primeira_bola_p_uniforme": round(float(stats.chisquare(c1)[1]), 5),
        "sexta_bola_p_uniforme": round(float(stats.chisquare(c6)[1]), 5),
    }, freq / n


def main():
    df = load()
    real_m, real_o = draws_matrix(df).astype(float), draw_order(df)
    emu = pd.read_csv(RESULTS / "emulador_5000.csv")
    emu_o = emu[[f"o{i}" for i in range(1, 7)]].values
    emu_m = matriz(emu_o)
    massa = pd.read_csv(RESULTS / "emulador_massas.csv").massa_g.values

    pr, fr = perfil(real_m, real_o)
    pe, fe = perfil(emu_m, emu_o)
    teor = {"qui2_frequencias": 54, "soma_media": 183.0, "soma_dp": 40.6, "pares_media": 3.0, "ate_31_media": 3.1,
            "repeticao_do_sorteio_anterior": 0.6}
    out = {"real": pr, "emulador": pe, "teorico_sorteio_uniforme": teor}

    # frequências: emulador x real (inteiro e período da anomalia)
    r_all, p_all = stats.pearsonr(fe, fr)
    f_anom = real_m[1850:].mean(0)
    r_an, p_an = stats.pearsonr(fe, f_anom)
    out["frequencia_emulador_x_real"] = {"correlacao_historico_inteiro": round(float(r_all), 3), "p": round(float(p_all), 3),
                                         "correlacao_periodo_2016_em_diante": round(float(r_an), 3), "p_": round(float(p_an), 3)}

    # perfil de viés do emulador: massa e posição de carga x frequência
    r_m, p_m = stats.pearsonr(massa, fe)
    r_n, p_n = stats.pearsonr(NUMS, fe)
    out["vies_do_emulador"] = {
        "massa_x_frequencia": {"correlacao": round(float(r_m), 3), "p": round(float(p_m), 4),
                               "massa_min_max_g": [round(float(massa.min()), 3), round(float(massa.max()), 3)]},
        "numero_(posicao_de_carga)_x_frequencia": {"correlacao": round(float(r_n), 3), "p": round(float(p_n), 4)},
        "mais_sorteados": [(int(i + 1), round(float(fe[i] * 100), 2)) for i in np.argsort(-fe)[:8]],
        "menos_sorteados": [(int(i + 1), round(float(fe[i] * 100), 2)) for i in np.argsort(fe)[:8]],
        "frequencia_por_dezena_do_volante_pct": {f"{d * 10 + 1:02d}-{d * 10 + 10:02d}": round(float(fe[d * 10:d * 10 + 10].mean() * 100), 2)
                                                 for d in range(6)},
        "metade_1_x_metade_2": round(float(np.corrcoef(emu_m[:2500].mean(0), emu_m[2500:].mean(0))[0, 1]), 3)}
    # ordem de saída: a posição de carga influencia qual bola sai primeiro?
    c1 = np.bincount(emu_o[:, 0], minlength=61)[1:] / len(emu_o) * 100
    out["emulador_primeira_bola"] = {"mais_frequentes_pct": [(int(i + 1), round(float(c1[i]), 2)) for i in np.argsort(-c1)[:6]],
                                     "esperado_pct": 1.67}

    (RESULTS / "comparar_emulador.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
