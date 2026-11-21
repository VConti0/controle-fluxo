"""Trabalhador da busca física distribuída: sorteios físicos inteiros numa faixa própria de sementes.

Cada trabalhador (uma sessão/máquina) recebe um número e simula sorteios no emulador físico (emulador.py)
com as sementes 1.000.000.000 + número * 100.000.000 em diante, sem repetir sementes de outro trabalhador.
Procura um sorteio com as mesmas 6 dezenas do concurso-alvo (em qualquer ordem). Quando acha, grava a
semente (que permite refazer o sorteio e recuperar posições e condições da simulação) e termina.

Progresso em results/trabalhador_<número>.json (retoma de onde parou).

Uso: python3 -u fisica_trabalhador.py <número> [minutos] [concurso_alvo]
"""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

import emulador
from common import RESULTS, load

LOTE = 2_000


def main():
    num = int(sys.argv[1])
    minutos = float(sys.argv[2]) if len(sys.argv) > 2 else 110
    concurso = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    arq = RESULTS / f"trabalhador_{num}.json"
    alvo = load()[[f"d{i}" for i in range(1, 7)]].values[concurso - 1]
    est = json.loads(arq.read_text()) if arq.exists() else {
        "trabalhador": num, "concurso_alvo": concurso, "proxima_semente": 1_000_000_000 + num * 100_000_000,
        "sorteios": 0, "segundos": 0, "acertos": [0] * 7, "quinas": [], "sena": None}
    if est["sena"]:
        print("SENA", json.dumps(est["sena"]), flush=True)
        return
    emulador.sorteio(0)
    fim = time.time() + minutos * 60
    with Pool() as pool:
        while time.time() < fim:
            t0 = time.time()
            sementes = range(est["proxima_semente"], est["proxima_semente"] + LOTE)
            res = np.array(pool.map(emulador.sorteio, sementes, chunksize=50))
            h = np.isin(res, alvo).sum(1)
            est["acertos"] = [a + int((h == k).sum()) for k, a in enumerate(est["acertos"])]
            for i in np.flatnonzero(h == 5):
                est["quinas"].append({"semente": int(sementes[i]), "ordem_de_saida": [int(x) for x in res[i]]})
            est["sorteios"] += LOTE
            est["proxima_semente"] += LOTE
            est["segundos"] += round(time.time() - t0)
            if h.max() == 6:
                i = int(h.argmax())
                est["sena"] = {"trabalhador": num, "concurso": concurso, "semente": int(sementes[i]),
                               "ordem_de_saida": [int(x) for x in res[i]]}
            arq.write_text(json.dumps(est, indent=1))
            print(f"sorteios {est['sorteios']} melhor {int(h.max())} acertos {est['acertos']} {round(time.time() - t0)}s", flush=True)
            if est["sena"]:
                print("SENA", json.dumps(est["sena"]), flush=True)
                return


if __name__ == "__main__":
    main()
