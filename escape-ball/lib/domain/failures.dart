/// Typed failures the rest of the app can switch on. Data-layer
/// implementations translate their own errors (Firebase codes, plugin
/// exceptions) into these, so screens never look at error text.
library;

sealed class Failure implements Exception {
  final String detail;
  const Failure(this.detail);

  @override
  String toString() => '$runtimeType($detail)';
}

/// The player does not have enough coins for a bet or an item.
class InsufficientFunds extends Failure {
  const InsufficientFunds() : super('insufficient-funds');
}

/// The request was malformed (unknown item, bet out of range...).
class InvalidRequest extends Failure {
  const InvalidRequest(super.detail);
}

/// The store did not confirm a purchase, or the token was already used.
class PurchaseRejected extends Failure {
  const PurchaseRejected(super.detail);
}

/// Payment started but not approved yet (e.g. boleto). Credited later.
class PurchasePending extends Failure {
  const PurchasePending() : super('pending');
}

/// The action needs a signed-in player.
class NotSignedIn extends Failure {
  const NotSignedIn() : super('unauthenticated');
}

/// The player closed the sign-in screen.
class SignInCancelled extends Failure {
  const SignInCancelled() : super('cancelled');
}

/// Network down, server error, or anything else worth a retry.
class ServiceUnavailable extends Failure {
  const ServiceUnavailable(super.detail);
}
