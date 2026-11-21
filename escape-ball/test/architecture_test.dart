// Enforces the Clean Architecture dependency rule on lib/ by reading every
// import. Layers (see .claude/skills/revisao-clean-architecture/SKILL.md):
//
//   domain/        pure Dart: entities, rules, ports (interfaces), use cases
//   data/          implementations of the ports (Firebase, Play, AdMob...)
//   presentation/  Flutter UI and state; talks to domain only
//   di/, main.dart composition root: the only code that sees every layer
//
// If this test fails, move the code to the right layer or add a port in
// domain/ports instead of loosening the rules here.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _pkg = 'package:escapeball/';

/// Packages that are implementation details and must stay in data/ or di/.
const _infraPackages = [
  'package:firebase_',
  'package:cloud_functions',
  'package:cloud_firestore',
  'package:google_sign_in',
  'package:google_mobile_ads',
  'package:in_app_purchase',
  'package:shared_preferences',
];

/// dart: libraries the domain must not use (UI, IO, platform).
const _impureDartLibs = ['dart:ui', 'dart:io', 'dart:html', 'dart:js_interop', 'dart:ffi'];

class _Import {
  final String file;
  final int line;
  final String uri;

  /// Target path relative to lib/, or null for package:/dart: imports
  /// outside this app.
  final String? target;
  _Import(this.file, this.line, this.uri, this.target);

  @override
  String toString() => '$file:$line imports $uri';
}

List<_Import> _importsUnder(String dir) {
  final out = <_Import>[];
  final re = RegExp(r'''^\s*(?:import|export)\s+['"]([^'"]+)['"]''');
  final libDir = Directory('lib').absolute.path;
  for (final f in Directory(dir).listSync(recursive: true).whereType<File>()) {
    if (!f.path.endsWith('.dart')) continue;
    final lines = f.readAsLinesSync();
    for (var i = 0; i < lines.length; i++) {
      final m = re.firstMatch(lines[i]);
      if (m == null) continue;
      final uri = m.group(1)!;
      String? target;
      if (uri.startsWith(_pkg)) {
        target = uri.substring(_pkg.length);
      } else if (!uri.contains(':')) {
        final abs = File(f.parent.absolute.uri.resolve(uri).toFilePath()).absolute.path;
        target = abs.startsWith(libDir) ? abs.substring(libDir.length + 1) : abs;
      }
      out.add(_Import(f.path, i + 1, uri, target));
    }
  }
  return out;
}

void main() {
  test('domain/ is pure Dart and depends on nothing outside domain/', () {
    final bad = [
      for (final i in _importsUnder('lib/domain'))
        if ((i.uri.startsWith('package:') && !(i.target?.startsWith('domain/') ?? false)) ||
            _impureDartLibs.contains(i.uri) ||
            (i.target != null && !i.target!.startsWith('domain/')))
          i,
    ];
    expect(bad, isEmpty, reason: 'domain must not import Flutter, plugins or other layers:\n${bad.join('\n')}');
  });

  test('presentation/ does not depend on data/, di/ or infrastructure packages', () {
    final bad = [
      for (final i in _importsUnder('lib/presentation'))
        if (_infraPackages.any(i.uri.startsWith) ||
            (i.target != null && (i.target!.startsWith('data/') || i.target!.startsWith('di/'))))
          i,
    ];
    expect(bad, isEmpty, reason: 'presentation must go through domain ports:\n${bad.join('\n')}');
  });

  test('data/ does not depend on presentation/ or di/', () {
    final bad = [
      for (final i in _importsUnder('lib/data'))
        if (i.target != null && (i.target!.startsWith('presentation/') || i.target!.startsWith('di/')))
          i,
    ];
    expect(bad, isEmpty, reason: bad.join('\n'));
  });

  test('ports in domain/ports are interfaces only', () {
    for (final f in Directory('lib/domain/ports').listSync().whereType<File>()) {
      final src = f.readAsStringSync();
      final classes = RegExp(r'^(?:abstract |sealed |final |base |interface )*class (\w+)', multiLine: true)
          .allMatches(src)
          .map((m) => m.group(0)!)
          .toList();
      for (final c in classes) {
        final isInterface = c.contains('abstract interface class');
        final isValue = !c.contains('abstract'); // plain data classes (PurchaseUpdate) are fine
        expect(isInterface || isValue, isTrue, reason: '${f.path}: "$c" should be `abstract interface class`');
      }
    }
  });

  test('every layer folder exists (guards against files drifting back to lib/)', () {
    final top = Directory('lib').listSync().map((e) => e.uri.pathSegments.where((s) => s.isNotEmpty).last).toSet();
    expect(top, containsAll(['domain', 'data', 'presentation', 'di', 'main.dart', 'config.dart']));
    final stray = top.difference({'domain', 'data', 'presentation', 'di', 'main.dart', 'config.dart'});
    expect(stray, isEmpty, reason: 'new top-level entries in lib/ must belong to a layer: $stray');
  });
}
