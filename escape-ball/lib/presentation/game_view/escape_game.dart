/// Draws a [RoundSim] with neon glow and advances it in real time.
library;

import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flame/game.dart';
import 'package:material_ui/material_ui.dart';

import '../../domain/game/arena.dart';
import '../../domain/game/physics.dart';
import '../../domain/game/round.dart';
import 'skins.dart';

class HudState {
  final int attempt;
  final bool finished;
  final bool shattered;
  const HudState(this.attempt, this.finished, this.shattered);
}

class EscapeGame extends Game {
  RoundSim sim;
  final BallSkin ball;
  final MapSkin map;

  /// Home screen preview: start a new random round when one ends.
  final bool loop;

  /// Playback speed (1 = real time).
  double speed;

  final ValueNotifier<HudState> hud;
  final void Function(SimEvent event)? onEvent;

  double _acc = 0;
  double _time = 0;
  double _finishedFor = 0;
  final List<Vec> _trail = [];
  final List<_Ring> _rings = [];
  double _shatterT = 0;
  final math.Random _rng = math.Random();

  EscapeGame({
    required this.sim,
    required this.ball,
    required this.map,
    this.loop = false,
    this.speed = 1,
    this.onEvent,
  }) : hud = ValueNotifier(HudState(sim.attempt, false, false));

  @override
  Color backgroundColor() => map.background;

  @override
  void update(double dt) {
    if (dt > 0.05) dt = 0.05;
    _time += dt;
    _acc += dt * speed;
    var n = 0;
    while (_acc >= kDt) {
      _acc -= kDt;
      sim.advance();
      n++;
      if (n % 2 == 0) {
        _trail.add(sim.ball);
        if (_trail.length > 16) _trail.removeAt(0);
      }
      for (final e in sim.drainEvents()) {
        _handle(e);
      }
    }
    for (final r in _rings) {
      r.t += dt;
    }
    _rings.removeWhere((r) => r.t > r.life);
    if (sim.shattered) _shatterT += dt;
    if (sim.isFinished) {
      _finishedFor += dt;
      if (loop && _finishedFor > 1.6) _restart();
    }
  }

  void _handle(SimEvent e) {
    switch (e.type) {
      case SimEventType.death:
      case SimEventType.timeout:
        _rings.add(_Ring(e.position, 0.5, markerColors[(sim.attempt - 1) % markerColors.length]));
        _trail.clear();
      case SimEventType.escape:
      case SimEventType.shatter:
        _rings.add(_Ring(e.position, 1.2, ball.glow));
      case SimEventType.respawn:
        _trail.clear();
      case SimEventType.bounce:
        break;
    }
    if (e.type != SimEventType.bounce) {
      hud.value = HudState(sim.attempt, sim.isFinished, sim.shattered);
    }
    onEvent?.call(e);
  }

  void _restart() {
    sim = RoundSim(ArenaSpec.fromSeed(_rng.nextInt(0x7fffffff) + 1, map.shape));
    _trail.clear();
    _rings.clear();
    _finishedFor = 0;
    _shatterT = 0;
    hud.value = HudState(sim.attempt, false, false);
  }

  @override
  void render(Canvas canvas) {
    final w = size.x;
    final h = size.y;
    final scale = math.min(w, h) * 0.44 / kArenaRadius;
    canvas.save();
    canvas.translate(w / 2, h / 2);
    canvas.scale(scale);

    _drawBackdrop(canvas);

    canvas.save();
    canvas.rotate(sim.theta);
    _drawArena(canvas, scale);
    canvas.restore();

    _drawRings(canvas);
    _drawBall(canvas);
    canvas.restore();
  }

  void _drawBackdrop(Canvas canvas) {
    final glow = Paint()
      ..shader = ui.Gradient.radial(
        Offset.zero,
        kArenaRadius * 1.4,
        [map.wallA.withValues(alpha: 0.10), map.background.withValues(alpha: 0)],
      );
    canvas.drawCircle(Offset.zero, kArenaRadius * 1.4, glow);
  }

  Shader _wallShader() => ui.Gradient.linear(
        const Offset(-kArenaRadius, -kArenaRadius),
        const Offset(kArenaRadius, kArenaRadius),
        [map.wallA, map.wallB],
      );

