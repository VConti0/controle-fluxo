/// Guess bands and payouts.
///
/// Money-like amounts are integers in hundredths of a coin ("cents") so
/// payouts keep their precision: 1 coin = 100 cents = R$ 2,50.
library;

class Band {
  final int index;
  final int first;

  /// Inclusive; `null` means "or later".
  final int? last;

  const Band(this.index, this.first, this.last);

  bool contains(int attempt) => attempt >= first && (last == null || attempt <= last!);

  String get label => last == null ? '$first+' : '$first–$last';
}

const List<Band> kBands = [
  Band(0, 1, 2),
  Band(1, 3, 4),
  Band(2, 5, 6),
  Band(3, 7, 8),
  Band(4, 9, null),
];

int bandOf(int attempt) => kBands.firstWhere((b) => b.contains(attempt)).index;

const int kCentsPerCoin = 100;

/// Bets the player can pick, in whole coins.
const List<int> kBetCoins = [1, 2, 5, 10, 20, 50, 100];

/// Multiplier for a band: the return-to-player share divided by the band's
/// real probability, rounded down to 2 decimals. Shared with the server
/// through the generated odds file.
double multiplierFor(double probability, double rtp) {
  if (probability <= 0) return 0;
  return (rtp / probability * 100).floorToDouble() / 100;
}

/// Payout in cents for a winning bet (0 when the guess missed).
int payoutCents({required int betCents, required double multiplier, required bool won}) {
  if (!won) return 0;
  return (betCents * multiplier).floor();
}

String formatCoins(int cents) {
  final whole = cents ~/ kCentsPerCoin;
  final frac = (cents % kCentsPerCoin).toString().padLeft(2, '0');
  return frac == '00' ? '$whole' : '$whole,$frac';
}

class ShapeOdds {
  final List<double> probabilities;
  final List<double> multipliers;
  const ShapeOdds(this.probabilities, this.multipliers);

  factory ShapeOdds.fromJson(Map<String, dynamic> j) => ShapeOdds(
        [for (final p in j['probabilities'] as List) (p as num).toDouble()],
        [for (final m in j['multipliers'] as List) (m as num).toDouble()],
      );
}

class OddsTable {
  final double rtp;
  final Map<String, ShapeOdds> shapes;
  const OddsTable(this.rtp, this.shapes);

  factory OddsTable.fromJson(Map<String, dynamic> j) => OddsTable(
        (j['rtp'] as num).toDouble(),
        {
          for (final e in (j['shapes'] as Map<String, dynamic>).entries)
            e.key: ShapeOdds.fromJson(e.value as Map<String, dynamic>),
        },
      );
}
