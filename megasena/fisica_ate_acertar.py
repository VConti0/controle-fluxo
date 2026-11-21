"""Emulador FÍSICO rodando até reproduzir um concurso real (mesmas 6 dezenas, em qualquer ordem).

Cada sorteio é uma simulação completa do globo (emulador.py): 60 bolas de 66 g, colisões, atrito, rotação,
pás e ar. O estado inicial de cada sorteio é definido pela semente, então qualquer sorteio pode ser refeito
depois para ver a posição de todas as bolas.

Grava o progresso em results/fisica_concurso<N>.json a cada lote: quantos sorteios, distribuição de acertos
e as sementes dos sorteios com 4 ou mais dezenas certas. Retoma de onde parou.

Uso: python3 fisica_ate_acertar.py [concurso] [minutos]
"""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

import emulador
from common import RESULTS, load

LOTE = 4000


def main():
    conc = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    minutos = float(sys.argv[2]) if len(sys.argv) > 2 else 110
    df = load()
    linha = df[df.concurso == conc].iloc[0]
    alvo = sorted(int(linha[f"d{i}"]) for i in range(1, 7))
    arq = RESULTS / f"fisica_concurso{conc}.json"
    est = json.loads(arq.read_text()) if arq.exists() else {
        "concurso": conc, "alvo": alvo, "sorteios": 0, "proxima_semente": 1_000_000, "segundos": 0,
        "acertos": [0] * 7, "proximos": []}
    emulador.sorteio(0)
    fim = time.time() + minutos * 60
    with Pool(4) as pool:
        while time.time() < fim and est["acertos"][6] == 0:
            t0 = time.time()
            sementes = range(est["proxima_semente"], est["proxima_semente"] + LOTE)
            res = np.array(pool.map(emulador.sorteio, sementes, chunksize=50))
            h = np.isin(res, alvo).sum(1)
            for k in range(7):
                est["acertos"][k] += int((h == k).sum())
            for i in np.flatnonzero(h >= 4):
                est["proximos"].append({"semente": int(sementes[i]), "acertos": int(h[i]),
                                        "ordem_de_saida": [int(x) for x in res[i]]})
            est["sorteios"] += LOTE
            est["proxima_semente"] += LOTE
            est["segundos"] += round(time.time() - t0)
            arq.write_text(json.dumps(est, indent=1))
            print(est["sorteios"], est["acertos"], flush=True)


if __name__ == "__main__":
    main()
