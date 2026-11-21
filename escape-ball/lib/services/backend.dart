/// The server side of the economy: balance, bets and purchases. In
/// production this is Cloud Functions ([FirebaseBackend]); offline builds and
/// tests use [LocalBackend], which follows the same rules on the device.
library;

import 'dart:math' as math;

import 'package:cloud_functions/cloud_functions.dart';

import '../config.dart';
import '../economy/bet.dart';
import '../economy/catalog.dart';
import '../economy/inventory.dart';
import '../game/arena.dart';
import '../game/round.dart';

class RoundTicket {
  final int seed;
  final ArenaShape shape;

  /// Attempt on which the ball escapes, as the server decided it.
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

class BackendException implements Exception {
  /// `insufficient-funds`, `invalid-purchase`, `unauthenticated`, `unavailable`...
  final String code;
  final String message;
  const BackendException(this.code, this.message);

  @override
  String toString() => 'BackendException($code): $message';
}

abstract class Backend {
  Future<Profile> getProfile();

  Future<RoundTicket> startRound({
    required ArenaShape shape,
    required int band,
    required int betCents,
  });

  /// Sends a store purchase to be checked and credited. Safe to call twice
  /// with the same token: it is credited once.
  Future<Profile> verifyPurchase({required String productId, required String purchaseToken});

  Future<Profile> buyWithCoins(String itemId);

  Future<void> deleteAccount();
}

/// A round with no coins at stake, for players who are not signed in.
RoundTicket practiceTicket({required ArenaShape shape, required int band, math.Random? random}) {
  final seed = (random ?? math.Random()).nextInt(0x7fffffff) + 1;
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

class FirebaseBackend implements Backend {
  final FirebaseFunctions _fns;

  FirebaseBackend()
      : _fns = FirebaseFunctions.instanceFor(region: AppConfig.functionsRegion) {
    if (AppConfig.useEmulators) {
      _fns.useFunctionsEmulator(AppConfig.emulatorHost, 5001);
    }
  }

  Future<Map<String, dynamic>> _call(String name, [Map<String, dynamic>? data]) async {
    try {
      final res = await _fns.httpsCallable(name).call<Object?>(data ?? const {});
      return Map<String, dynamic>.from(res.data as Map);
    } on FirebaseFunctionsException catch (e) {
      throw BackendException(e.code, e.message ?? e.code);
    }
  }

  @override
  Future<Profile> getProfile() async => Profile.fromJson(await _call('getProfile'));

  @override
  Future<RoundTicket> startRound({
    required ArenaShape shape,
    required int band,
    required int betCents,
  }) async {
    final r = await _call('startRound', {'shape': shape.name, 'band': band, 'bet': betCents});
    return RoundTicket(
      seed: (r['seed'] as num).toInt(),
      shape: shape,
      attempt: (r['attempt'] as num).toInt(),
      band: band,
      betCents: betCents,
      payoutCents: (r['payout'] as num).toInt(),
      balanceCents: (r['balance'] as num).toInt(),
      practice: false,
    );
  }

  @override
  Future<Profile> verifyPurchase({required String productId, required String purchaseToken}) async =>
      Profile.fromJson(
          await _call('verifyPurchase', {'productId': productId, 'purchaseToken': purchaseToken}));

  @override
  Future<Profile> buyWithCoins(String itemId) async =>
      Profile.fromJson(await _call('buyWithCoins', {'itemId': itemId}));

  @override
  Future<void> deleteAccount() => _call('deleteAccount');
}

/// Runs the same rules as the Cloud Functions on the device. Used by the
/// offline web demo and by tests. Never used in a release with Firebase.
class LocalBackend implements Backend {
  final Catalog catalog;
  final OddsTable odds;
  final math.Random _random;
  Profile _profile;
  final Set<String> _usedTokens = {};

  LocalBackend({
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
    if (band < 0 || band >= kBands.length) {
      throw const BackendException('invalid-argument', 'band');
    }
    if (betCents < catalog.minBetCoins * kCentsPerCoin ||
        betCents > catalog.maxBetCoins * kCentsPerCoin ||
        betCents % kCentsPerCoin != 0) {
      throw const BackendException('invalid-argument', 'bet');
    }
    if (_profile.balanceCents < betCents) {
      throw const BackendException('failed-precondition', 'insufficient-funds');
    }
    final seed = _random.nextInt(0x7fffffff) + 1;
    final attempt = simulateOutcome(seed, shape);
    final mult = odds.shapes[shape.name]!.multipliers[band];
    final payout = payoutCents(
        betCents: betCents, multiplier: mult, won: kBands[band].contains(attempt));
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
    final pack = catalog.pack(productId);
    if (pack != null) {
      if (_usedTokens.add(purchaseToken)) {
        _profile = _profile.copyWith(
            balanceCents: _profile.balanceCents + pack.coins * kCentsPerCoin);
      }
      return _profile;
    }
    if (productId == catalog.removeAdsProductId) {
      _profile = _profile.copyWith(removeAds: true);
      return _profile;
    }
    final item = catalog.itemForProduct(productId);
    if (item == null) throw const BackendException('invalid-argument', 'unknown product');
    _profile = _profile.copyWith(owned: {..._profile.owned, item.id});
    return _profile;
  }

  @override
  Future<Profile> buyWithCoins(String itemId) async {
    final item = catalog.item(itemId);
    if (item == null || item.price != PriceType.coins) {
      throw const BackendException('invalid-argument', 'item');
    }
    if (_profile.owned.contains(itemId)) return _profile;
    final cost = item.coins * kCentsPerCoin;
    if (_profile.balanceCents < cost) {
      throw const BackendException('failed-precondition', 'insufficient-funds');
    }
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
