/// Store purchases. The Play Store implementation is in `billing_play.dart`;
/// this file holds the interface and the fake used for testing.
library;

import 'dart:async';

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

abstract class BillingService {
  Future<void> init({required Set<String> consumables, required Set<String> nonConsumables});

  bool get available;

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

/// Simulated store: every purchase succeeds instantly and costs nothing.
/// Enabled with `--dart-define=FAKE_BILLING=true` and in offline builds.
class FakeBillingService implements BillingService {
  final _controller = StreamController<PurchaseUpdate>.broadcast();
  final Map<String, String> _prices = {};
  Set<String> _all = {};

  @override
  Future<void> init({required Set<String> consumables, required Set<String> nonConsumables}) async {
    _all = {...consumables, ...nonConsumables};
  }

  @override
  bool get available => true;

  @override
  Map<String, String> get prices => _prices;

  @override
  Stream<PurchaseUpdate> get updates => _controller.stream;

  @override
  Future<void> buy(String productId) async {
    if (!_all.contains(productId)) {
      _controller.add(PurchaseUpdate(
        productId: productId,
        result: PurchaseResult.error,
        error: 'unknown product',
        complete: () async {},
      ));
      return;
    }
    _controller.add(PurchaseUpdate(
      productId: productId,
      result: PurchaseResult.purchased,
      token: 'fake:$productId:${DateTime.now().microsecondsSinceEpoch}',
      complete: () async {},
    ));
  }

  @override
  Future<void> restore() async {}

  @override
  void dispose() => _controller.close();
}
