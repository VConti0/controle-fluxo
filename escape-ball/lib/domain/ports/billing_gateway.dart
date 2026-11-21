/// Store purchases (Google Play, or a fake for tests).
library;

enum PurchaseResult { purchased, restored, pending, cancelled, error }

class PurchaseUpdate {
  final String productId;
  final PurchaseResult result;

  /// Token to send to the server, for purchased/restored.
  final String? token;
  final String? error;

  /// Call after the server has credited the purchase: it acknowledges (or
  /// consumes, for coin packs) the purchase with the store. A purchase that
  /// is never completed is refunded by Google after 3 days.
  final Future<void> Function() complete;

  const PurchaseUpdate({
    required this.productId,
    required this.result,
    required this.complete,
    this.token,
    this.error,
  });
}

abstract interface class BillingGateway {
  Future<void> init({required Set<String> consumables, required Set<String> nonConsumables});

  /// Localised price strings from the store, by product id. Missing entries
  /// mean the store did not return that product (not set up yet).
  Map<String, String> get prices;

  Stream<PurchaseUpdate> get updates;

  Future<void> buy(String productId);

  /// Re-delivers owned purchases (and coin packs not yet consumed) on
  /// [updates].
  Future<void> restore();

  void dispose();
}
