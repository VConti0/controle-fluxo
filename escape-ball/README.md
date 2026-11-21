# Vai Escapar? (Escape Ball)

Jogo para Android em que uma bolinha quica dentro de um polígono que gira, cheio de espinhos, até achar a saída. O jogador aposta em qual tentativa ela vai escapar.

- **Jogar:** é uma simulação para assistir. A cada tentativa que falha, a bolinha deixa um "X" onde morreu e a abertura cresce.
- **Palpite:** antes da rodada, o jogador escolhe uma faixa de tentativas (1–2, 3–4, 5–6, 7–8, 9+). Sem login, joga no **modo treino** (sem moedas). Com login, aposta **moedas**: cada faixa paga um multiplicador calculado pela chance real dela, com retorno médio de 95%.
- **Loja:**
  - pacotes de moedas de R$ 5 a R$ 2.000 (1 moeda = R$ 2,50)
  - visuais da bolinha e do mapa (alguns grátis, alguns por moedas, alguns pagos)
  - "Remover anúncios"
  - qualquer visual pode ser testado por 1 rodada assistindo a um anúncio
- **Anúncios (AdMob):** banner no menu, no palpite, no resultado e na loja; intersticial a cada 3 rodadas; recompensado para testar um visual. Nunca durante a simulação.
- **Login com Google:** só é pedido para comprar ou apostar.

