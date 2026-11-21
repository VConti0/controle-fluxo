import '../game/arena.dart';
import 'bet.dart';

/// A round as decided by the server (or locally, in practice mode): the
/// seed to replay and how it ends.
class RoundTicket {
  final int seed;
  final ArenaShape shape;

  /// Attempt on which the ball escapes.
  final int attempt;
  final int band;
  final int betCents;
  final int payoutCents;

  /// Balance after the round, or null in practice mode.
  final int? balanceCents;
  final bool practice;

  const RoundTicket({
    required this.seed,
    required this.shape,
    required this.attempt,
    required this.band,
    required this.betCents,
    required this.payoutCents,
    required this.balanceCents,
    required this.practice,
  });

  bool get won => kBands[band].contains(attempt);
}
