import 'dart:math' as math;

import '../../domain/economy/bet.dart';
import '../../domain/economy/catalog.dart';
import '../../domain/economy/inventory.dart';
import '../../domain/economy/round_ticket.dart';
import '../../domain/failures.dart';
import '../../domain/game/arena.dart';
import '../../domain/game/round.dart';
import '../../domain/ports/economy_repository.dart';

/// Applies the same rules as the Cloud Functions on the device. Used by the
/// offline web demo and by tests; never in a release with Firebase. Keep it in
/// step with functions/src/domain/economy.ts: the shared contract tests in
/// test/economy_test.dart cover both sets of rules.
class LocalEconomyRepository implements EconomyRepository {
  final Catalog catalog;
  final OddsTable odds;
  final math.Random _random;
  Profile _profile;

  /// token → product it was first used for.
  final Map<String, String> _usedTokens = {};

  LocalEconomyRepository({
    required this.catalog,
    required this.odds,
    Profile initial = const Profile(balanceCents: 20 * kCentsPerCoin),
    math.Random? random,
  })  : _profile = initial,
        _random = random ?? math.Random();

  @override
  Future<Profile> getProfile() async => _profile;

  @override
  Future<RoundTicket> startRound({
    required ArenaShape shape,
    required int band,
    required int betCents,
  }) async {
    if (band < 0 || band >= kBands.length) throw const InvalidRequest('band');
    if (betCents < catalog.minBetCoins * kCentsPerCoin ||
        betCents > catalog.maxBetCoins * kCentsPerCoin ||
        betCents % kCentsPerCoin != 0) {
      throw const InvalidRequest('bet');
    }
    if (_profile.balanceCents < betCents) throw const InsufficientFunds();
    final seed = _random.nextInt(0x7fffffff) + 1;
    final attempt = simulateOutcome(seed, shape);
    final mult = odds.shapes[shape.name]!.multipliers[band];
    final payout =
        payoutCents(betCents: betCents, multiplier: mult, won: kBands[band].contains(attempt));
    _profile = _profile.copyWith(balanceCents: _profile.balanceCents - betCents + payout);
    return RoundTicket(
      seed: seed,
      shape: shape,
      attempt: attempt,
      band: band,
      betCents: betCents,
      payoutCents: payout,
      balanceCents: _profile.balanceCents,
      practice: false,
    );
  }

  @override
  Future<Profile> verifyPurchase({required String productId, required String purchaseToken}) async {
    final firstUse = _usedTokens[purchaseToken];
    if (firstUse != null && firstUse != productId) {
      throw const PurchaseRejected('token-product-mismatch');
    }
    final pack = catalog.pack(productId);
    if (pack != null) {
      if (firstUse == null) {
        _profile = _profile.copyWith(
            balanceCents: _profile.balanceCents + pack.coins * kCentsPerCoin);
      }
      _usedTokens[purchaseToken] = productId;
      return _profile;
    }
    if (productId == catalog.removeAdsProductId) {
      _usedTokens[purchaseToken] = productId;
      _profile = _profile.copyWith(removeAds: true);
      return _profile;
    }
    final item = catalog.itemForProduct(productId);
    if (item == null) throw const InvalidRequest('unknown product');
    _usedTokens[purchaseToken] = productId;
    _profile = _profile.copyWith(owned: {..._profile.owned, item.id});
    return _profile;
  }

  @override
  Future<Profile> buyWithCoins(String itemId) async {
    final item = catalog.item(itemId);
    if (item == null || item.price != PriceType.coins) throw const InvalidRequest('item');
    if (_profile.owned.contains(itemId)) return _profile;
    final cost = item.coins * kCentsPerCoin;
    if (_profile.balanceCents < cost) throw const InsufficientFunds();
    _profile = _profile.copyWith(
      balanceCents: _profile.balanceCents - cost,
      owned: {..._profile.owned, itemId},
    );
    return _profile;
  }

  @override
  Future<void> deleteAccount() async {
    _profile = Profile.empty;
  }
}
