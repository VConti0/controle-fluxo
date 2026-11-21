"""Busca física em sequência, em rodadas de 10.000 sorteios.

Cada rodada simula 10.000 sorteios no emulador físico (emulador.py: globo, 60 bolas de 66 g, colisões,
atrito, rotação, pás, ar). O alvo começa no concurso 1. Se algum dos 10.000 sorteios da rodada der as
mesmas 6 dezenas do concurso-alvo (em qualquer ordem), o alvo passa para o concurso seguinte; a busca
segue assim até o último concurso real e depois continua gerando os próximos até o 4000.

Progresso gravado a cada rodada em results/fisica_sequencia.json (retoma de onde parou). Para cada
sorteio com 4 ou mais dezenas do alvo fica guardada a semente, que permite refazer o sorteio e ver a
posição de todas as bolas.

Uso: python3 fisica_sequencia.py [minutos]
"""
import json
import sys
import time
from multiprocessing import Pool

import numpy as np

import emulador
from common import RESULTS, load

RODADA = 10_000
ARQ = RESULTS / "fisica_sequencia.json"


def main():
    minutos = float(sys.argv[1]) if len(sys.argv) > 1 else 110
    df = load()
    dez = df[[f"d{i}" for i in range(1, 7)]].values
    est = json.loads(ARQ.read_text()) if ARQ.exists() else {
        "concurso_alvo": 1, "rodadas": 0, "sorteios": 0, "proxima_semente": 10_000_000, "segundos": 0,
        "concursos_reproduzidos": [], "rodadas_no_alvo_atual": 0, "acertos_no_alvo_atual": [0] * 7,
        "proximos_do_alvo_atual": [], "historico_de_rodadas": []}
    emulador.sorteio(0)
    fim = time.time() + minutos * 60
    with Pool(4) as pool:
        while time.time() < fim and est["concurso_alvo"] <= len(dez):
            t0 = time.time()
            alvo = dez[est["concurso_alvo"] - 1]
            sementes = range(est["proxima_semente"], est["proxima_semente"] + RODADA)
            res = np.array(pool.map(emulador.sorteio, sementes, chunksize=100))
            h = np.isin(res, alvo).sum(1)
            dist = [int((h == k).sum()) for k in range(7)]
            est["acertos_no_alvo_atual"] = [a + b for a, b in zip(est["acertos_no_alvo_atual"], dist)]
            for i in np.flatnonzero(h >= 4):
                est["proximos_do_alvo_atual"].append({"semente": int(sementes[i]), "acertos": int(h[i]),
                                                      "ordem_de_saida": [int(x) for x in res[i]]})
            est["rodadas"] += 1
            est["rodadas_no_alvo_atual"] += 1
            est["sorteios"] += RODADA
            est["proxima_semente"] += RODADA
            est["segundos"] += round(time.time() - t0)
            est["historico_de_rodadas"].append({"rodada": est["rodadas"], "alvo": int(est["concurso_alvo"]),
                                                "melhor_acerto": int(h.max()), "distribuicao": dist})
            if h.max() == 6:
                i = int(h.argmax())
                est["concursos_reproduzidos"].append({"concurso": int(est["concurso_alvo"]), "semente": int(sementes[i]),
                                                      "ordem_de_saida": [int(x) for x in res[i]],
                                                      "rodadas_ate_acertar": est["rodadas_no_alvo_atual"]})
                est["concurso_alvo"] += 1
                est["rodadas_no_alvo_atual"], est["acertos_no_alvo_atual"], est["proximos_do_alvo_atual"] = 0, [0] * 7, []
            ARQ.write_text(json.dumps(est, indent=1))
            print(f"rodada {est['rodadas']} alvo {est['concurso_alvo']} melhor {int(h.max())} {dist} {round(time.time() - t0)}s", flush=True)


if __name__ == "__main__":
    main()
