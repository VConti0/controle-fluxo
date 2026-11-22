"""Quatro palpites para o próximo concurso, um por fonte e um combinado.

1. estatístico: probabilidades do modelo combinado (combinacoes.py);
2. físico: frequência de cada bola nos sorteios do emulador (emulador_5000.csv + fisica_frequencia.npy);
3. viés real: frequência das dezenas desde o concurso 1851 (início da anomalia);
4. combinado: média dos três, cada um padronizado (escore z).
"""
import json

import numpy as np
import pandas as pd

from common import RESULTS, draws_matrix, load


def z(v):
    return (v - v.mean()) / v.std()


def top6(v):
    return sorted(int(i + 1) for i in np.argsort(-v)[:6])


def main():
    df = load()
    m = draws_matrix(df)
    c = json.loads((RESULTS / "combinacoes.json").read_text())
    est = np.array([c["probabilidade_por_numero_pct"][str(i)] for i in range(1, 61)])
    emu = pd.read_csv(RESULTS / "emulador_5000.csv")[[f"o{i}" for i in range(1, 7)]].values
    novo = np.load(RESULTS / "fisica_frequencia.npy")
    todos = np.concatenate([emu, novo])
    fis = np.bincount(todos.ravel(), minlength=61)[1:] / len(todos) * 100
    f_a, f_b = (np.bincount(x.ravel(), minlength=61)[1:] / len(x) for x in (emu, novo))
    real = m[1850:].mean(0) * 100
    comb = (z(est) + z(fis) + z(real)) / 3
    out = {"concurso": int(df.concurso.iloc[-1]) + 1,
           "sorteios_fisicos_na_amostra": int(len(todos)),
           "correlacao_entre_as_duas_amostras_fisicas": round(float(np.corrcoef(f_a, f_b)[0, 1]), 3),
           "correlacoes_entre_fontes": {"estatistico_x_fisico": round(float(np.corrcoef(est, fis)[0, 1]), 3),
                                        "estatistico_x_vies_real": round(float(np.corrcoef(est, real)[0, 1]), 3),
                                        "fisico_x_vies_real": round(float(np.corrcoef(fis, real)[0, 1]), 3)},
           "palpites": {"1_estatistico": top6(est), "2_fisico": top6(fis), "3_vies_real_desde_2016": top6(real),
                        "4_combinado": top6(comb)},
           "pct_por_numero": {"estatistico": {int(i + 1): round(float(est[i]), 2) for i in np.argsort(-est)[:10]},
                              "fisico": {int(i + 1): round(float(fis[i]), 2) for i in np.argsort(-fis)[:10]},
                              "vies_real": {int(i + 1): round(float(real[i]), 2) for i in np.argsort(-real)[:10]},
                              "combinado_z": {int(i + 1): round(float(comb[i]), 2) for i in np.argsort(-comb)[:10]}}}
    (RESULTS / "palpites_3089.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
