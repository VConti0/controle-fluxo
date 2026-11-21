import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/ports/preferences_store.dart';

class SharedPrefsStore implements PreferencesStore {
  final SharedPreferences _prefs;
  SharedPrefsStore(this._prefs);

  @override
  String? getString(String key) => _prefs.getString(key);

  @override
  Future<void> setString(String key, String value) => _prefs.setString(key, value);

  @override
  Future<void> remove(String key) => _prefs.remove(key);
}

/// Used when the platform storage is unavailable (private browsing, tests).
class MemoryPrefsStore implements PreferencesStore {
  final Map<String, String> _values = {};

  @override
  String? getString(String key) => _values[key];

  @override
  Future<void> setString(String key, String value) async => _values[key] = value;

  @override
  Future<void> remove(String key) async => _values.remove(key);
}
