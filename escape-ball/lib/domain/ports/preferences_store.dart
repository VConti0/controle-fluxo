/// Small key-value settings kept on the device (equipped skins).
abstract interface class PreferencesStore {
  String? getString(String key);
  Future<void> setString(String key, String value);
  Future<void> remove(String key);
}
