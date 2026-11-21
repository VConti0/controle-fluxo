/// Full-screen ads and consent. Banners are widgets, so they are provided to
/// the presentation layer separately (see `AppState.bannerBuilder`).
abstract interface class AdsGateway {
  /// Asks for consent where the law requires it, then starts the SDK.
  Future<void> init();

  /// Whether the privacy settings entry must be shown (EU/UK users).
  bool get privacyOptionsRequired;

  Future<void> showPrivacyOptions();

  /// Shows a preloaded interstitial if one is ready.
  Future<void> showInterstitial();

  /// Shows a rewarded ad. Completes with true if the player earned the reward.
  Future<bool> showRewarded();
}
