# Mega-Sena: modelos de predição + LLM

Todos os **3.088 concursos** (11/03/1996 a 19/11/2026), baixados da API oficial da Caixa, com
modelos estatísticos, de machine learning e um Transformer estilo GPT treinado como modelo de
linguagem sobre as dezenas. Cada modelo foi avaliado fora da amostra antes de gerar o palpite do
**concurso 3089 (22/11/2026)**.

## TL;DR

**Nenhum modelo prevê a Mega-Sena melhor que o acaso.** Nos 500 concursos de teste (2589–3088),
um jogo aleatório acerta em média **0,600** dezenas. Todos os modelos ficaram dentro do ruído
estatístico, e nenhum fez quadra uma única vez.

| Modelo | Acertos médios (500 concursos) | p-valor vs. acaso |
|---|---|---|
| Aleatório (controle) | 0,628 | 0,37 |
| Mais frequentes (histórico) | 0,592 | 0,80 |
| Quentes (últimos 25) | 0,616 | 0,61 |
| Frios | 0,544 | 0,08 |
| Atrasados (maior jejum) | 0,594 | 0,85 |
| Regressão logística | 0,584 | 0,61 |
| Gradient boosting | 0,652 | 0,10 |
| **LLM Transformer** | **0,606** | **0,85** |

Os modelos probabilísticos confirmam o resultado:
- O log-loss da regressão logística e do gradient boosting (0,32511 / 0,32509) é **igual ou pior** que o de
  chutar "10% para cada número" (0,32508).
- O LLM teve entropia cruzada de **4,065 nats/bola** no teste, contra **4,051** do sorteio
  aleatório sem reposição, ou seja, um pouco *pior* que o acaso. No treino ele cai bem abaixo
  disso: decora o passado e não generaliza (veja `results/llm.json`, campo `curva`).

## O que a análise estatística encontrou (`results/analise.json`)

- Soma das dezenas, pares/ímpares, repetição em relação ao concurso anterior e autocorrelação:
  tudo bate com o esperado para sorteios aleatórios.
- A frequência dos 60 números é **levemente não-uniforme** (qui² p = 0,019). O 10 saiu 364 vezes, o 26
  só 250 (o esperado é 308,8). O desvio vem todo do período 2013–2026 (p = 0,0008). A primeira metade é
  uniforme (p = 0,53).
- Usar esse desvio ("os mais frequentes dos últimos 1000 concursos") deu z = +2,47 num
  walk-forward. Só que essa janela foi escolhida *depois* de olhar os dados, entre mais de uma dúzia
  de estratégias testadas, e não sobrevive à correção por múltiplos testes (precisaria de z ≈ 2,9).
  Mesmo se fosse real, seria +0,04 acerto por jogo, sem efeito prático.

## Palpites para o concurso 3089 (`results/previsao.json`)

| Estratégia | Dezenas |
|---|---|
| Consenso dos modelos | 04 05 10 16 38 43 |
| LLM Transformer (top-6 marginal) | 05 10 11 32 35 52 |
| Gradient boosting | 10 16 28 30 36 38 |
| Mais frequentes (histórico) | 05 10 27 37 38 53 |
| Exploratório (frequentes últimos 1000) | 10 11 27 35 38 46 |
| Quentes (últimos 25) | 04 06 10 27 29 57 |
| Atrasados | 08 11 15 26 53 56 |
| Surpresinha aleatória | 05 23 39 51 52 57 |

Qualquer um desses jogos tem a mesma chance de sena: **1 em 50.063.860**. O backtest mostra que
nenhum deles é melhor que a surpresinha.

## Teste da semana passada (`results/comparacao_ate_3082.json`)

Modelos treinados só com os concursos 1–3082 (até 06/11/2026) e um único palpite por modelo,
comparado com os três sorteios da semana seguinte:

- 3083 (08/11): 22 25 29 37 46 54
- 3084 (10/11): 06 14 22 30 31 37
- 3085 (12/11): 10 27 29 37 39 59

