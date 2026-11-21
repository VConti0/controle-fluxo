import 'dart:math' as math;

import '../economy/round_ticket.dart';
import '../game/arena.dart';
import '../game/round.dart';
import '../ports/economy_repository.dart';

/// Starts a round: a real bet through the server when there is one and the
/// player is betting, otherwise a practice round decided on the device.
class PlayRound {
  final EconomyRepository? _economy;
  final math.Random _random;

  PlayRound(this._economy, {math.Random? random}) : _random = random ?? math.Random();

  bool get canBet => _economy != null;

  Future<RoundTicket> call({
    required ArenaShape shape,
    required int band,
    required int betCents,
    required bool signedIn,
  }) {
    final economy = _economy;
    if (betCents == 0 || !signedIn || economy == null) {
      return Future.value(practice(shape: shape, band: band));
    }
    return economy.startRound(shape: shape, band: band, betCents: betCents);
  }

  /// A round with no coins at stake.
  RoundTicket practice({required ArenaShape shape, required int band}) {
    final seed = _random.nextInt(0x7fffffff) + 1;
    return RoundTicket(
      seed: seed,
      shape: shape,
      attempt: simulateOutcome(seed, shape),
      band: band,
      betCents: 0,
      payoutCents: 0,
      balanceCents: null,
      practice: true,
    );
  }
}
