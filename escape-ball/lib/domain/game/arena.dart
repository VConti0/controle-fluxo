/// The rotating polygon: its shape, opening and spikes, all derived from a
/// seed so the same seed always builds the same arena.
library;

import 'det_math.dart';
import 'physics.dart';

/// Simulation constants. Units are arbitrary "arena units": the polygon's
/// circumradius is [kArenaRadius]; the renderer scales to the screen.
const double kArenaRadius = 100.0;
const double kBallRadius = 4.0;
const double kGravity = 420.0;
const double kRestitution = 0.98;
const double kMinBounceSpeed = 230.0;
const double kMaxSpeed = 420.0;
const int kStepsPerSecond = 240;
const double kDt = 1.0 / kStepsPerSecond;
const double kAttemptTimeoutSeconds = 10.0;
const double kPauseSeconds = 0.5;
const int kMaxAttempts = 12;
const double kSpikeBase = 12.0;
const double kSpikeHeight = 14.0;

/// Opening width in arena units, per attempt (1-based). It is absolute, not
/// a fraction of the edge, so every map shape gives similar odds. The
/// progress bar shows attempts 1..8; the opening keeps widening after that.
double gapWidth(int attempt) => kGapBase + kGapStep * (attempt - 1);

const double kGapBase = 14.0;
const double kGapStep = 10.0;

/// Map shapes on sale. The id is shared with the server's seed tables.
enum ArenaShape {
  triangle(3),
  square(4),
  pentagon(5),
  hexagon(6),
  octagon(8);

  final int sides;
  const ArenaShape(this.sides);

  static ArenaShape byName(String name) =>
      ArenaShape.values.firstWhere((s) => s.name == name, orElse: () => ArenaShape.pentagon);
}

class Spike {
  final int edge;

  /// Position of the spike's centre along its edge, 0..1.
  final double t;

  /// Base corners and apex in arena-local coordinates.
  final Vec left;
  final Vec right;
  final Vec apex;

  const Spike(this.edge, this.t, this.left, this.right, this.apex);
}

class Launch {
  final double angle;
  final double speed;
  const Launch(this.angle, this.speed);
}

class ArenaSpec {
  final int seed;
  final ArenaShape shape;
  final double theta0;
  final double omega;
  final double gapCenter;

  /// Local (unrotated) polygon vertices.
  final List<Vec> vertices;
  final List<Spike> spikes;
  final List<Launch> launches;

  ArenaSpec._(this.seed, this.shape, this.theta0, this.omega, this.gapCenter, this.vertices,
      this.spikes, this.launches);

  factory ArenaSpec.fromSeed(int seed, ArenaShape shape) {
    final rng = DetRandom(seed ^ (shape.sides * 0x45d9f3b));
    final n = shape.sides;
    // Put the middle of edge 0 at the top when theta = 0.
    final phase = -kHalfPi - kPi / n;
    final vertices = <Vec>[
      for (var k = 0; k < n; k++)
        Vec(kArenaRadius * dcos(phase + kTwoPi * k / n), kArenaRadius * dsin(phase + kTwoPi * k / n)),
    ];
    final theta0 = rng.range(0, kTwoPi);
    final omegaMag = rng.range(0.55, 1.15);
    final omega = rng.nextDouble() < 0.5 ? -omegaMag : omegaMag;
    final gapCenter = rng.range(0.35, 0.65);

    final spikes = <Spike>[];
    for (var e = 0; e < n; e++) {
      final a = vertices[e];
      final b = vertices[(e + 1) % n];
      final edge = b - a;
      final len = edge.length;
      final dir = edge * (1 / len);
      final mid = (a + b) * 0.5;
      final inward = mid * (-1 / mid.length);
      final slots = (len / 30).floor();
      for (var i = 0; i < slots; i++) {
        final t = (i + 0.5) / slots;
        if (t < 0.1 || t > 0.9) continue;
        if (rng.nextDouble() > 0.7) continue;
        final jitter = rng.range(-0.25, 0.25) / slots;
        final tt = t + jitter;
        final c = a + edge * tt;
        final half = dir * (kSpikeBase / 2);
        spikes.add(Spike(e, tt, c - half, c + half, c + inward * kSpikeHeight));
      }
    }

    final launches = <Launch>[
      for (var i = 0; i < kMaxAttempts; i++) Launch(rng.range(0, kTwoPi), rng.range(140, 240)),
    ];
    return ArenaSpec._(seed, shape, theta0, omega, gapCenter, vertices, spikes, launches);
  }

  /// Wall segments in local coordinates for the given attempt. Edge 0 is
  /// split around the opening.
  List<Segment> wallsFor(int attempt) {
    final n = vertices.length;
    final out = <Segment>[];
    for (var e = 0; e < n; e++) {
      final a = vertices[e];
      final b = vertices[(e + 1) % n];
      if (e != 0) {
        out.add(Segment(a, b));
        continue;
      }
      final (t0, t1) = gapRange(attempt);
      final ab = b - a;
      if (t0 > 0) out.add(Segment(a, a + ab * t0));
      if (t1 < 1) out.add(Segment(a + ab * t1, b));
    }
    return out;
  }

  /// Start and end of the opening along edge 0, as fractions 0..1.
  (double, double) gapRange(int attempt) {
    final edgeLen = (vertices[1] - vertices[0]).length;
    var frac = gapWidth(attempt) / edgeLen;
    if (frac > 0.9) frac = 0.9;
    final half = frac / 2;
    var t0 = gapCenter - half;
    var t1 = gapCenter + half;
    if (t0 < 0) t0 = 0;
    if (t1 > 1) t1 = 1;
    return (t0, t1);
  }

  /// Spikes still standing on this attempt: the opening swallows the spikes
  /// it grows over.
  List<Spike> spikesFor(int attempt) {
    final (t0, t1) = gapRange(attempt);
    return [
      for (final s in spikes)
        if (!(s.edge == 0 && s.t > t0 - 0.06 && s.t < t1 + 0.06)) s,
    ];
  }
}
