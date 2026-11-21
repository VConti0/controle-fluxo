/// How each ball and map skin looks. Ids match `assets/data/catalog.json`.
library;

import 'package:material_ui/material_ui.dart';

import 'arena.dart';

enum TrailStyle { fade, fire, rainbow, ghost }

class BallSkin {
  final String id;
  final Color core;
  final Color glow;
  final TrailStyle trail;
  final double opacity;
  const BallSkin(this.id, this.core, this.glow, this.trail, {this.opacity = 1});
}

class MapSkin {
  final String id;
  final ArenaShape shape;

  /// Wall gradient, from the first vertex around the polygon.
  final Color wallA;
  final Color wallB;
  final Color background;
  const MapSkin(this.id, this.shape, this.wallA, this.wallB, this.background);
}

const ballSkins = <String, BallSkin>{
  'ball_white': BallSkin('ball_white', Color(0xFFFFFFFF), Color(0xFFFFFFFF), TrailStyle.fade),
  'ball_neon': BallSkin('ball_neon', Color(0xFFB6FF3B), Color(0xFF7CFF00), TrailStyle.fade),
  'ball_ice': BallSkin('ball_ice', Color(0xFFE6FBFF), Color(0xFF3BD8FF), TrailStyle.fade),
  'ball_ghost':
      BallSkin('ball_ghost', Color(0xFFF2E9FF), Color(0xFFB57BFF), TrailStyle.ghost, opacity: 0.7),
  'ball_fire': BallSkin('ball_fire', Color(0xFFFFE08A), Color(0xFFFF5A1F), TrailStyle.fire),
  'ball_rainbow': BallSkin('ball_rainbow', Color(0xFFFFFFFF), Color(0xFFFF4FD8), TrailStyle.rainbow),
};

const mapSkins = <String, MapSkin>{
  'map_pentagon': MapSkin('map_pentagon', ArenaShape.pentagon, Color(0xFF1FD8E0),
      Color(0xFFB6FF3B), Color(0xFF07140F)),
  'map_square': MapSkin(
      'map_square', ArenaShape.square, Color(0xFFFF9F1C), Color(0xFFFFE066), Color(0xFF160E05)),
  'map_octagon': MapSkin(
      'map_octagon', ArenaShape.octagon, Color(0xFF3B82FF), Color(0xFF7DF9FF), Color(0xFF050B18)),
  'map_hexagon': MapSkin(
      'map_hexagon', ArenaShape.hexagon, Color(0xFFB57BFF), Color(0xFFFF4FD8), Color(0xFF0F0718)),
  'map_triangle': MapSkin(
      'map_triangle', ArenaShape.triangle, Color(0xFFFF3B5C), Color(0xFFFFB03B), Color(0xFF180507)),
};

BallSkin ballSkin(String id) => ballSkins[id] ?? ballSkins['ball_white']!;
MapSkin mapSkin(String id) => mapSkins[id] ?? mapSkins['map_pentagon']!;

/// Colours of the X markers, cycling per attempt like the reference video.
const markerColors = <Color>[
  Color(0xFF7BD389),
  Color(0xFFB57BFF),
  Color(0xFFB0B8C8),
  Color(0xFFFF5A7A),
  Color(0xFF4F8CFF),
  Color(0xFF4FA3FF),
  Color(0xFFFFB03B),
  Color(0xFFFF7A3B),
];
