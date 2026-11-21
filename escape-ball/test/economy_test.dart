import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:escapeball/data/local/local_economy_repository.dart';
import 'package:escapeball/domain/economy/bet.dart';
import 'package:escapeball/domain/economy/catalog.dart';
import 'package:escapeball/domain/economy/inventory.dart';
import 'package:escapeball/domain/failures.dart';
import 'package:escapeball/domain/game/arena.dart';
import 'package:flutter_test/flutter_test.dart';

Catalog _catalog() => Catalog.fromJson(
    jsonDecode(File('assets/data/catalog.json').readAsStringSync()) as Map<String, dynamic>);

OddsTable _odds() => OddsTable.fromJson(
    jsonDecode(File('assets/data/odds.json').readAsStringSync()) as Map<String, dynamic>);

void main() {
  group('bands and payouts', () {
    test('every attempt falls in exactly one band', () {
      for (var a = 1; a <= kMaxAttempts; a++) {
        expect(kBands.where((b) => b.contains(a)).length, 1, reason: 'attempt $a');
      }
      expect(bandOf(1), 0);
      expect(bandOf(2), 0);
      expect(bandOf(3), 1);
      expect(bandOf(8), 3);
      expect(bandOf(9), 4);
      expect(bandOf(12), 4);
    });

    test('payout rounds down to the cent and is zero on a miss', () {
      expect(payoutCents(betCents: 100, multiplier: 3.27, won: true), 327);
      expect(payoutCents(betCents: 300, multiplier: 9.63, won: true), 2889);
      expect(payoutCents(betCents: 500, multiplier: 9.63, won: false), 0);
    });

    test('multiplier never exceeds the target return', () {
      expect(multiplierFor(0.25, 0.95), 3.8);
      expect(multiplierFor(0.099, 0.95), 9.59);
      expect(multiplierFor(0, 0.95), 0);
    });

    test('formatCoins', () {
      expect(formatCoins(0), '0');
      expect(formatCoins(100), '1');
      expect(formatCoins(2889), '28,89');
      expect(formatCoins(5), '0,05');
    });

    test('generated odds return close to, and never above, the target', () {
      final odds = _odds();
      for (final shape in ArenaShape.values) {
        final o = odds.shapes[shape.name]!;
        expect(o.probabilities.reduce((a, b) => a + b), closeTo(1, 1e-9));
        for (var b = 0; b < kBands.length; b++) {
          final ret = o.probabilities[b] * o.multipliers[b];
          expect(ret, lessThanOrEqualTo(odds.rtp + 1e-9), reason: '${shape.name} band $b');
          expect(ret, greaterThan(odds.rtp - 0.01), reason: '${shape.name} band $b');
        }
      }
    });
  });

  group('catalog', () {
    test('coin packs follow 1 coin = R\$ 2,50, from R\$ 5 to R\$ 2.000', () {
      final c = _catalog();
      for (final p in c.coinPacks) {
        expect(p.brl, closeTo(p.coins * 2.5, 1e-9), reason: p.productId);
      }
      expect(c.coinPacks.first.brl, 5);
      expect(c.coinPacks.last.brl, 2000);
    });

    test('exactly one default item per kind, and it is free', () {
      final c = _catalog();
      for (final kind in ItemKind.values) {
        final defaults = c.ofKind(kind).where((i) => i.isDefault).toList();
        expect(defaults, hasLength(1), reason: kind.name);
        expect(defaults.single.price, PriceType.free);
      }
    });

    test('every map has a shape and every paid item a product id', () {
      final c = _catalog();
      for (final i in c.items) {
        if (i.kind == ItemKind.map) expect(i.shape, isNotNull, reason: i.id);
        if (i.price == PriceType.paid) expect(i.productId, isNotNull, reason: i.id);
        if (i.price == PriceType.coins) expect(i.coins, greaterThan(0), reason: i.id);
      }
      expect(c.ofKind(ItemKind.ball).where((i) => i.price == PriceType.free), isNotEmpty);
      expect(c.ofKind(ItemKind.map).where((i) => i.price == PriceType.free), isNotEmpty);
    });

    test('inventory falls back to free skins it does not own', () {
      final inv = Inventory(
        catalog: _catalog(),
        profile: Profile.empty,
        equipped: {ItemKind.ball: 'ball_fire', ItemKind.map: 'map_hexagon'},
      );
      expect(inv.owns('ball_white'), isTrue);
      expect(inv.owns('ball_fire'), isFalse);
      expect(inv.ball, 'ball_white');
      expect(inv.map, 'map_pentagon');
    });
  });

  group('local backend (same rules as the server)', () {
    LocalEconomyRepository make({int coins = 10}) => LocalEconomyRepository(
          catalog: _catalog(),
          odds: _odds(),
          initial: Profile(balanceCents: coins * kCentsPerCoin),
          random: math.Random(1),
        );

    test('a round debits the bet and credits the payout', () async {
      final b = make();
      final t = await b.startRound(shape: ArenaShape.pentagon, band: 1, betCents: 200);
      final mult = _odds().shapes['pentagon']!.multipliers[1];
      final expected = t.won ? (200 * mult).floor() : 0;
      expect(t.payoutCents, expected);
      expect(t.balanceCents, 1000 - 200 + expected);
      expect((await b.getProfile()).balanceCents, t.balanceCents);
    });

    test('rejects bets it cannot cover, and odd amounts', () async {
      final b = make(coins: 1);
      expect(() => b.startRound(shape: ArenaShape.square, band: 0, betCents: 200),
          throwsA(isA<InsufficientFunds>()));
      expect(() => b.startRound(shape: ArenaShape.square, band: 0, betCents: 150),
          throwsA(isA<InvalidRequest>()));
      expect(() => b.startRound(shape: ArenaShape.square, band: 9, betCents: 100),
          throwsA(isA<InvalidRequest>()));
    });

    test('a purchase token credits coins only once', () async {
      final b = make(coins: 0);
      await b.verifyPurchase(productId: 'coins_10', purchaseToken: 'tok1');
      await b.verifyPurchase(productId: 'coins_10', purchaseToken: 'tok1');
      expect((await b.getProfile()).balanceCents, 10 * kCentsPerCoin);
      await b.verifyPurchase(productId: 'coins_10', purchaseToken: 'tok2');
      expect((await b.getProfile()).balanceCents, 20 * kCentsPerCoin);
    });

    test('a token cannot be replayed for a different product (same rule as the server)',
        () async {
      final b = make(coins: 0);
      await b.verifyPurchase(productId: 'coins_2', purchaseToken: 'tokX');
      expect(() => b.verifyPurchase(productId: 'coins_800', purchaseToken: 'tokX'),
          throwsA(isA<PurchaseRejected>()));
    });

    test('remove ads and paid skins unlock', () async {
      final b = make();
      final p1 = await b.verifyPurchase(productId: 'remove_ads', purchaseToken: 'a');
      expect(p1.removeAds, isTrue);
      final p2 = await b.verifyPurchase(productId: 'ball_fire', purchaseToken: 'b');
      expect(p2.owned, contains('ball_fire'));
    });

    test('buying a skin with coins', () async {
      final b = make(coins: 5);
      final p = await b.buyWithCoins('ball_ice');
      expect(p.owned, contains('ball_ice'));
      expect(p.balanceCents, 100);
      expect(() => b.buyWithCoins('ball_ghost'), throwsA(isA<InsufficientFunds>()));
      expect(() => b.buyWithCoins('ball_fire'), throwsA(isA<InvalidRequest>()));
    });
  });
}
