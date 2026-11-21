/// Portuguese and English text, picked from the phone's language.
library;

import 'package:material_ui/material_ui.dart';

class S {
  final bool pt;
  const S(this.pt);

  static S of(BuildContext context) {
    final lang = Localizations.maybeLocaleOf(context)?.languageCode ?? 'pt';
    return S(lang == 'pt');
  }

  String _(String p, String e) => pt ? p : e;

  String get appTitle => _('Vai Escapar?', 'Will It Escape?');
  String get bigTitle => _('VAI ESCAPAR?', 'WILL IT ESCAPE?');
  String get play => _('Jogar', 'Play');
  String get store => _('Loja', 'Store');
  String get settings => _('Ajustes', 'Settings');
  String get signIn => _('Entrar com Google', 'Sign in with Google');
  String get signInWhy => _(
      'Entre para apostar moedas e fazer compras. Sem login você joga no modo treino.',
      'Sign in to bet coins and make purchases. Signed out, you play in practice mode.');
  String get signOut => _('Sair da conta', 'Sign out');
  String get coins => _('moedas', 'coins');
  String attempt(int n) => _('TENTATIVA $n', 'ATTEMPT $n');
  String get guessTitle => _('Em qual tentativa ela escapa?', 'Which attempt will it escape on?');
  String get guessHint =>
      _('A abertura cresce a cada tentativa.', 'The opening grows with every attempt.');
  String attemptsLabel(String range) => _('Tentativas $range', 'Attempts $range');
  String get bet => _('Aposta', 'Bet');
  String get practiceMode => _('Modo treino (sem moedas)', 'Practice mode (no coins)');
  String get practice => _('Treino', 'Practice');
  String get start => _('Soltar a bolinha', 'Drop the ball');
  String get notEnoughCoins => _('Moedas insuficientes.', 'Not enough coins.');
  String get buyCoins => _('Comprar moedas', 'Buy coins');
  String escapedOn(int n) => _('Escapou na tentativa $n!', 'Escaped on attempt $n!');
  String get escaped => _('ESCAPOU!', 'ESCAPED!');
  String get shattered => _('AS PAREDES QUEBRARAM!', 'THE WALLS SHATTERED!');
  String get youWon => _('Você acertou!', 'You got it!');
  String get youLost => _('Não foi dessa vez.', 'Not this time.');
  String yourGuess(String range) => _('Seu palpite: $range', 'Your guess: $range');
  String won(String c) => _('+$c moedas', '+$c coins');
  String balance(String c) => _('Saldo: $c moedas', 'Balance: $c coins');
  String get playAgain => _('Jogar de novo', 'Play again');
  String get menu => _('Menu', 'Menu');
  String get balls => _('Bolinhas', 'Balls');
  String get maps => _('Mapas', 'Maps');
  String get noAds => _('Sem anúncios', 'No ads');
  String get coinsTab => _('Moedas', 'Coins');
  String get equip => _('Usar', 'Equip');
  String get equipped => _('Em uso', 'Equipped');
  String get owned => _('Seu', 'Owned');
  String get free => _('Grátis', 'Free');
  String coinPrice(int c) => _('$c moedas', '$c coins');
  String get tryWithAd => _('Testar 1 rodada (anúncio)', 'Try 1 round (ad)');
  String get trialActive => _('Teste ativo na próxima rodada', 'Trial on your next round');
  String get adNotReady => _('Anúncio indisponível agora. Tente de novo.', 'No ad available. Try again.');
  String get removeAdsTitle => _('Remover anúncios', 'Remove ads');
  String get removeAdsBody => _(
      'Tira os banners e os anúncios entre rodadas. Compra única, vale para sempre na sua conta.',
      'Removes banners and ads between rounds. One-time purchase, yours forever.');
  String get removeAdsOwned => _('Anúncios removidos. Obrigado!', 'Ads removed. Thank you!');
  String coinPack(int c) => _('$c moedas', '$c coins');
  String get coinsDisclaimer => _(
      'Moedas são virtuais e sem valor de resgate: não podem ser sacadas, trocadas por dinheiro nem transferidas. Apenas para maiores de 18 anos.',
      'Coins are virtual and have no cash value: they cannot be withdrawn, exchanged for money or transferred. 18+ only.');
  String get restore => _('Restaurar compras', 'Restore purchases');
  String get privacyPolicy => _('Política de privacidade', 'Privacy policy');
  String get privacyOptions => _('Privacidade dos anúncios', 'Ad privacy settings');
  String get deleteAccount => _('Excluir conta', 'Delete account');
  String get deleteConfirm => _(
      'Isso apaga sua conta, seu saldo de moedas e seus itens. Não dá para desfazer.',
      'This deletes your account, coin balance and items. It cannot be undone.');
  String get cancel => _('Cancelar', 'Cancel');
  String get confirm => _('Confirmar', 'Confirm');
  String get processing => _('Processando compra…', 'Processing purchase…');
  String get purchaseDone => _('Compra concluída!', 'Purchase complete!');
  String get purchasePending =>
      _('Pagamento pendente. Creditamos quando for aprovado.', 'Payment pending. We will credit it once approved.');
  String get purchaseFailed => _('A compra não foi concluída.', 'The purchase did not go through.');
  String get genericError => _('Algo deu errado. Tente de novo.', 'Something went wrong. Try again.');
  String get offlineNotice => _(
      'Modo demonstração: nada é cobrado e o saldo é só deste aparelho.',
      'Demo mode: nothing is charged and the balance lives on this device only.');
  String get firebaseMissing => _(
      'Servidor não configurado: só o modo treino está disponível.',
      'Server not configured: only practice mode is available.');
  String get ageNotice => _('Jogo de azar simulado. 18+.', 'Simulated gambling. 18+.');
  String get speed => _('Velocidade', 'Speed');
  String get signedInAs => _('Conectado como', 'Signed in as');
}