> **As moedas não podem ser sacadas, trocadas por dinheiro nem transferidas, nunca.** Se isso mudar, o jogo vira aposta com dinheiro real, que exige licença da Lei 14.790/2023 e o programa de jogos de azar da Play Store. Do jeito que está, é um jogo de "azar simulado": classifique como **18+** (veja [Play Console](#4-play-console)).

## Como está organizado (Clean Architecture)

As dependências apontam para dentro: as telas e as integrações dependem do domínio, e o domínio não depende de nada externo.

| Pasta | Camada | O quê |
|---|---|---|
| `lib/domain/` | domínio (Dart puro) | física determinística (`game/`), economia e catálogo (`economy/`), falhas tipadas, **portas** (`ports/`, interfaces) e **casos de uso** (`usecases/`) |
| `lib/data/` | dados | implementações das portas: Firebase, Google Play, AdMob, armazenamento local e as versões offline e de teste |
| `lib/presentation/` | apresentação | telas, `AppState`, desenho do jogo, textos PT/EN; só conversa com o domínio |
| `lib/di/` + `main.dart` | composição | o único lugar que escolhe qual implementação atende cada porta |
| `lib/config.dart` | configuração | **tudo o que você precisa trocar antes de publicar** |
| `functions/src/domain/` | domínio do servidor | regras de saldo, aposta e compra |
| `functions/src/adapters/` | adaptadores | Firestore, API do Google Play, Firebase Auth, arquivos de dados |
| `assets/data/catalog.json` | dados | preços, IDs de produto e itens; o servidor lê o mesmo arquivo |
| `tool/gen_seeds.dart` | ferramenta | gera as tabelas de sementes do servidor e as chances mostradas no app |

**A regra de dependências é testada automaticamente** em `test/architecture_test.dart` e `functions/test/architecture.test.ts`: se uma tela importar o Firebase ou o domínio importar o Flutter, o teste falha.

**Revisão de código:** a skill `.claude/skills/revisao-clean-architecture/` define as camadas, as checagens, o checklist SOLID e o formato do relatório. No Claude Code, peça "revisa minhas mudanças"; o `CLAUDE.md` indica a skill.

### Por que o servidor decide a rodada

O saldo vale dinheiro, então o celular não pode decidir quem ganhou. Quando o jogador aposta, o servidor:

1. desconta a aposta;
2. sorteia uma semente de uma tabela pré-calculada (5.000 por formato de mapa, com o resultado de cada uma já conhecido);
3. paga o prêmio, se for o caso, e devolve a semente.

O celular só **reproduz** a rodada daquela semente. A física usa matemática determinística, então ela chega ao mesmo resultado (há um teste que confere isso). Se você mudar qualquer constante da física em `lib/game/arena.dart`, rode de novo:

```bash
dart run tool/gen_seeds.dart            # --rtp=0.95 muda o retorno médio
```

## Rodar e testar

Pré-requisitos: [Flutter](https://docs.flutter.dev/get-started/install) 3.50+, Android Studio (ou só o SDK do Android), Node 22 e `npm i -g firebase-tools`.

```bash
flutter pub get
flutter test                          # física, economia, tabelas de sementes
cd functions && npm install && npm test && npm run test:rules && cd ..   # servidor e regras
```

**Demonstração sem nada configurado.** Abre no navegador ou no celular. As moedas são de mentira e ficam só no aparelho:

```bash
flutter run -d chrome                         # web: sempre em modo demonstração
flutter run --dart-define=OFFLINE=true        # celular em modo demonstração
```

**No seu celular, sem conta de desenvolvedor:**

```bash
flutter build apk --release --dart-define=FAKE_BILLING=true
# instale build/app/outputs/flutter-apk/app-release.apk no celular
```

- Funcionam o jogo, os anúncios de teste do Google e o login com Google (depois de configurar o Firebase, abaixo).
- Compras de verdade só funcionam com o app na Play Store. Com `FAKE_BILLING=true` as compras são simuladas, nada é cobrado, e o servidor só aceita esse tipo de compra se a variável `ALLOW_FAKE_PURCHASES=true` estiver ligada nas funções.
- **Desligue `ALLOW_FAKE_PURCHASES` antes de publicar**, senão qualquer um consegue moedas de graça.
- Sem o `google-services.json`, o app abre só no modo treino e mostra um aviso.

**Servidor local (emulador):**

```bash
cd functions && npm run serve      # funções, login e banco locais
# em outro terminal, com o emulador do Android aberto:
flutter run --dart-define=USE_EMULATORS=true --dart-define=FAKE_BILLING=true
node functions/scripts/smoke.mjs   # teste de ponta a ponta contra os emuladores
```

## Publicar na Play Store: o passo a passo

### 1. Contas

- **[Google Play Console](https://play.google.com/console):** US$ 25, pagos uma vez, com verificação de identidade.
  - **Atenção:** contas pessoais novas precisam fazer um **teste fechado com pelo menos 12 testadores durante 14 dias seguidos** antes de liberar a produção. Comece a juntar testadores cedo.
- **[AdMob](https://admob.google.com):** grátis. Crie o app e três blocos de anúncio: banner, intersticial e premiado.
- **[Firebase](https://console.firebase.google.com):** crie um projeto e ative o **plano Blaze**, que cobra por uso. As Cloud Functions exigem esse plano; com poucos jogadores o custo é perto de zero. Configure um alerta de orçamento.

### 2. Firebase

1. Adicione um app Android com o pacote `com.vconti.escapeball`.
2. Baixe o `google-services.json` e coloque em `android/app/`. Ele fica fora do git.
3. Em Authentication → Método de login, ative o **Google**. Copie o "ID do cliente da Web" para `googleServerClientId` em `lib/config.dart`.
4. Registre a impressão digital **SHA-1** das suas chaves no app Android do Firebase. Rode `cd android && ./gradlew signingReport` para ver a de debug e a de release. Depois de publicar, adicione também a SHA-1 da "Chave de assinatura do app" que o Play Console mostra em Integridade do app.
5. Crie o banco Firestore no modo produção, região `southamerica-east1`.
6. Publique o servidor:
   ```bash
   firebase login
   firebase use --add            # escolha o seu projeto
   cd functions && npm install && cd ..
   firebase deploy --only functions,firestore:rules
   ```

### 3. Chave de assinatura

```bash
keytool -genkey -v -keystore ~/escape-ball-upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

Crie `android/key.properties`. Esse arquivo fica fora do git; **guarde a chave e as senhas num lugar seguro**, porque sem elas você não atualiza mais o app:

```
storePassword=...
keyPassword=...
keyAlias=upload
storeFile=/caminho/para/escape-ball-upload.jks
```

### 4. Play Console

1. Crie o app.
2. **Produtos no app** (Monetizar → Produtos → Produtos no app). Crie exatamente estes IDs. Os preços sugeridos estão em `assets/data/catalog.json`:

   | ID | Tipo | Preço sugerido |
   |---|---|---|
   | `coins_2` … `coins_800` | moedas (consumível) | R$ 5 … R$ 2.000 (R$ 2,50 por moeda) |
   | `remove_ads` | único | R$ 9,90 |
   | `ball_fire`, `ball_rainbow` | único | R$ 4,90 / R$ 6,90 |
   | `map_hexagon`, `map_triangle` | único | R$ 6,90 |

   Confira se R$ 2.000 cabe no preço máximo por item em BRL. Se não couber, remova `coins_800` do `catalog.json`.
3. **Acesso da API para o servidor validar as compras:**
   - No Google Cloud do projeto Firebase, ative a **Google Play Android Developer API**.
   - No Play Console → Usuários e permissões, convide a conta de serviço das funções (`PROJETO@appspot.gserviceaccount.com`, ou a conta "Compute Engine default" que aparece no Google Cloud) com permissão de **ver dados financeiros e gerenciar pedidos**.
4. **Política de privacidade:** edite o `PRIVACY.md`, publique em algum lugar público (GitHub Pages serve) e coloque a URL em `lib/config.dart` e no Play Console.
5. **Exclusão de conta:** o app tem o botão "Excluir conta" em Ajustes. O Google também exige uma **página web** explicando como pedir a exclusão (pode ser uma seção do `PRIVACY.md`). Informe essa URL no formulário de Segurança dos dados.
6. **Segurança dos dados:** o app coleta
   - e-mail e nome (login Google)
   - ID do usuário
   - histórico de compras
   - ID de publicidade (AdMob)
   - dados de interação com o app (apostas)

   Tudo é transmitido com criptografia, e o usuário pode pedir a exclusão.
7. **Classificação de conteúdo (IARC):** responda **Sim** para "jogos de azar simulados". Isso deve resultar em 18+ / ClassInd 18.
8. **Público-alvo:** somente maiores de 18.
9. **Anúncios:** marque que o app contém anúncios.

### 5. AdMob

Troque os IDs de **teste** pelos seus:
- `lib/config.dart`: `admobBannerAndroid`, `admobInterstitialAndroid`, `admobRewardedAndroid`
- `android/app/src/main/AndroidManifest.xml`: `com.google.android.gms.ads.APPLICATION_ID`

Configure a mensagem de consentimento GDPR no AdMob (Privacidade e mensagens). O app já mostra o formulário para quem está na Europa. **Nunca clique nos seus próprios anúncios reais.**

### 6. Gerar e enviar

```bash
flutter build appbundle --release
# envie build/app/outputs/bundle/release/app-release.aab para "Teste interno"
```

No Play Console → Configuração → Teste de licença, adicione o seu Gmail. Assim as compras do teste interno usam cartões de teste e não cobram.

## Levar para o iOS (segunda etapa)

O código já está pronto para isso: a pasta `ios/` existe, e login, compras e anúncios ficam atrás de interfaces (`AuthService`, `BillingService`, `AdsService`). O servidor também já registra a loja de cada compra (`store: "play"`). Falta:

- **Conta:** Apple Developer (US$ 99/ano). Crie o app e os mesmos produtos no App Store Connect.
- **Login:** "Entrar com a Apple" (pacote `sign_in_with_apple`). A Apple exige isso quando o app tem login com Google.
- **Anúncios:**
  - Aviso de rastreamento ATT (pacote `app_tracking_transparency`) antes de carregar anúncios.
  - `SKAdNetworkItems` e `GADApplicationIdentifier` no `ios/Runner/Info.plist`.
- **Compras:**
  - Uma implementação de `PurchaseVerifier` em `functions/src/play.ts` para a App Store Server API, gravando `store: "app_store"`.
  - No app, `billing_play.dart` → uma versão StoreKit.
- **Firebase:** `GoogleService-Info.plist` em `ios/Runner/`.
- **Compilação:** num Mac com Xcode, ou no [Codemagic](https://codemagic.io) sem Mac. Distribuição pelo TestFlight.
