import '../economy/inventory.dart';
import '../failures.dart';
import '../ports/billing_gateway.dart';
import '../ports/economy_repository.dart';

sealed class PurchaseOutcome {
  const PurchaseOutcome();
}

/// The server credited it. [isNew] is false for restored purchases.
class PurchaseCredited extends PurchaseOutcome {
  final Profile profile;
  final String productId;
  final bool isNew;
  const PurchaseCredited(this.profile, this.productId, {required this.isNew});
}

class PurchaseAwaitingPayment extends PurchaseOutcome {
  const PurchaseAwaitingPayment();
}

/// Cancelled, refused by the store or by the server.
class PurchaseFailed extends PurchaseOutcome {
  final bool userVisible;
  const PurchaseFailed({required this.userVisible});
}

/// Left uncompleted so the store delivers it again (signed out, offline).
class PurchaseDeferred extends PurchaseOutcome {
  const PurchaseDeferred();
}

/// Turns a store purchase into coins or items: the server checks and credits
/// it first, and only then is it acknowledged with the store. If anything
/// fails before that, the purchase stays open and is retried on next launch.
class ProcessPurchase {
  final EconomyRepository? _economy;
  const ProcessPurchase(this._economy);

  Future<PurchaseOutcome> call(PurchaseUpdate u, {required bool signedIn}) async {
    switch (u.result) {
      case PurchaseResult.pending:
        return const PurchaseAwaitingPayment();
      case PurchaseResult.cancelled:
      case PurchaseResult.error:
        return const PurchaseFailed(userVisible: true);
      case PurchaseResult.purchased:
      case PurchaseResult.restored:
        break;
    }
    final economy = _economy;
    final token = u.token;
    if (economy == null || !signedIn || token == null) return const PurchaseDeferred();
    final isNew = u.result == PurchaseResult.purchased;
    try {
      final profile = await economy.verifyPurchase(productId: u.productId, purchaseToken: token);
      await u.complete();
      return PurchaseCredited(profile, u.productId, isNew: isNew);
    } on PurchasePending {
      return const PurchaseAwaitingPayment();
    } on Failure {
      return isNew ? const PurchaseFailed(userVisible: true) : const PurchaseDeferred();
    }
  }
}
