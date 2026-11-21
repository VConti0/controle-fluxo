// Generates the seed tables the server draws rounds from, and the odds the
// app shows on the guess screen.
//
//   dart run tool/gen_seeds.dart [--count=5000] [--rtp=0.95]
//
// Writes:
//   assets/data/odds.json          probabilities and multipliers per map shape
//   functions/data/seeds.json  the same multipliers plus [seed, attempt]
//                                  pairs the server picks from
//
// Re-run it whenever the physics or arena constants change: old seeds would
// no longer replay to the outcomes the server pays out on.
import 'dart:convert';
import 'dart:io';

import 'package:escapeball/economy/bet.dart';
import 'package:escapeball/game/arena.dart';
import 'package:escapeball/game/round.dart';

void main(List<String> args) {
  var count = 5000;
  var rtp = 0.95;
  for (final a in args) {
    if (a.startsWith('--count=')) count = int.parse(a.substring(8));
    if (a.startsWith('--rtp=')) rtp = double.parse(a.substring(6));
  }

  final odds = <String, dynamic>{};
  final seeds = <String, dynamic>{};
  for (final shape in ArenaShape.values) {
    final hits = List.filled(kBands.length, 0);
    final pairs = <List<int>>[];
    for (var i = 0; i < count; i++) {
      // Spread seeds over the 32-bit range (Knuth's multiplicative hash).
      final seed = ((i + 1) * 2654435761) & 0xffffffff;
      final attempt = simulateOutcome(seed, shape);
      hits[bandOf(attempt)]++;
      pairs.add([seed, attempt]);
    }
    final probs = [for (final h in hits) h / count];
    final mults = [for (final p in probs) multiplierFor(p, rtp)];
    odds[shape.name] = {'probabilities': probs, 'multipliers': mults};
    seeds[shape.name] = {'multipliers': mults, 'seeds': pairs};
    stdout.writeln('${shape.name.padRight(9)} '
        'p=${probs.map((p) => p.toStringAsFixed(3)).join(' ')}  '
        'x=${mults.join(' ')}');
  }

  final bands = [
    for (final b in kBands) [b.first, b.last ?? 999],
  ];
  _write('assets/data/odds.json', {'rtp': rtp, 'bands': bands, 'shapes': odds});
  _write('functions/data/seeds.json', {'rtp': rtp, 'bands': bands, 'shapes': seeds});
}

void _write(String path, Object json) {
  final f = File(path);
  f.parent.createSync(recursive: true);
  f.writeAsStringSync(const JsonEncoder().convert(json));
  stdout.writeln('wrote $path (${f.lengthSync()} bytes)');
}
