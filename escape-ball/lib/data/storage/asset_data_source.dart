import 'dart:convert';

import 'package:flutter/services.dart' show AssetBundle;

import '../../domain/economy/bet.dart';
import '../../domain/economy/catalog.dart';

/// Reads the catalog and odds shipped in assets/data/.
class AssetDataSource {
  final AssetBundle _bundle;
  const AssetDataSource(this._bundle);

  Future<Catalog> catalog() async => Catalog.fromJson(
      jsonDecode(await _bundle.loadString('assets/data/catalog.json')) as Map<String, dynamic>);

  Future<OddsTable> odds() async => OddsTable.fromJson(
      jsonDecode(await _bundle.loadString('assets/data/odds.json')) as Map<String, dynamic>);
}
