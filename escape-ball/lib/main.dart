import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart' show GlobalWidgetsLocalizations;
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app_state.dart';
import 'config.dart';
import 'screens/common.dart';
import 'screens/home_screen.dart';
import 'services/auth_service.dart';
import 'services/backend.dart';
import 'services/billing_service.dart';
import 'services/ads_service.dart';
import 'services/platform_services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  final app = await bootstrap();
  runApp(EscapeBallApp(state: app));
}

/// Builds the app state with real services when Firebase is configured, and
/// falls back to an offline demo (web) or practice-only mode (Firebase not
/// set up yet) otherwise.
Future<AppState> bootstrap() async {
  final (catalog, odds) = await AppState.loadData();
  SharedPreferences? prefs;
  try {
    prefs = await SharedPreferences.getInstance();
  } catch (_) {}

  if (kIsWeb || AppConfig.offline) {
    final state = AppState(
      catalog: catalog,
      odds: odds,
      auth: FakeAuthService(),
      backend: LocalBackend(catalog: catalog, odds: odds),
      billing: FakeBillingService(),
      ads: const NoAdsService(),
      demo: true,
      prefs: prefs,
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

  final ads = createAdsService();
  final state = AppState(
    catalog: catalog,
    odds: odds,
    auth: firebaseOk ? FirebaseAuthService() : FakeAuthService(),
    backend: firebaseOk ? FirebaseBackend() : null,
    billing: firebaseOk ? createBillingService() : FakeBillingService(),
    ads: ads,
    demo: !firebaseOk,
    serverMissing: !firebaseOk,
    prefs: prefs,
  );
  // Consent and ads load in the background so the menu shows immediately.
  ads.init();
  await state.init();
  return state;
}

class EscapeBallApp extends StatelessWidget {
  final AppState state;
  const EscapeBallApp({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    return AppScope(
      state: state,
      child: MaterialApp(
        onGenerateTitle: (context) =>
            Localizations.localeOf(context).languageCode == 'pt' ? 'Vai Escapar?' : 'Will It Escape?',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        supportedLocales: const [Locale('pt', 'BR'), Locale('en')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
        ],
        home: const HomeScreen(),
      ),
    );
  }
}
