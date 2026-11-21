import '../../domain/ports/ads_gateway.dart';

/// Offline builds, the web and tests: no ads. Rewarded "ads" succeed so the
/// try-a-skin flow can be exercised.
class NoAds implements AdsGateway {
  final bool grantRewards;
  const NoAds({this.grantRewards = true});

  @override
  Future<void> init() async {}

  @override
  bool get privacyOptionsRequired => false;

  @override
  Future<void> showPrivacyOptions() async {}

  @override
  Future<void> showInterstitial() async {}

  @override
  Future<bool> showRewarded() async => grantRewards;
}
