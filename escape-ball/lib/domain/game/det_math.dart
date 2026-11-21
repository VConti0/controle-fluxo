/// Deterministic math helpers.
///
/// The server picks a seed whose outcome was computed ahead of time by
/// `tool/gen_seeds.dart`; the phone replays that seed and must reach the
/// same result. Platform `sin`/`cos` come from each platform's libm and may
/// differ in the last bit, which a chaotic simulation amplifies. These
/// versions only use + - * / and floor, which IEEE 754 defines exactly, so
/// every device computes the same bits. `sqrt` is also exactly rounded by
/// IEEE 754, so `dart:math`'s is safe to use.
library;

import 'dart:math' as math;

const double kPi = 3.141592653589793;
const double kTwoPi = 6.283185307179586;
const double kHalfPi = 1.5707963267948966;

double dsin(double x) {
  // Reduce to [-pi, pi].
  x = x - kTwoPi * (x / kTwoPi + 0.5).floorToDouble();
  // Reduce to [-pi/2, pi/2] using sin(pi - x) = sin(x).
  if (x > kHalfPi) {
    x = kPi - x;
  } else if (x < -kHalfPi) {
    x = -kPi - x;
  }
  final x2 = x * x;
  // Taylor series to x^19 in Horner form; error < 1e-13 on [-pi/2, pi/2].
  var p = 1.0 / 121645100408832000.0;
  p = -1.0 / 355687428096000.0 + x2 * p;
  p = 1.0 / 1307674368000.0 + x2 * p;
  p = -1.0 / 6227020800.0 + x2 * p;
  p = 1.0 / 39916800.0 + x2 * p;
  p = -1.0 / 362880.0 + x2 * p;
  p = 1.0 / 5040.0 + x2 * p;
  p = -1.0 / 120.0 + x2 * p;
  p = 1.0 / 6.0 + x2 * p;
  // Signs alternate: x - x^3/6 + x^5/120 - ...
  return x * (1.0 - x2 * p);
}

double dcos(double x) => dsin(x + kHalfPi);

double dsqrt(double x) => x <= 0 ? 0.0 : math.sqrt(x);

/// xorshift32: only shifts, xors and masks, so it behaves the same on the
/// Dart VM and when compiled to JavaScript.
class DetRandom {
  int _s;

  DetRandom(int seed) : _s = (seed & 0xffffffff) == 0 ? 0x9e3779b9 : seed & 0xffffffff;

  int nextU32() {
    var x = _s;
    x ^= (x << 13) & 0xffffffff;
    x ^= x >>> 17;
    x ^= (x << 5) & 0xffffffff;
    _s = x & 0xffffffff;
    return _s;
  }

  /// Uniform in [0, 1).
  double nextDouble() => nextU32() / 4294967296.0;

  double range(double min, double max) => min + (max - min) * nextDouble();

  int nextInt(int max) => nextU32() % max;
}
