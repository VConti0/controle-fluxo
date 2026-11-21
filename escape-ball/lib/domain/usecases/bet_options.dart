import '../economy/bet.dart';
import '../economy/catalog.dart';
import '../economy/inventory.dart';

/// Which bets the guess screen offers and whether the player can afford one.
class BetOptions {
  final Catalog catalog;
  const BetOptions(this.catalog);

  List<int> get coinChoices => [
        for (final c in kBetCoins)
          if (c >= catalog.minBetCoins && c <= catalog.maxBetCoins) c,
      ];

  /// Cents at stake: 0 in practice mode.
  int stakeCents({required int coins, required bool practice}) =>
      practice ? 0 : coins * kCentsPerCoin;

  bool canAfford(Profile profile, int stakeCents) =>
      stakeCents == 0 || profile.balanceCents >= stakeCents;
}
