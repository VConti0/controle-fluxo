import '../account/app_user.dart';

/// Sign-in. Only needed to buy things and to bet coins.
abstract interface class AuthRepository {
  AppUser? get user;
  Stream<AppUser?> get changes;

  /// Throws `SignInCancelled` if the player closes the sign-in screen.
  Future<AppUser> signInWithGoogle();
  Future<void> signOut();
}
