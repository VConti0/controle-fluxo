/// Everything you need to change before publishing is here.
library;

class AppConfig {
  static const packageName = 'com.vconti.escapeball';

  /// Cloud Functions region (São Paulo).
  static const functionsRegion = 'southamerica-east1';

  /// Privacy policy and account deletion pages. Host PRIVACY.md somewhere
  /// public (GitHub Pages works) and put the URLs here and in the Play Console.
  static const privacyPolicyUrl = 'https://example.com/escape-ball/privacy';
  static const deleteAccountUrl = 'https://example.com/escape-ball/delete-account';

  /// Web client id of your Firebase project (Firebase console → Authentication
  /// → Sign-in method → Google → Web SDK configuration). Google Sign-In on
  /// Android needs it to return an ID token.
  static const googleServerClientId = 'REPLACE_ME.apps.googleusercontent.com';

  /// Show an interstitial after every N finished rounds.
  static const interstitialEveryRounds = 3;

  // ---------------------------------------------------------------------
  // AdMob. These are Google's official TEST ids: they always show test ads
  // and are safe to ship to testers. Replace them with your own ad unit ids
  // before publishing (and the app id in android/app/src/main/AndroidManifest.xml).
  static const admobBannerAndroid = 'ca-app-pub-3940256099942544/6300978111';
  static const admobInterstitialAndroid = 'ca-app-pub-3940256099942544/1033173712';
  static const admobRewardedAndroid = 'ca-app-pub-3940256099942544/5224354917';

  // ---------------------------------------------------------------------
  // Build flags (pass with --dart-define=NAME=true).

  /// Purchases are simulated: nothing is charged and the server (emulator or
  /// a project with ALLOW_FAKE_PURCHASES set) credits them anyway. For
  /// testing on a phone before the app is on the Play Store.
  static const fakeBilling = bool.fromEnvironment('FAKE_BILLING');

  /// Use the local Firebase emulators (functions on :5001, auth on :9099).
  static const useEmulators = bool.fromEnvironment('USE_EMULATORS');

  /// Host of the emulators as seen from the device. 10.0.2.2 is the
  /// Android emulator's name for the computer running it.
  static const emulatorHost = String.fromEnvironment('EMULATOR_HOST', defaultValue: '10.0.2.2');

  /// Run without Firebase, ads or the Play Store: the web demo and tests.
  static const offline = bool.fromEnvironment('OFFLINE');
}
