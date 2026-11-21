/// Google Play Billing through the `in_app_purchase` plugin.
library;

import 'dart:async';

import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:in_app_purchase_android/in_app_purchase_android.dart';

import '../../domain/ports/billing_gateway.dart';

class PlayBillingGateway implements BillingGateway {
  final InAppPurchase _iap;
  final _controller = StreamController<PurchaseUpdate>.broadcast();
  final Map<String, ProductDetails> _details = {};
  final Map<String, String> _prices = {};
  Set<String> _consumables = {};
  StreamSubscription<List<PurchaseDetails>>? _sub;

  PlayBillingGateway(this._iap);

  @override
  Map<String, String> get prices => _prices;

  @override
  Stream<PurchaseUpdate> get updates => _controller.stream;

  @override
  Future<void> init({required Set<String> consumables, required Set<String> nonConsumables}) async {
    _consumables = consumables;
    _sub = _iap.purchaseStream.listen(_onPurchases, onError: (Object e) {
      _controller.add(PurchaseUpdate(
        productId: '',
        result: PurchaseResult.error,
        error: '$e',
        complete: () async {},
      ));
    });
    if (!await _iap.isAvailable()) return;
    final res = await _iap.queryProductDetails({...consumables, ...nonConsumables});
    for (final d in res.productDetails) {
      _details[d.id] = d;
      _prices[d.id] = d.price;
    }
  }

  void _onPurchases(List<PurchaseDetails> list) {
    for (final p in list) {
      final result = switch (p.status) {
        PurchaseStatus.purchased => PurchaseResult.purchased,
        PurchaseStatus.restored => PurchaseResult.restored,
        PurchaseStatus.pending => PurchaseResult.pending,
        PurchaseStatus.canceled => PurchaseResult.cancelled,
        PurchaseStatus.error => PurchaseResult.error,
      };
      _controller.add(PurchaseUpdate(
        productId: p.productID,
        result: result,
        token: p.verificationData.serverVerificationData,
        error: p.error?.message,
        complete: () => _complete(p),
      ));
    }
  }

  Future<void> _complete(PurchaseDetails p) async {
    if (_consumables.contains(p.productID)) {
      // Consuming also acknowledges, and lets the player buy the pack again.
      final android = _iap.getPlatformAddition<InAppPurchaseAndroidPlatformAddition>();
      await android.consumePurchase(p);
    } else if (p.pendingCompletePurchase) {
      await _iap.completePurchase(p);
    }
  }

  @override
  Future<void> buy(String productId) async {
    final details = _details[productId];
    if (details == null) {
      _controller.add(PurchaseUpdate(
        productId: productId,
        result: PurchaseResult.error,
        error: 'product-not-found',
        complete: () async {},
      ));
      return;
    }
    final param = PurchaseParam(productDetails: details);
    if (_consumables.contains(productId)) {
      // Consumed only after the server credits the coins (see _complete).
      await _iap.buyConsumable(purchaseParam: param, autoConsume: false);
    } else {
      await _iap.buyNonConsumable(purchaseParam: param);
    }
  }

  @override
  Future<void> restore() => _iap.restorePurchases();

  @override
  void dispose() {
    _sub?.cancel();
    _controller.close();
  }
}
