import 'package:flame/game.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../game/arena.dart';
import '../game/escape_game.dart';
import '../game/round.dart';
import '../game/skins.dart';
import '../l10n/strings.dart';
import '../services/backend.dart';
import 'common.dart';
import 'result_screen.dart';

/// Replays the round the server picked. No ads here.
class PlayScreen extends StatefulWidget {
  final RoundTicket ticket;
  final String ball;
  final String map;
  const PlayScreen({super.key, required this.ticket, required this.ball, required this.map});

  @override
  State<PlayScreen> createState() => _PlayScreenState();
}

class _PlayScreenState extends State<PlayScreen> {
  late final EscapeGame _game;
  double _speed = 1;
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _game = EscapeGame(
      sim: RoundSim(ArenaSpec.fromSeed(widget.ticket.seed, widget.ticket.shape)),
      ball: ballSkin(widget.ball),
      map: mapSkin(widget.map),
      onEvent: _onEvent,
    );
  }

  void _onEvent(SimEvent e) {
    switch (e.type) {
      case SimEventType.death:
      case SimEventType.timeout:
        HapticFeedback.lightImpact();
      case SimEventType.escape:
      case SimEventType.shatter:
        HapticFeedback.heavyImpact();
        _finish();
      default:
        break;
    }
  }

  Future<void> _finish() async {
    if (_done) return;
    _done = true;
    // The ball's escape attempt should match the server's; if a device ever
    // replays it differently, the server's result is what counts and shows.
    await Future<void>.delayed(const Duration(milliseconds: 1800));
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
      builder: (_) => ResultScreen(ticket: widget.ticket, replayedAttempt: _game.sim.escapedOn),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      backgroundColor: mapSkin(widget.map).background,
      body: SafeArea(
        child: Stack(
          children: [
            Positioned.fill(child: GameWidget(game: _game)),
            Positioned(
              left: 16,
              right: 16,
              top: 24,
              child: ValueListenableBuilder<HudState>(
                valueListenable: _game.hud,
                builder: (context, hud, _) => Column(
                  children: [
                    NeonTitle(
                      hud.finished ? (hud.shattered ? s.shattered : s.escaped) : s.bigTitle,
                      size: 40,
                    ),
                    const SizedBox(height: 16),
                    ProgressSegments(filled: (hud.attempt - 1).clamp(0, 8)),
                    const SizedBox(height: 10),
                    Text(
                      s.attempt(hud.attempt),
                      style: const TextStyle(
                          letterSpacing: 4, color: Colors.white70, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              right: 12,
              bottom: 12,
              child: TextButton.icon(
                onPressed: () => setState(() {
                  _speed = _speed == 1 ? 2 : (_speed == 2 ? 4 : 1);
                  _game.speed = _speed;
                }),
                icon: const Icon(Icons.fast_forward),
                label: Text('${_speed.toInt()}×'),
              ),
            ),
            Positioned(
              left: 4,
              top: 4,
              child: IconButton(
                icon: const Icon(Icons.close),
                onPressed: () {
                  // Leaving early does not change the result: show it now.
                  _done = true;
                  Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
                    builder: (_) => ResultScreen(ticket: widget.ticket, replayedAttempt: null),
                  ));
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
