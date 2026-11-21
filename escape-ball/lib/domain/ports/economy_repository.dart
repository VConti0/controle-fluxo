import '../economy/inventory.dart';
import '../economy/round_ticket.dart';
import '../game/arena.dart';

/// Balance, bets and purchases. The real implementation talks to the Cloud
/// Functions; the offline one applies the same rules on the device.
///
/// Every method throws a `Failure` (see `failures.dart`) on error.
abstract interface class EconomyRepository {
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
