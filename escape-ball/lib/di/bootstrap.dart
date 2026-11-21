/// Composition root: the only place that knows which implementation backs
/// each port. Everything else depends on `domain/` interfaces.
library;

import 'package:cloud_functions/cloud_functions.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart' show rootBundle;
import 'package:google_sign_in/google_sign_in.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';
import '../data/ads/no_ads.dart';
import '../data/billing/fake_billing_gateway.dart';
import '../data/firebase/firebase_auth_repository.dart';
import '../data/firebase/firebase_economy_repository.dart';
import '../data/local/fake_auth_repository.dart';
import '../data/local/local_economy_repository.dart';
import '../data/storage/asset_data_source.dart';
import '../data/storage/shared_prefs_store.dart';
import '../domain/ports/preferences_store.dart';
import '../presentation/app_state.dart';
import 'platform_services.dart';

/// Builds the app state with real services when Firebase is configured, and
/// falls back to an offline demo (web, `OFFLINE=true`) or practice-only mode
/// (Firebase not set up yet) otherwise.
Future<AppState> bootstrap() async {
  final assets = AssetDataSource(rootBundle);
  final catalog = await assets.catalog();
  final odds = await assets.odds();
  PreferencesStore prefs;
  try {
    prefs = SharedPrefsStore(await SharedPreferences.getInstance());
  } catch (_) {
    prefs = MemoryPrefsStore();
  }

  if (kIsWeb || AppConfig.offline) {
    final state = AppState(
      catalog: catalog,
      odds: odds,
      auth: FakeAuthRepository(),
      economy: LocalEconomyRepository(catalog: catalog, odds: odds),
      billing: FakeBillingGateway(),
      ads: const NoAds(),
      bannerBuilder: () => const SizedBox.shrink(),
      prefs: prefs,
      mode: AppMode.demo,
    );
    await state.init();
    return state;
  }

  var firebaseOk = true;
  try {
    // Reads android/app/google-services.json.
    await Firebase.initializeApp();
  } catch (_) {
    firebaseOk = false;
  }

  final (ads, banner) = createAds(offline: false);
  final AppState state;
  if (firebaseOk) {
    final auth = FirebaseAuth.instance;
    final functions = FirebaseFunctions.instanceFor(region: AppConfig.functionsRegion);
    if (AppConfig.useEmulators) {
      auth.useAuthEmulator(AppConfig.emulatorHost, 9099);
      functions.useFunctionsEmulator(AppConfig.emulatorHost, 5001);
    }
    state = AppState(
      catalog: catalog,
      odds: odds,
      auth: FirebaseAuthRepository(auth, GoogleSignIn.instance,
          serverClientId: AppConfig.googleServerClientId),
      economy: FirebaseEconomyRepository(functions),
      billing: createBilling(fake: AppConfig.fakeBilling),
      ads: ads,
      bannerBuilder: banner,
      prefs: prefs,
      mode: AppMode.online,
    );
  } else {
    state = AppState(
      catalog: catalog,
      odds: odds,
      auth: FakeAuthRepository(),
      economy: null,
      billing: FakeBillingGateway(),
      ads: ads,
      bannerBuilder: banner,
      prefs: prefs,
      mode: AppMode.serverMissing,
    );
  }
  // Consent and ads load in the background so the menu shows immediately.
  ads.init();
  await state.init();
  return state;
}