  void _drawArena(Canvas canvas, double scale) {
    final px = 1 / scale; // one screen pixel in arena units

    // Faint dashed outline just outside the walls.
    final dash = Paint()
      ..color = map.wallA.withValues(alpha: 0.25)
      ..strokeWidth = 1.2 * px;
    final verts = sim.arena.vertices;
    for (var i = 0; i < verts.length; i++) {
      final a = verts[i] * 1.07;
      final b = verts[(i + 1) % verts.length] * 1.07;
      final len = (b - a).length;
      final steps = (len / 4).floor();
      for (var s = 0; s < steps; s += 2) {
        final p0 = a + (b - a) * (s / steps);
        final p1 = a + (b - a) * ((s + 1) / steps);
        canvas.drawLine(Offset(p0.x, p0.y), Offset(p1.x, p1.y), dash);
      }
    }

    final shatterOffset = _shatterT * 60;
    final shatterAlpha = (1 - _shatterT / 1.2).clamp(0.0, 1.0);
    final walls = sim.shattered ? sim.arena.wallsFor(sim.attempt) : sim.walls;
    if (shatterAlpha > 0) {
      final glow = Paint()
        ..shader = _wallShader()
        ..strokeWidth = 7 * px
        ..strokeCap = StrokeCap.round
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, 5 * px)
        ..color = Colors.white.withValues(alpha: 0.7 * shatterAlpha);
      final line = Paint()
        ..shader = _wallShader()
        ..strokeWidth = 3 * px
        ..strokeCap = StrokeCap.round
        ..color = Colors.white.withValues(alpha: shatterAlpha);
      for (final s in walls) {
        var a = s.a;
        var b = s.b;
        if (sim.shattered) {
          final mid = (a + b) * 0.5;
          final out = mid * (shatterOffset / mid.length);
          a = a + out;
          b = b + out;
        }
        canvas.drawLine(Offset(a.x, a.y), Offset(b.x, b.y), glow);
        canvas.drawLine(Offset(a.x, a.y), Offset(b.x, b.y), line);
      }
    }

    // Spikes.
    final spikeFill = Paint()..color = Color.lerp(map.background, Colors.black, 0.4)!;
    final spikeLine = Paint()
      ..shader = _wallShader()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6 * px
      ..strokeJoin = StrokeJoin.round;
    final tip = Paint()..color = Colors.white;
    for (final s in sim.spikes) {
      final path = Path()
        ..moveTo(s.left.x, s.left.y)
        ..lineTo(s.apex.x, s.apex.y)
        ..lineTo(s.right.x, s.right.y)
        ..close();
      canvas.drawPath(path, spikeFill);
      canvas.drawPath(path, spikeLine);
      canvas.drawCircle(Offset(s.apex.x, s.apex.y), 1.1 * px * 1.5, tip);
    }

    // X markers where earlier attempts died.
    for (final m in sim.markers) {
      final c = markerColors[(m.attempt - 1) % markerColors.length];
      final o = Offset(m.local.x, m.local.y);
      const r = kBallRadius * 1.9;
      canvas.drawCircle(o, r, Paint()..color = map.background.withValues(alpha: 0.85));
      canvas.drawCircle(
          o,
          r,
          Paint()
            ..color = c
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.6 * px);
      final xp = Paint()
        ..color = Colors.white.withValues(alpha: 0.75)
        ..strokeWidth = 1.4 * px
        ..strokeCap = StrokeCap.round;
      const k = r * 0.42;
      // Keep the X upright while the arena turns.
      canvas.save();
      canvas.translate(o.dx, o.dy);
      canvas.rotate(-sim.theta);
      canvas.drawLine(const Offset(-k, -k), const Offset(k, k), xp);
      canvas.drawLine(const Offset(-k, k), const Offset(k, -k), xp);
      canvas.restore();
    }
  }

  void _drawRings(Canvas canvas) {
    for (final r in _rings) {
      final f = r.t / r.life;
      canvas.drawCircle(
        Offset(r.at.x, r.at.y),
        kBallRadius * (1.5 + f * 6),
        Paint()
          ..color = r.color.withValues(alpha: (1 - f) * 0.8)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5,
      );
    }
  }

  Color _trailColor(int i, int n) {
    final f = (i + 1) / n;
    switch (ball.trail) {
      case TrailStyle.fade:
        return ball.glow.withValues(alpha: 0.35 * f);
      case TrailStyle.ghost:
        return ball.glow.withValues(alpha: 0.25 * f);
      case TrailStyle.fire:
        return Color.lerp(const Color(0xFFFF2A00), const Color(0xFFFFD34D), f)!
            .withValues(alpha: 0.6 * f);
      case TrailStyle.rainbow:
        final hue = ((_time * 180) + i * 22) % 360;
        return HSVColor.fromAHSV(0.7 * f, hue, 0.9, 1).toColor();
    }
  }

  void _drawBall(Canvas canvas) {
    if (sim.phase == RoundPhase.pausing) return;
    final n = _trail.length;
    for (var i = 0; i < n; i++) {
      final p = _trail[i];
      final f = (i + 1) / n;
      canvas.drawCircle(Offset(p.x, p.y), kBallRadius * (0.45 + 0.55 * f), Paint()..color = _trailColor(i, n));
    }
    final o = Offset(sim.ball.x, sim.ball.y);
    canvas.drawCircle(
      o,
      kBallRadius * 2.2,
      Paint()
        ..color = ball.glow.withValues(alpha: 0.45 * ball.opacity)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.drawCircle(o, kBallRadius, Paint()..color = ball.core.withValues(alpha: ball.opacity));
  }
}

class _Ring {
  final Vec at;
  final double life;
  final Color color;
  double t = 0;
  _Ring(this.at, this.life, this.color);
}
