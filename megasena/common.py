"""Utilidades compartilhadas: carga dos dados e métricas de avaliação."""
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "megasena.csv"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

N_NUM = 60
N_PICK = 6
TEST_SIZE = 500  # últimos 500 concursos usados como teste fora da amostra


def load():
    df = pd.read_csv(DATA)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    return df


def draws_matrix(df):
    """Matriz binária (n_concursos x 60): 1 se o número saiu no concurso."""
    m = np.zeros((len(df), N_NUM), dtype=np.int8)
    nums = df[[f"d{i}" for i in range(1, 7)]].values - 1
    m[np.arange(len(df))[:, None], nums] = 1
    return m


def draw_order(df):
    return df[[f"o{i}" for i in range(1, 7)]].values  # 1..60, na ordem em que saíram


# Distribuição hipergeométrica de acertos para um jogo de 6 dezenas escolhido ao acaso.
HITS_PMF = np.array([comb(6, k) * comb(54, 6 - k) / comb(60, 6) for k in range(7)])
RANDOM_MEAN_HITS = float((np.arange(7) * HITS_PMF).sum())  # = 0.6
RANDOM_VAR_HITS = float(((np.arange(7) - RANDOM_MEAN_HITS) ** 2 * HITS_PMF).sum())


def summarize_hits(hits, name):
    """Compara acertos médios com o acaso: z-score e p-valor bilateral (aprox. normal)."""
    from math import erf, sqrt

    hits = np.asarray(hits)
    n = len(hits)
    mean = hits.mean()
    se = sqrt(RANDOM_VAR_HITS / n)
    z = (mean - RANDOM_MEAN_HITS) / se
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
    dist = {k: int((hits == k).sum()) for k in range(7)}
    return {"modelo": name, "n_testes": n, "acertos_medios": round(float(mean), 4),
            "acaso_esperado": round(RANDOM_MEAN_HITS, 4), "z": round(z, 3), "p_valor": round(p, 4),
            "distribuicao_acertos": dist, "quadras_ou_mais": int((hits >= 4).sum())}
