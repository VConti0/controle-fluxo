/// Ads. The AdMob implementation is in `ads_admob.dart`; this file holds the
/// interface and the no-op used offline and in tests.
library;

import 'package:material_ui/material_ui.dart';

abstract class AdsService {
  /// Asks for consent where the law requires it, then starts the SDK.
  Future<void> init();

  /// Whether the privacy settings entry must be shown (EU/UK users).
  bool get privacyOptionsRequired;

  Future<void> showPrivacyOptions();

  /// A banner sized for the bottom of the screen, or an empty box.
  Widget banner();

  /// Shows a preloaded interstitial if one is ready.
  Future<void> showInterstitial();

  /// Shows a rewarded ad. Completes with true if the player earned the reward.
  Future<bool> showRewarded();
}

class NoAdsService implements AdsService {
  /// Offline demo: pretend the rewarded ad was watched.
  final bool grantRewards;
  const NoAdsService({this.grantRewards = true});

  @override
  Future<void> init() async {}

  @override
  bool get privacyOptionsRequired => false;

  @override
  Future<void> showPrivacyOptions() async {}

  @override
  Widget banner() => const SizedBox.shrink();

  @override
  Future<void> showInterstitial() async {}

  @override
  Future<bool> showRewarded() async => grantRewards;
}
