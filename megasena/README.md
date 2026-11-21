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

## Como rodar

```bash
pip install -r requirements.txt   # torch: --index-url https://download.pytorch.org/whl/cpu
python3 fetch_data.py   # baixa/atualiza data/megasena.csv (incremental)
python3 analise.py      # testes estatísticos
python3 classicos.py    # backtest dos modelos clássicos e de ML (~1 min)
python3 llm.py          # treina o Transformer e faz o backtest (~15 min em CPU)
python3 prever.py       # palpites para o próximo concurso (~2 min)
```

Para atualizar depois de cada sorteio (inclusive a Mega da Virada), rode `fetch_data.py` e `prever.py`.

## Arquivos

- `fetch_data.py`: download pela API `servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{n}`
- `common.py`: carga dos dados e métricas (distribuição hipergeométrica de acertos)
- `analise.py`: testes de aleatoriedade
- `classicos.py`: heurísticas, regressão logística e gradient boosting com backtest walk-forward
- `llm.py`: GPT decoder (356 mil parâmetros) com tokens `<SEP> b1..b6` na ordem real do sorteio
- `prever.py`: re-treina tudo no histórico completo e gera os palpites
