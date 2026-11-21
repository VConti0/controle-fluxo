import 'dart:async';

import '../../domain/account/app_user.dart';
import '../../domain/ports/auth_repository.dart';

/// Offline builds and tests: signing in always succeeds as a demo user.
class FakeAuthRepository implements AuthRepository {
  final _controller = StreamController<AppUser?>.broadcast();
  AppUser? _user;

  FakeAuthRepository({AppUser? signedInAs}) : _user = signedInAs;

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
