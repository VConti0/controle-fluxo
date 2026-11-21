/// Tiny 2D vector helpers for the deterministic simulation.
library;

import 'det_math.dart';

class Vec {
  final double x;
  final double y;
  const Vec(this.x, this.y);

  static const zero = Vec(0, 0);

  Vec operator +(Vec o) => Vec(x + o.x, y + o.y);
  Vec operator -(Vec o) => Vec(x - o.x, y - o.y);
  Vec operator *(double k) => Vec(x * k, y * k);
  double dot(Vec o) => x * o.x + y * o.y;
  double get length2 => x * x + y * y;
  double get length => dsqrt(length2);

  /// Rotates by an angle given as its cosine and sine.
  Vec rotate(double c, double s) => Vec(x * c - y * s, x * s + y * c);

  @override
  String toString() => 'Vec($x, $y)';
}

class Segment {
  final Vec a;
  final Vec b;
  const Segment(this.a, this.b);
}

/// Closest point to [p] on segment [a]-[b].
Vec closestPointOnSegment(Vec p, Vec a, Vec b) {
  final ab = b - a;
  final len2 = ab.length2;
  if (len2 == 0) return a;
  var t = (p - a).dot(ab) / len2;
  if (t < 0) t = 0;
  if (t > 1) t = 1;
  return a + ab * t;
}

/// Distance squared from [p] to segment [s].
double distance2ToSegment(Vec p, Segment s) =>
    (p - closestPointOnSegment(p, s.a, s.b)).length2;
