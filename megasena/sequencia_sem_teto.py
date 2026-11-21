"""Sequência com reinício, sem teto: roda até acertar todos os concursos em sequência.
Registra o progresso em results/sequencia_sem_teto.json a cada bloco de 2 bilhões de tentativas."""
import json
import time

import numpy as np

from common import RESULTS, draws_matrix, load
from sequencia_com_reinicio import roda

BLOCO = 2_000_000_000
ARQ = RESULTS / "sequencia_sem_teto.json"


def main():
    m = draws_matrix(load()).astype(np.int64)
    P = np.load(RESULTS / "historico_probabilidades.npy").astype(np.float64)
    W = P / (1 - P)
    est = json.loads(ARQ.read_text()) if ARQ.exists() else {"tentativas": 0, "chegou": [0] * 8, "blocos": 0, "segundos": 0}
    while True:
        t0 = time.time()
        chegou, completas = roda(W, m, BLOCO // 4, est["blocos"] + 1)      # semente nova a cada bloco
        est["sequencias_completas"] = est.get("sequencias_completas", 0) + int(completas)
        est["tentativas"] += BLOCO
        est["blocos"] += 1
        est["segundos"] += round(time.time() - t0)
        est["chegou"] = [int(a + b) for a, b in zip(est["chegou"], chegou)]
        est["maior_sequencia"] = max((k for k, v in enumerate(est["chegou"]) if v), default=0)
        est["acertou_concurso_1"], est["acertou_1_e_2"] = est["chegou"][1], est["chegou"][2]
        ARQ.write_text(json.dumps(est, indent=2))
        print(est["tentativas"], est["chegou"][1:4], flush=True)
        if est["sequencias_completas"] > 0:
            break


if __name__ == "__main__":
    main()
