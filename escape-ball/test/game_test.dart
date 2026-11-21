import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:escapeball/domain/game/arena.dart';
import 'package:escapeball/domain/game/det_math.dart';
import 'package:escapeball/domain/game/physics.dart';
import 'package:escapeball/domain/game/round.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('deterministic math', () {
    test('dsin/dcos match dart:math closely over many turns', () {
      for (var i = -2000; i <= 2000; i++) {
        final x = i * 0.0137;
        expect(dsin(x), closeTo(math.sin(x), 1e-12), reason: 'sin($x)');
        expect(dcos(x), closeTo(math.cos(x), 1e-12), reason: 'cos($x)');
      }
    });

    test('DetRandom is a fixed sequence', () {
      final a = DetRandom(42);
      final b = DetRandom(42);
      final seqA = [for (var i = 0; i < 5; i++) a.nextU32()];
      final seqB = [for (var i = 0; i < 5; i++) b.nextU32()];
      expect(seqA, seqB);
      // xorshift32 from 42, computed by hand: guards against accidental changes
      // that would invalidate every generated seed table.
      expect(seqA.first, 11355432);
      for (var i = 0; i < 1000; i++) {
        final d = a.nextDouble();
        expect(d >= 0 && d < 1, isTrue);
      }
    });
  });

  group('physics', () {
    test('closest point clamps to the segment', () {
      const a = Vec(0, 0);
      const b = Vec(10, 0);
      expect(closestPointOnSegment(const Vec(5, 3), a, b).x, 5);
      expect(closestPointOnSegment(const Vec(-4, 1), a, b).x, 0);
      expect(closestPointOnSegment(const Vec(14, 1), a, b).x, 10);
    });

    test('ball never leaves through a wall while running', () {
      for (final shape in ArenaShape.values) {
        for (var seed = 1; seed <= 40; seed++) {
          final sim = RoundSim(ArenaSpec.fromSeed(seed * 7919, shape));
          while (!sim.isFinished) {
            sim.advance();
            if (sim.phase == RoundPhase.running) {
              // Inside the polygon, the ball is at most one circumradius plus
              // its own radius from the centre; past the opening it escapes.
              expect(sim.ball.length, lessThan(kArenaRadius + 3 * kBallRadius + 1e-6));
            }
          }
        }
      }
    });
  });

  group('rounds', () {
    test('same seed, same round, bit for bit', () {
      for (final shape in ArenaShape.values) {
        final a = RoundSim(ArenaSpec.fromSeed(123456, shape));
        final b = RoundSim(ArenaSpec.fromSeed(123456, shape));
        while (!a.isFinished) {
          a.advance();
          b.advance();
        }
        expect(b.isFinished, isTrue);
        expect(a.escapedOn, b.escapedOn);
        expect(a.ball.x, b.ball.x);
        expect(a.ball.y, b.ball.y);
        expect(a.step, b.step);
      }
    });

    test('every round ends by the last attempt, with one X per failed attempt', () {
      for (final shape in ArenaShape.values) {
        for (var seed = 1; seed <= 150; seed++) {
          final sim = RoundSim(ArenaSpec.fromSeed(seed * 104729, shape));
          while (!sim.isFinished) {
            sim.advance();
          }
          expect(sim.escapedOn, inInclusiveRange(1, kMaxAttempts));
          expect(sim.markers.length, sim.escapedOn! - 1);
        }
      }
    });

    test('opening widens every attempt', () {
      for (var a = 2; a <= kMaxAttempts; a++) {
        expect(gapWidth(a), greaterThan(gapWidth(a - 1)));
      }
      expect(gapWidth(1), greaterThan(2 * kBallRadius));
    });

    test('server seed table replays to the same outcomes on this platform', () {
      final file = File('functions/data/seeds.json');
      final json = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
      final shapes = json['shapes'] as Map<String, dynamic>;
      for (final shape in ArenaShape.values) {
        final seeds = (shapes[shape.name] as Map<String, dynamic>)['seeds'] as List;
        // Every 25th entry keeps the test quick while covering the table.
        for (var i = 0; i < seeds.length; i += 25) {
          final pair = seeds[i] as List;
          expect(simulateOutcome(pair[0] as int, shape), pair[1],
              reason: '${shape.name} seed ${pair[0]}');
        }
      }
    });
  });
}
