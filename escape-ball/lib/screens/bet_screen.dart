import 'package:material_ui/material_ui.dart';

import '../app_state.dart';
import '../economy/bet.dart';
import '../l10n/strings.dart';
import '../services/auth_service.dart';
import '../services/backend.dart';
import 'common.dart';
import 'play_screen.dart';
import 'store_screen.dart';

class BetScreen extends StatefulWidget {
  const BetScreen({super.key});

  @override
  State<BetScreen> createState() => _BetScreenState();
}

class _BetScreenState extends State<BetScreen> {
  int _band = 1;
  int _betCoins = 1;
  bool _practice = false;
  bool _starting = false;

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    final odds = app.odds.shapes[app.roundShape.name]!;
    final practice = _practice || !app.canBet;
    final bets = [
      for (final b in kBetCoins)
        if (b >= app.catalog.minBetCoins && b <= app.catalog.maxBetCoins) b,
    ];
    final betCents = practice ? 0 : _betCoins * kCentsPerCoin;
    final enough = practice || app.profile.balanceCents >= betCents;

    return Scaffold(
      appBar: AppBar(title: Text(s.play), actions: const [Padding(padding: EdgeInsets.only(right: 12), child: CoinChip())]),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(s.guessTitle,
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  Text(s.guessHint, style: const TextStyle(color: Colors.white60)),
                  const SizedBox(height: 16),
                  for (final b in kBands)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _BandTile(
                        label: s.attemptsLabel(b.label),
                        probability: odds.probabilities[b.index],
                        multiplier: odds.multipliers[b.index],
                        selected: _band == b.index,
                        showMultiplier: !practice,
                        onTap: () => setState(() => _band = b.index),
                      ),
                    ),
                  const SizedBox(height: 12),
                  if (!app.signedIn) ...[
                    Text(s.signInWhy, style: const TextStyle(color: Colors.white70)),
                    const SizedBox(height: 8),
                    NeonButton(
                      label: s.signIn,
                      icon: Icons.login,
                      primary: false,
                      onPressed: () => _signIn(context),
                    ),
                  ] else if (app.canBet) ...[
                    Row(
                      children: [
                        Text(s.bet, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                        const Spacer(),
                        Text(s.practice),
                        Switch(value: _practice, onChanged: (v) => setState(() => _practice = v)),
                      ],
                    ),
                    if (!_practice)
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final c in bets)
                            ChoiceChip(
                              label: Text('$c'),
                              selected: _betCoins == c,
                              onSelected: (_) => setState(() => _betCoins = c),
                            ),
                        ],
                      ),
                    if (!_practice && !enough) ...[
                      const SizedBox(height: 8),
                      Text(s.notEnoughCoins, style: const TextStyle(color: Colors.orangeAccent)),
                      TextButton(
                        onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                            builder: (_) => const StoreScreen(initialTab: 0))),
                        child: Text(s.buyCoins),
                      ),
                    ],
                    const SizedBox(height: 8),
                    Text(s.ageNotice, style: const TextStyle(color: Colors.white38, fontSize: 12)),
                  ],
                  if (practice)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(s.practiceMode, style: const TextStyle(color: Colors.white54)),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: NeonButton(
                label: s.start,
                icon: Icons.sports_baseball,
                onPressed: (!enough || _starting) ? null : () => _start(context, betCents),
              ),
            ),
            const BannerSlot(),
          ],
        ),
      ),
    );
  }

  Future<void> _signIn(BuildContext context) async {
    final s = S.of(context);
    try {
      await AppScope.read(context).signIn();
    } on SignInCancelled {
      return;
    } catch (_) {
      if (context.mounted) showSnack(context, s.genericError);
    }
  }

  Future<void> _start(BuildContext context, int betCents) async {
    final app = AppScope.read(context);
    final s = S.of(context);
    setState(() => _starting = true);
    try {
      final ticket = await app.startRound(band: _band, betCents: betCents);
      if (!context.mounted) return;
      await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => PlayScreen(ticket: ticket, ball: app.roundBall, map: app.roundMap),
      ));
    } on BackendException catch (e) {
      if (context.mounted) {
        showSnack(context, e.message == 'insufficient-funds' ? s.notEnoughCoins : s.genericError);
      }
    } catch (_) {
      if (context.mounted) showSnack(context, s.genericError);
    } finally {
      if (mounted) setState(() => _starting = false);
    }
  }
}

class _BandTile extends StatelessWidget {
  final String label;
  final double probability;
  final double multiplier;
  final bool selected;
  final bool showMultiplier;
  final VoidCallback onTap;

  const _BandTile({
    required this.label,
    required this.probability,
    required this.multiplier,
    required this.selected,
    required this.showMultiplier,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? const Color(0xFF15301F) : kCard,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: selected ? kNeon : const Color(0xFF1C2B24), width: selected ? 2 : 1),
          ),
          child: Row(
            children: [
              Icon(selected ? Icons.radio_button_checked : Icons.radio_button_off,
                  color: selected ? kNeon : Colors.white38),
              const SizedBox(width: 12),
              Expanded(
                child: Text(label, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ),
              Text('${(probability * 100).round()}%', style: const TextStyle(color: Colors.white54)),
              if (showMultiplier) ...[
                const SizedBox(width: 12),
                SizedBox(
                  width: 64,
                  child: Text(
                    '×${multiplier.toStringAsFixed(2).replaceAll('.', ',')}',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                        color: Color(0xFFFFD34D), fontWeight: FontWeight.w800, fontSize: 16),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
