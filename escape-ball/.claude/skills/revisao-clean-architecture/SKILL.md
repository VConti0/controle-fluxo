---
name: revisao-clean-architecture
description: Use when reviewing, writing or changing code in the Escape Ball project (Flutter in lib/, Cloud Functions in functions/src/) — before a commit, merge or pull request, when asked for a code review, or when a change may break the Clean Architecture layers or the SOLID principles.
---

# Revisão de código: Clean Architecture + SOLID

## Visão geral

As dependências apontam **para dentro**: telas e implementações dependem do domínio, nunca o contrário. O domínio é Dart/TypeScript puro e testável sem Firebase, Flutter ou plugins. Esta skill define as camadas do projeto, as checagens obrigatórias e o formato do relatório.

## Mapa de camadas

**App (Flutter, `lib/`)**

| Pasta | O que mora lá | Pode importar | Nunca importa |
|---|---|---|---|
| `domain/` | entidades (`economy/`, `game/`, `account/`), `failures.dart`, portas (`ports/`, só `abstract interface class`), casos de uso (`usecases/`) | `dart:core/math/async/convert` e o próprio `domain/` | Flutter, `material_ui`, Flame, `dart:ui`, `dart:io`, qualquer `package:` de terceiros, `config.dart`, outras camadas |
| `data/` | implementações das portas: Firebase, Play Billing, AdMob, SharedPreferences, assets; fakes/offline em `data/local` | `domain/`, pacotes de infraestrutura | `presentation/`, `di/` |
| `presentation/` | telas, `AppState`, desenho do jogo (`game_view/`), textos (`l10n/`) | `domain/`, Flutter/Flame/`material_ui`, `config.dart` | `data/`, `di/`, `firebase_*`, `cloud_functions`, `google_sign_in`, `google_mobile_ads`, `in_app_purchase*`, `shared_preferences` |
| `di/` + `main.dart` | raiz de composição: escolhe qual implementação atende cada porta | tudo | — |

**Servidor (`functions/src/`)**

| Pasta | Pode importar | Nunca importa |
|---|---|---|
| `domain/` (`economy.ts`, `catalog.ts`) | `./` do próprio domínio e `node:` | `firebase-*`, `@googleapis/*`, `../adapters` |
| `adapters/` | `../domain`, SDKs | outros adapters, `index.ts` |
| `index.ts` | tudo (só monta e expõe) | — |

## Procedimento

1. **Escopo.** Revise o que mudou, não o projeto inteiro (salvo pedido explícito):
   ```bash
   git diff --name-only origin/main...HEAD -- escape-ball
   git diff origin/main...HEAD -- escape-ball
   ```
2. **Checagens automáticas primeiro.** Qualquer falha é **bloqueante**:
   ```bash
   cd escape-ball
   flutter analyze
   flutter test test/architecture_test.dart
   (cd functions && npx vitest run test/architecture.test.ts)
   ```
3. **Checklist manual** em cada arquivo alterado (abaixo).
4. **Números de linha**: tire de `grep -n` ou da leitura do arquivo **na árvore atual**. Nunca use a numeração da saída de `git show`/`git diff`; ela não corresponde ao arquivo.
5. **Escreva o relatório** no formato definido mais abaixo.

## Checklist manual

| Princípio | Sinal de problema neste projeto | Correção esperada |
|---|---|---|
| Regra de dependência | tela chamando Firebase/plugin; domínio com `Color`, `Widget`, `rootBundle`, `AppConfig` | criar/usar uma porta em `domain/ports`, implementar em `data/`, ligar em `di/bootstrap.dart` |
| **S** – Responsabilidade única | `AppState` ou uma tela ganhando regra de negócio (cálculo de aposta, crédito, validação); widget decidindo quando mostrar anúncio | mover a regra para um caso de uso em `domain/usecases` ou para a entidade |
| **O** – Aberto/fechado | novo item/produto exigindo `if (id == ...)` ou `kind == ball ? ... : ...` espalhado | dados no `assets/data/catalog.json`; mapas por `ItemKind`; nomes em `l10n/strings.dart` |
| **L** – Substituição de Liskov | fake (`LocalEconomyRepository`, `FakeBillingGateway`, `NoAds`) com regra diferente da real (ex.: aceitar token reutilizado que o servidor recusa) | igualar a regra e cobrir os dois lados com teste |
| **I** – Segregação de interfaces | porta com métodos que só uma tela usa, ou porta que devolve `Widget` | dividir a porta; UI fica na apresentação (ex.: `bannerBuilder`) |
| **D** – Inversão de dependência | `Classe.instance`, `FirebaseX.instance` ou `AppConfig` lidos dentro de `data/` ou `domain/`; `new` de implementação fora de `di/` | receber pelo construtor; montar em `di/bootstrap.dart` / `functions/src/index.ts` |
| Erros | tela comparando texto (`e.message == '...'`) ou capturando exceção de SDK | traduzir no `data/` para uma `Failure` tipada (`InsufficientFunds`, `PurchaseRejected`...) e tratar por tipo |
| Determinismo | código em `domain/game` usando `math.sin/cos`, `Random()` sem semente, ou mudando constantes da física | usar `det_math.dart`; ao mudar a física, rodar `dart run tool/gen_seeds.dart` e os testes |
| Testes | regra nova em `domain/` ou `functions/src/domain` sem teste | teste unitário com fakes em memória |

## Severidade

- **Bloqueante:** checagem automática falhando; violação da regra de dependência; regra de dinheiro (saldo, aposta, compra) fora do domínio do servidor ou sem teste; tela tratando erro por texto.
- **Importante:** violação de SOLID que vai obrigar a editar vários arquivos na próxima mudança; fake divergente da implementação real.
- **Sugestão:** nome, organização, duplicação pequena. Não impede o merge.

## Formato do relatório (em português)

1. **Veredito:** `Aprovar` | `Aprovar com sugestões` | `Pedir mudanças` (há qualquer bloqueante → `Pedir mudanças`).
2. **Checagens automáticas:** um item por comando, com ✅/❌ e a mensagem de falha resumida.
3. **Achados**, do mais grave ao mais leve. Um por linha, neste formato:
   `[Bloqueante|Importante|Sugestão] caminho/arquivo.dart:linha — princípio — o que está errado — correção concreta`
4. **O que está bom:** no máximo 3 itens.

## Pragmatismo: o que NÃO pedir

- Caso de uso que só repassa uma chamada da porta sem nenhuma regra.
- Interface para classe de valor do domínio (`Profile`, `RoundTicket`) ou para widget.
- Dividir uma classe só pelo tamanho, sem responsabilidades realmente diferentes.
- Mover `config.dart` para o domínio ou criar porta para constantes de tela.

## Ao corrigir (não só revisar)

Nova dependência de infraestrutura:
1. Porta em `domain/ports/`, como `abstract interface class`.
2. Implementação em `data/`.
3. Fake em `data/local/` para testes e modo offline.
4. Ligação em `di/bootstrap.dart`.

Depois, rode `flutter analyze && flutter test` e, se mexeu no servidor, `cd functions && npm test`.
