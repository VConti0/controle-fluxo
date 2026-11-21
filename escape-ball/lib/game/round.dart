/// One round: the ball keeps trying until it escapes. Each failed attempt
/// leaves an X where the ball died, and the opening widens a step.
library;

import 'arena.dart';
import 'det_math.dart';
import 'physics.dart';

enum RoundPhase { running, pausing, escaped }

enum SimEventType { bounce, death, timeout, escape, shatter, respawn }

class SimEvent {
  final SimEventType type;
  final Vec position;
  const SimEvent(this.type, this.position);
}

class Marker {
  /// Arena-local position, so the X turns with the polygon.
  final Vec local;
  final int attempt;
  const Marker(this.local, this.attempt);
}

class RoundSim {
  final ArenaSpec arena;
  final int _pauseSteps = (kPauseSeconds * kStepsPerSecond).round();
  final int _timeoutSteps = (kAttemptTimeoutSeconds * kStepsPerSecond).round();

  RoundPhase phase = RoundPhase.running;
  int attempt = 1;
  int step = 0;
  int _attemptSteps = 0;
  int _pauseLeft = 0;
  bool shattered = false;

  /// Attempt on which the ball escaped, once it has.
  int? escapedOn;

  Vec ball = Vec.zero;
  Vec velocity = Vec.zero;
  final List<Marker> markers = [];
  final List<SimEvent> _events = [];

  late List<Segment> _walls;
  late List<Segment> _spikeEdges;

  RoundSim(this.arena) {
    _startAttempt();
  }

  double get theta => arena.theta0 + arena.omega * step * kDt;

  bool get isFinished => escapedOn != null;

  List<SimEvent> drainEvents() {
    final out = List<SimEvent>.of(_events);
    _events.clear();
    return out;
  }

  void _startAttempt() {
    _walls = arena.wallsFor(attempt);
    final spikes = attempt >= kMaxAttempts ? const <Spike>[] : arena.spikesFor(attempt);
    _spikeEdges = [
      for (final s in spikes) ...[Segment(s.left, s.apex), Segment(s.apex, s.right)],
    ];
    final launch = arena.launches[attempt - 1];
    ball = Vec.zero;
    velocity = Vec(dcos(launch.angle) * launch.speed, dsin(launch.angle) * launch.speed);
    _attemptSteps = 0;
    phase = RoundPhase.running;
  }

  void advance() {
    step++;
    switch (phase) {
      case RoundPhase.escaped:
        // Free fall off screen, no collisions.
        velocity = Vec(velocity.x, velocity.y + kGravity * kDt);
        ball = ball + velocity * kDt;
        return;
      case RoundPhase.pausing:
        _pauseLeft--;
        if (_pauseLeft <= 0) {
          attempt++;
          _startAttempt();
          _events.add(const SimEvent(SimEventType.respawn, Vec.zero));
        }
        return;
      case RoundPhase.running:
        _stepRunning();
    }
  }

  void _stepRunning() {
    _attemptSteps++;
    velocity = Vec(velocity.x, velocity.y + kGravity * kDt);
    final speed2 = velocity.length2;
    if (speed2 > kMaxSpeed * kMaxSpeed) {
      velocity = velocity * (kMaxSpeed / dsqrt(speed2));
    }
    ball = ball + velocity * kDt;

    final th = theta;
    final c = dcos(th);
    final s = dsin(th);
    // Ball in arena-local coordinates (rotate by -theta).
    var local = ball.rotate(c, -s);
    const r2 = kBallRadius * kBallRadius;

    for (final edge in _spikeEdges) {
      if (distance2ToSegment(local, edge) < r2) {
        _die(local, SimEventType.death);
        return;
      }
    }

    for (final wall in _walls) {
      final cp = closestPointOnSegment(local, wall.a, wall.b);
      final d = local - cp;
      final dist2 = d.length2;
      if (dist2 >= r2) continue;
      final dist = dsqrt(dist2);
      final nLocal = dist > 1e-9 ? d * (1 / dist) : local * (-1 / (local.length + 1e-9));
      local = cp + nLocal * kBallRadius;
      ball = local.rotate(c, s);
      final n = nLocal.rotate(c, s);
      final q = cp.rotate(c, s);
      final wallVel = Vec(-arena.omega * q.y, arena.omega * q.x);
      var rel = velocity - wallVel;
      final vn = rel.dot(n);
      if (vn < 0) {
        var out = -vn * kRestitution;
        if (out < kMinBounceSpeed) out = kMinBounceSpeed;
        rel = rel + n * (out - vn);
        velocity = rel + wallVel;
        _events.add(SimEvent(SimEventType.bounce, ball));
      }
    }

    if (ball.length > kArenaRadius + 3 * kBallRadius) {
      escapedOn = attempt;
      phase = RoundPhase.escaped;
      _events.add(SimEvent(SimEventType.escape, ball));
      return;
    }

    if (_attemptSteps >= _timeoutSteps) {
      if (attempt >= kMaxAttempts) {
        // Last attempt: the walls shatter and the ball drops out.
        shattered = true;
        _walls = const [];
        escapedOn = attempt;
        phase = RoundPhase.escaped;
        _events.add(SimEvent(SimEventType.shatter, ball));
      } else {
        _die(local, SimEventType.timeout);
      }
    }
  }

  void _die(Vec local, SimEventType type) {
    markers.add(Marker(local, attempt));
    _events.add(SimEvent(type, ball));
    phase = RoundPhase.pausing;
    _pauseLeft = _pauseSteps;
  }

  /// Walls for the current attempt, in local coordinates (for drawing).
  List<Segment> get walls => _walls;

  /// Spikes standing this attempt (for drawing).
  List<Spike> get spikes => attempt >= kMaxAttempts ? const [] : arena.spikesFor(attempt);
}

/// Runs a round to the end without drawing it. Used by the seed generator,
/// by tests, and by the offline backend.
int simulateOutcome(int seed, ArenaShape shape) {
  final sim = RoundSim(ArenaSpec.fromSeed(seed, shape));
  while (!sim.isFinished) {
    sim.advance();
  }
  return sim.escapedOn!;
}
