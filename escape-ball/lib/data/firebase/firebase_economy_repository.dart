import 'package:cloud_functions/cloud_functions.dart';

import '../../domain/economy/inventory.dart';
import '../../domain/economy/round_ticket.dart';
import '../../domain/failures.dart';
import '../../domain/game/arena.dart';
import '../../domain/ports/economy_repository.dart';

/// Calls the Cloud Functions in `functions/src/index.ts`.
class FirebaseEconomyRepository implements EconomyRepository {
  final FirebaseFunctions _fns;

  FirebaseEconomyRepository(this._fns);

  Future<Map<String, dynamic>> _call(String name, [Map<String, dynamic>? data]) async {
    try {
      final res = await _fns.httpsCallable(name).call<Object?>(data ?? const {});
      return Map<String, dynamic>.from(res.data as Map);
    } on FirebaseFunctionsException catch (e) {
      throw mapFunctionsError(e.code, e.message);
    } catch (e) {
      throw ServiceUnavailable('$e');
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

/// Translates the server's error codes (see `EconomyError` in
/// functions/src/domain/economy.ts) into domain failures.
Failure mapFunctionsError(String code, String? message) {
  final msg = message ?? code;
  switch (code) {
    case 'unauthenticated':
      return const NotSignedIn();
    case 'failed-precondition':
      if (msg == 'insufficient-funds') return const InsufficientFunds();
      if (msg == 'pending') return const PurchasePending();
      return InvalidRequest(msg);
    case 'permission-denied':
      return PurchaseRejected(msg);
    case 'invalid-argument':
    case 'not-found':
      return InvalidRequest(msg);
    default:
      return ServiceUnavailable(msg);
  }
}