| Estratégia | Palpite | 3083 | 3084 | 3085 |
|---|---|---|---|---|
| Mais frequentes (histórico) | 05 10 27 37 38 53 | 1 | 1 | 3 |
| LLM (jogo mais gerado) | 02 09 29 37 43 47 | 2 | 1 | 2 |
| Atrasados | 15 21 26 37 46 56 | 2 | 1 | 1 |
| Exploratório (últimos 1000) | 10 11 27 35 38 46 | 1 | 0 | 2 |
| LLM (top-6 marginal) | 10 35 38 43 53 54 | 1 | 0 | 1 |
| Gradient boosting | 02 04 05 14 16 58 | 0 | 1 | 0 |
| Quentes (últimos 25) | 04 05 10 38 41 57 | 0 | 0 | 1 |
| Consenso | 04 05 10 35 38 43 | 0 | 0 | 1 |
| Surpresinha aleatória | 13 17 35 40 51 60 | 0 | 0 | 0 |

Nenhum palpite chegou à quadra (menor faixa premiada). O melhor foi um terno. O 37 saiu nos três
sorteios da semana, e sozinho responde por 9 dos 22 acertos da tabela. Três sorteios são amostra
pequena demais para ranquear modelos: o teste que vale é o de 500 concursos acima.

## Ensemble multi-modelo (`ensemble.py`)

Pipeline único com 5 modelos base (hipergeométrica com encolhimento, auditoria em janelas móveis,
Monte Carlo de máxima entropia com 100.000 sorteios, ARIMA + FFT por número, XGBoost + LSTM), um
meta-modelo (soft voting + stacking por regressão logística) e um filtro combinatório (soma 150–210,
2 a 4 pares, no máximo 2 dezenas por linha e por coluna do volante).

Backtest walk-forward nos últimos 20 concursos (3069–3088), 1 jogo por concurso:

| Modelo | Acertos médios | Ternos | Quadras+ |
|---|---|---|---|
| Ensemble final | 0,55 | 0 | 0 |
| Soft voting | 0,70 | 0 | 0 |
| Stacking | 0,70 | 1 | 0 |
| M1 hipergeométrica | 0,80 | 1 | 0 |
| M2 auditoria | 0,50 | 0 | 0 |
| M3 Monte Carlo | 0,95 | 0 | 0 |
| M4 ARIMA + FFT | 0,60 | 0 | 0 |
| M5 XGBoost + LSTM | 0,85 | 0 | 0 |
| Aleatório (teórico) | 0,60 | | |

Com 20 concursos, a média de um apostador aleatório cai entre 0,30 e 0,90 em 95% dos casos, então
só o M3 sai dessa faixa, e por pouco. O ensemble final ficou abaixo do acaso. O filtro combinatório
aprova 30,8% de todas as combinações possíveis e os mesmos 30,8% dos sorteios históricos: ele não
seleciona nada que saia mais.

Saídas em `results/`: `ensemble_saida.txt` (relatório), `ensemble_matriz.csv` (scores dos 60 números),
`ensemble_backtest.csv` e `ensemble.json` (pesos do stacking, backtest e os 5 jogos).

## Como rodar

```bash
pip install -r requirements.txt   # torch: --index-url https://download.pytorch.org/whl/cpu
python3 fetch_data.py   # baixa/atualiza data/megasena.csv (incremental)
python3 analise.py      # testes estatísticos
python3 classicos.py    # backtest dos modelos clássicos e de ML (~1 min)
python3 llm.py          # treina o Transformer e faz o backtest (~15 min em CPU)
python3 prever.py       # palpites para o próximo concurso (~2 min)
python3 ensemble.py --backtest 20   # comitê multi-modelo, backtest e Top 5 jogos (~10 min)
python3 online.py        # aprendizado sorteio a sorteio e percentual de acerto por ano (~30 min)
python3 comite.py        # testes estatísticos do debate (runs, entropia, Monte Carlo, ARIMA, FFT)
python3 comparar.py --ate 3082 --alvos 3083 3084 3085   # prevê com dados até o 3082 e compara com o real
```

Para atualizar depois de cada sorteio (inclusive a Mega da Virada), rode `fetch_data.py` e `prever.py`.

## Arquivos

- `fetch_data.py`: download pela API `servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{n}`
- `common.py`: carga dos dados e métricas (distribuição hipergeométrica de acertos)
- `analise.py`: testes de aleatoriedade
- `classicos.py`: heurísticas, regressão logística e gradient boosting com backtest walk-forward
- `llm.py`: GPT decoder (356 mil parâmetros) com tokens `<SEP> b1..b6` na ordem real do sorteio
- `prever.py`: re-treina tudo no histórico (ou até `--ate N`) e gera os palpites
- `comparar.py`: prevê com dados até um concurso de corte e compara com os resultados seguintes
