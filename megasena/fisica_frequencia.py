"""Frequência de cada bola no emulador físico: simula sorteios inteiros por um tempo e guarda todos.

Uso: python3 -u fisica_frequencia.py [minutos]   ->  results/fisica_frequencia.npy (ordem de saída de cada sorteio)
"""
import sys
import time
from multiprocessing import Pool

import numpy as np

import emulador
from common import RESULTS

ARQ = RESULTS / "fisica_frequencia.npy"


def main():
    minutos = float(sys.argv[1]) if len(sys.argv) > 1 else 35
    feitos = np.load(ARQ) if ARQ.exists() else np.zeros((0, 6), np.int16)
    emulador.sorteio(0)
    fim = time.time() + minutos * 60
    with Pool() as pool:
        while time.time() < fim:
            s0 = 500_000_000 + len(feitos)
            res = np.array(pool.map(emulador.sorteio, range(s0, s0 + 2000), chunksize=50), np.int16)
            feitos = np.concatenate([feitos, res])
            np.save(ARQ, feitos)
            print(len(feitos), flush=True)


if __name__ == "__main__":
    main()
