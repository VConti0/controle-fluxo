# Instruções para uma sessão-trabalhadora da busca física

Você recebeu um número de trabalhador N. Não altere código, não faça commit, não faça push e não abra
pull request. Responda em português.

1. No repositório controle-fluxo, confirme que está no branch `ccr-9c432ffd-3m14km` (se não,
   `git fetch origin ccr-9c432ffd-3m14km && git checkout ccr-9c432ffd-3m14km`).
2. `cd megasena && pip install numpy pandas numba`.
3. Rode em segundo plano (run_in_background, timeout de 7000000 ms):
   `cd megasena && mkdir -p results && python3 -u fisica_trabalhador.py N 110 >> results/trabalhador_N.log 2>&1`
4. Sempre que essa execução terminar, veja `tail -n 3 results/trabalhador_N.log`. Se a última linha
   começar com `SENA`, envie essa linha inteira com a ferramenta send_message (servidor
   claude-code-remote) para a sessão `session_01MUKpa5Guz4dPcTCVEg7F7C` e pare. Se não, rode o mesmo
   comando de novo (ele retoma de onde parou). Repita indefinidamente.

Não fique verificando o log enquanto o comando roda; espere a notificação de término.
