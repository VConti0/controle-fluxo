import 'dart:convert';
import 'dart:io';

import 'package:escapeball/data/firebase/firebase_economy_repository.dart';
import 'package:escapeball/data/local/local_economy_repository.dart';
import 'package:escapeball/domain/economy/bet.dart';
import 'package:escapeball/domain/economy/catalog.dart';
import 'package:escapeball/domain/economy/inventory.dart';
import 'package:escapeball/domain/economy/round_ticket.dart';
import 'package:escapeball/domain/failures.dart';
import 'package:escapeball/domain/game/arena.dart';
import 'package:escapeball/domain/ports/billing_gateway.dart';
import 'package:escapeball/domain/ports/economy_repository.dart';
import 'package:escapeball/domain/usecases/bet_options.dart';
import 'package:escapeball/domain/usecases/play_round.dart';
import 'package:escapeball/domain/usecases/process_purchase.dart';
import 'package:flutter_test/flutter_test.dart';

Catalog _catalog() => Catalog.fromJson(
    jsonDecode(File('assets/data/catalog.json').readAsStringSync()) as Map<String, dynamic>);

OddsTable _odds() => OddsTable.fromJson(
    jsonDecode(File('assets/data/odds.json').readAsStringSync()) as Map<String, dynamic>);

/// Economy whose verifyPurchase fails with a chosen failure.
class _FailingEconomy implements EconomyRepository {
  final Failure failure;
  _FailingEconomy(this.failure);

  @override
  Future<Profile> verifyPurchase({required String productId, required String purchaseToken}) =>
      Future.error(failure);

  @override
  dynamic noSuchMethod(Invocation invocation) => throw UnimplementedError();
}

PurchaseUpdate _update(PurchaseResult r, {String product = 'coins_10', String? token = 't1'}) {
  var completed = 0;
  late final PurchaseUpdate u;
  u = PurchaseUpdate(
    productId: product,
    result: r,
    token: token,
    complete: () async => completed++,
  );
  _completions[u] = () => completed;
  return u;
}

final _completions = Expando<int Function()>();
int _completedCount(PurchaseUpdate u) => _completions[u]!();

void main() {
  group('ProcessPurchase', () {
    test('credits, then completes with the store', () async {
      final economy = LocalEconomyRepository(catalog: _catalog(), odds: _odds(), initial: Profile.empty);
      final u = _update(PurchaseResult.purchased);
      final out = await ProcessPurchase(economy)(u, signedIn: true);
      expect(out, isA<PurchaseCredited>());
      expect((out as PurchaseCredited).profile.balanceCents, 10 * kCentsPerCoin);
      expect(out.isNew, isTrue);
      expect(_completedCount(u), 1);
    });

    test('signed out or no server: left open so the store redelivers it', () async {
      final economy = LocalEconomyRepository(catalog: _catalog(), odds: _odds());
      final u = _update(PurchaseResult.purchased);
      expect(await ProcessPurchase(economy)(u, signedIn: false), isA<PurchaseDeferred>());
      expect(await const ProcessPurchase(null)(u, signedIn: true), isA<PurchaseDeferred>());
      expect(_completedCount(u), 0);
    });

    test('server refusal is shown for new purchases and retried silently for restores', () async {
      final economy = _FailingEconomy(const ServiceUnavailable('offline'));
      final fresh = _update(PurchaseResult.purchased);
      final restored = _update(PurchaseResult.restored);
      expect(await ProcessPurchase(economy)(fresh, signedIn: true),
          isA<PurchaseFailed>().having((f) => f.userVisible, 'userVisible', true));
      expect(await ProcessPurchase(economy)(restored, signedIn: true), isA<PurchaseDeferred>());
      expect(_completedCount(fresh) + _completedCount(restored), 0);
    });

    test('pending payments are reported, not completed', () async {
      final u = _update(PurchaseResult.pending);
      expect(await const ProcessPurchase(null)(u, signedIn: true), isA<PurchaseAwaitingPayment>());
      final viaServer = _update(PurchaseResult.purchased);
      expect(await ProcessPurchase(_FailingEconomy(const PurchasePending()))(viaServer, signedIn: true),
          isA<PurchaseAwaitingPayment>());
      expect(_completedCount(viaServer), 0);
    });
  });

  group('PlayRound', () {
    test('practice when signed out, betting zero, or without a server', () async {
      final economy = LocalEconomyRepository(catalog: _catalog(), odds: _odds());
      final play = PlayRound(economy);
      for (final (cents, signedIn) in [(0, true), (100, false)]) {
        final t = await play(shape: ArenaShape.square, band: 1, betCents: cents, signedIn: signedIn);
        expect(t.practice, isTrue);
        expect(t.balanceCents, isNull);
      }
      final offline = await PlayRound(null)(shape: ArenaShape.square, band: 1, betCents: 100, signedIn: true);
      expect(offline.practice, isTrue);
      expect((await economy.getProfile()).balanceCents, 20 * kCentsPerCoin);
    });

    test('a real bet goes through the economy', () async {
      final economy = LocalEconomyRepository(catalog: _catalog(), odds: _odds());
      final RoundTicket t =
          await PlayRound(economy)(shape: ArenaShape.square, band: 1, betCents: 100, signedIn: true);
      expect(t.practice, isFalse);
      expect(t.balanceCents, (await economy.getProfile()).balanceCents);
    });
  });

  group('BetOptions', () {
    test('choices respect the catalog limits and affordability', () {
      final o = BetOptions(_catalog());
      expect(o.coinChoices.first, greaterThanOrEqualTo(1));
      expect(o.coinChoices.last, lessThanOrEqualTo(100));
      expect(o.stakeCents(coins: 5, practice: false), 500);
      expect(o.stakeCents(coins: 5, practice: true), 0);
      expect(o.canAfford(const Profile(balanceCents: 400), 500), isFalse);
      expect(o.canAfford(const Profile(balanceCents: 500), 500), isTrue);
      expect(o.canAfford(Profile.empty, 0), isTrue);
    });
  });

  group('server error mapping', () {
    test('maps Cloud Functions codes to typed failures', () {
      expect(mapFunctionsError('failed-precondition', 'insufficient-funds'), isA<InsufficientFunds>());
      expect(mapFunctionsError('failed-precondition', 'pending'), isA<PurchasePending>());
      expect(mapFunctionsError('permission-denied', 'already-used'), isA<PurchaseRejected>());
      expect(mapFunctionsError('unauthenticated', null), isA<NotSignedIn>());
      expect(mapFunctionsError('invalid-argument', 'bet'), isA<InvalidRequest>());
      expect(mapFunctionsError('internal', 'boom'), isA<ServiceUnavailable>());
    });
  });
}
