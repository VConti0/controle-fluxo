import 'dart:math' as math;

import 'package:flame/game.dart';
import 'package:material_ui/material_ui.dart';

import '../../domain/game/arena.dart';
import '../../domain/game/round.dart';
import '../app_state.dart';
import '../game_view/escape_game.dart';
import '../game_view/skins.dart';
import '../l10n/strings.dart';
import 'bet_screen.dart';
import 'common.dart';
import 'settings_screen.dart';
import 'store_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  EscapeGame? _preview;
  String? _previewKey;

  EscapeGame _game(AppState app) {
    final key = '${app.inventory.ball}/${app.inventory.map}';
    if (_preview == null || _previewKey != key) {
      final map = mapSkin(app.inventory.map);
      _previewKey = key;
      _preview = EscapeGame(
        sim: RoundSim(ArenaSpec.fromSeed(math.Random().nextInt(0x7fffffff) + 1, map.shape)),
        ball: ballSkin(app.inventory.ball),
        map: map,
        loop: true,
      );
    }
    return _preview!;
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    return Scaffold(
      backgroundColor: mapSkin(app.inventory.map).background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
              child: Row(
                children: [
                  CoinChip(onTap: () => _open(context, const StoreScreen(initialTab: 0))),
                  const Spacer(),
                  IconButton(
                    tooltip: s.store,
                    icon: const Icon(Icons.storefront),
                    onPressed: () => _open(context, const StoreScreen()),
                  ),
                  IconButton(
                    tooltip: s.settings,
                    icon: const Icon(Icons.settings),
                    onPressed: () => _open(context, const SettingsScreen()),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: NeonTitle(s.bigTitle, size: 44),
            ),
            Expanded(
              child: IgnorePointer(child: GameWidget(game: _game(app))),
            ),
            if (app.isDemo)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  app.serverMissing ? s.firebaseMissing : s.offlineNotice,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white54, fontSize: 12),
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 8),
              child: Column(
                children: [
                  NeonButton(
                    label: s.play,
                    icon: Icons.play_arrow_rounded,
                    onPressed: () => _open(context, const BetScreen()),
                  ),
                  const SizedBox(height: 10),
                  NeonButton(
                    label: s.store,
                    icon: Icons.palette_outlined,
                    primary: false,
                    onPressed: () => _open(context, const StoreScreen()),
                  ),
                ],
              ),
            ),
            const BannerSlot(),
          ],
        ),
      ),
    );
  }

  void _open(BuildContext context, Widget screen) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => screen));
  }
}
