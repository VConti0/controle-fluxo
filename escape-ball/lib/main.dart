import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart' show GlobalWidgetsLocalizations;
import 'package:material_ui/material_ui.dart';

import 'di/bootstrap.dart';
import 'presentation/app_state.dart';
import 'presentation/screens/common.dart';
import 'presentation/screens/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  final state = await bootstrap();
  runApp(EscapeBallApp(state: state));
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
