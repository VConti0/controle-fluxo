/// Shared look: neon title, progress bar, coin chip, buttons, banner slot.
library;

import 'package:material_ui/material_ui.dart';

import '../../domain/economy/bet.dart';
import '../app_state.dart';
import '../l10n/strings.dart';

const kNeon = Color(0xFF7CFFB0);
const kNeonDim = Color(0xFF2E6B4F);
const kBg = Color(0xFF060D0A);
const kCard = Color(0xFF0E1A15);

ThemeData buildTheme() {
  final base = ThemeData(
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(
      seedColor: kNeon,
      brightness: Brightness.dark,
      surface: kBg,
    ),
    scaffoldBackgroundColor: kBg,
    useMaterial3: true,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(backgroundColor: kBg, elevation: 0, centerTitle: true),
    cardTheme: const CardThemeData(color: kCard, margin: EdgeInsets.zero),
  );
}

class NeonTitle extends StatelessWidget {
  final String text;
  final double size;
  const NeonTitle(this.text, {super.key, this.size = 40});

  @override
  Widget build(BuildContext context) {
    return FittedBox(
      fit: BoxFit.scaleDown,
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: TextStyle(
          fontSize: size,
          fontWeight: FontWeight.w900,
          letterSpacing: 1.5,
          color: const Color(0xFFF2FFF7),
          shadows: const [
            Shadow(color: kNeon, blurRadius: 18),
            Shadow(color: kNeon, blurRadius: 6),
          ],
        ),
      ),
    );
  }
}

/// Eight segments that fill as the opening widens, one per failed attempt.
class ProgressSegments extends StatelessWidget {
  final int filled;
  const ProgressSegments({super.key, required this.filled});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < 8; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            width: 30,
            height: 14,
            margin: const EdgeInsets.symmetric(horizontal: 2.5),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4),
              color: i < filled ? const Color(0xFFA6F24A) : const Color(0xFF101C22),
              border: Border.all(color: const Color(0xFF26343C)),
              boxShadow: i < filled
                  ? const [BoxShadow(color: Color(0x88A6F24A), blurRadius: 8)]
                  : const [],
            ),
          ),
      ],
    );
  }
}

class CoinChip extends StatelessWidget {
  final VoidCallback? onTap;
  const CoinChip({super.key, this.onTap});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    final label = app.signedIn ? formatCoins(app.profile.balanceCents) : s.practice;
    return ActionChip(
      onPressed: onTap,
      avatar: Icon(app.signedIn ? Icons.monetization_on : Icons.sports_esports,
          color: const Color(0xFFFFD34D), size: 18),
      label: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
      backgroundColor: kCard,
      side: const BorderSide(color: kNeonDim),
    );
  }
}

class NeonButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool primary;
  const NeonButton(
      {super.key, required this.label, this.onPressed, this.icon, this.primary = true});

  @override
  Widget build(BuildContext context) {
    final style = primary
        ? FilledButton.styleFrom(
            backgroundColor: kNeon,
            foregroundColor: kBg,
            minimumSize: const Size.fromHeight(54),
            textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          )
        : OutlinedButton.styleFrom(
            foregroundColor: kNeon,
            side: const BorderSide(color: kNeonDim),
            minimumSize: const Size.fromHeight(50),
            textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          );
    final child = icon == null
        ? Text(label)
        : Row(mainAxisSize: MainAxisSize.min, children: [Icon(icon), const SizedBox(width: 8), Text(label)]);
    return primary
        ? FilledButton(onPressed: onPressed, style: style, child: child)
        : OutlinedButton(onPressed: onPressed, style: style, child: child);
  }
}

/// Bottom banner, hidden for players who bought "remove ads".
class BannerSlot extends StatelessWidget {
  const BannerSlot({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    if (!app.adsEnabled) return const SizedBox.shrink();
    return SafeArea(top: false, child: Center(child: app.banner()));
  }
}

void showSnack(BuildContext context, String text) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text)));
}
