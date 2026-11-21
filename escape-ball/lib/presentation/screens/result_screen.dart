import 'package:material_ui/material_ui.dart';

import '../../domain/economy/bet.dart';
import '../../domain/economy/round_ticket.dart';
import '../app_state.dart';
import '../l10n/strings.dart';
import 'common.dart';

class ResultScreen extends StatelessWidget {
  final RoundTicket ticket;

  /// Attempt the phone's replay escaped on, for diagnostics.
  final int? replayedAttempt;
  const ResultScreen({super.key, required this.ticket, required this.replayedAttempt});

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final app = AppScope.of(context);
    final t = ticket;
    final won = t.won;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    NeonTitle(s.escapedOn(t.attempt), size: 30),
                    const SizedBox(height: 24),
                    Icon(won ? Icons.emoji_events : Icons.sentiment_neutral,
                        size: 72, color: won ? const Color(0xFFFFD34D) : Colors.white38),
                    const SizedBox(height: 12),
                    Text(won ? s.youWon : s.youLost,
                        style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 8),
                    Text(s.yourGuess(kBands[t.band].label),
                        style: const TextStyle(color: Colors.white70, fontSize: 16)),
                    if (!t.practice) ...[
                      const SizedBox(height: 16),
                      if (t.payoutCents > 0)
                        Text(s.won(formatCoins(t.payoutCents)),
                            style: const TextStyle(
                                color: Color(0xFFFFD34D), fontSize: 28, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 8),
                      Text(s.balance(formatCoins(app.profile.balanceCents)),
                          style: const TextStyle(color: Colors.white60)),
                    ],
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
              child: Column(
                children: [
                  NeonButton(
                    label: s.playAgain,
                    icon: Icons.replay,
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const SizedBox(height: 10),
                  NeonButton(
                    label: s.menu,
                    primary: false,
                    onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
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
}
