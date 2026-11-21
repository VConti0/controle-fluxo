/// Sign-in. Only needed to buy things and to bet coins; playing in practice
/// mode works signed out.
library;

import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../config.dart';

class AppUser {
  final String uid;
  final String? name;
  final String? email;
  const AppUser(this.uid, this.name, this.email);
}

class SignInCancelled implements Exception {
  const SignInCancelled();
}

abstract class AuthService {
  AppUser? get user;
  Stream<AppUser?> get changes;
  Future<AppUser> signInWithGoogle();
  Future<void> signOut();
}

class FirebaseAuthService implements AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  bool _googleReady = false;

  FirebaseAuthService() {
    if (AppConfig.useEmulators) {
      _auth.useAuthEmulator(AppConfig.emulatorHost, 9099);
    }
  }

  static AppUser? _map(User? u) => u == null ? null : AppUser(u.uid, u.displayName, u.email);

  @override
  AppUser? get user => _map(_auth.currentUser);

  @override
  Stream<AppUser?> get changes => _auth.authStateChanges().map(_map);

  Future<void> _ensureGoogle() async {
    if (_googleReady) return;
    await GoogleSignIn.instance.initialize(serverClientId: AppConfig.googleServerClientId);
    _googleReady = true;
  }

  @override
  Future<AppUser> signInWithGoogle() async {
    await _ensureGoogle();
    final GoogleSignInAccount account;
    try {
      account = await GoogleSignIn.instance.authenticate();
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) throw const SignInCancelled();
      rethrow;
    }
    final idToken = account.authentication.idToken;
    final cred = await _auth.signInWithCredential(GoogleAuthProvider.credential(idToken: idToken));
    return _map(cred.user)!;
  }

  @override
  Future<void> signOut() async {
    await _auth.signOut();
    if (_googleReady) await GoogleSignIn.instance.signOut();
  }
}

/// Offline builds and tests: signing in always succeeds as a demo user.
class FakeAuthService implements AuthService {
  final _controller = StreamController<AppUser?>.broadcast();
  AppUser? _user;

  FakeAuthService({AppUser? user}) : _user = user; // ignore: prefer_initializing_formals

  @override
  AppUser? get user => _user;

  @override
  Stream<AppUser?> get changes => _controller.stream;

  @override
  Future<AppUser> signInWithGoogle() async {
    _user = const AppUser('demo', 'Demo', 'demo@example.com');
    _controller.add(_user);
    return _user!;
  }

  @override
  Future<void> signOut() async {
    _user = null;
    _controller.add(null);
  }
}
