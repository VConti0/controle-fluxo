// Private fields set from named parameters: Dart does not allow private
// named initializing formals.
// ignore_for_file: prefer_initializing_formals

import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../../domain/account/app_user.dart';
import '../../domain/failures.dart';
import '../../domain/ports/auth_repository.dart';

class FirebaseAuthRepository implements AuthRepository {
  final FirebaseAuth _auth;
  final GoogleSignIn _google;
  final String _serverClientId;
  bool _googleReady = false;

  FirebaseAuthRepository(this._auth, this._google, {required String serverClientId})
      : _serverClientId = serverClientId;

  static AppUser? _map(User? u) => u == null ? null : AppUser(u.uid, u.displayName, u.email);

  @override
  AppUser? get user => _map(_auth.currentUser);

  @override
  Stream<AppUser?> get changes => _auth.authStateChanges().map(_map);

  Future<void> _ensureGoogle() async {
    if (_googleReady) return;
    await _google.initialize(serverClientId: _serverClientId);
    _googleReady = true;
  }

  @override
  Future<AppUser> signInWithGoogle() async {
    try {
      await _ensureGoogle();
      final account = await _google.authenticate();
      final idToken = account.authentication.idToken;
      final cred = await _auth.signInWithCredential(GoogleAuthProvider.credential(idToken: idToken));
      return _map(cred.user)!;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) throw const SignInCancelled();
      throw ServiceUnavailable(e.description ?? e.code.name);
    } on FirebaseAuthException catch (e) {
      throw ServiceUnavailable(e.code);
    }
  }

  @override
  Future<void> signOut() async {
    await _auth.signOut();
    if (_googleReady) await _google.signOut();
  }
}
