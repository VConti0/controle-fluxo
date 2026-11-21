import 'dart:async';

import '../../domain/ports/billing_gateway.dart';

/// Simulated store: every purchase succeeds instantly and costs nothing.
/// Enabled with `--dart-define=FAKE_BILLING=true` and in offline builds. The
/// server only accepts these tokens when ALLOW_FAKE_PURCHASES is set.
class FakeBillingGateway implements BillingGateway {
  final _controller = StreamController<PurchaseUpdate>.broadcast();
  Set<String> _all = {};

  @override
  Future<void> init({required Set<String> consumables, required Set<String> nonConsumables}) async {
    _all = {...consumables, ...nonConsumables};
  }

  @override
  Map<String, String> get prices => const {};

  @override
  Stream<PurchaseUpdate> get updates => _controller.stream;

  @override
  Future<void> buy(String productId) async {
    final known = _all.contains(productId);
    _controller.add(PurchaseUpdate(
      productId: productId,
      result: known ? PurchaseResult.purchased : PurchaseResult.error,
      token: known ? 'fake:$productId:${DateTime.now().microsecondsSinceEpoch}' : null,
      error: known ? null : 'unknown product',
      complete: () async {},
    ));
  }

  @override
  Future<void> restore() async {}

  @override
  void dispose() => _controller.close();
}
