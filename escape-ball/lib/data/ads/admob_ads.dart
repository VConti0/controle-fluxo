/// AdMob banners, interstitials and rewarded ads.
library;

import 'dart:async';

import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:material_ui/material_ui.dart';

import '../../domain/ports/ads_gateway.dart';
import 'consent_service.dart';

class AdUnitIds {
  final String banner;
  final String interstitial;
  final String rewarded;
  const AdUnitIds({required this.banner, required this.interstitial, required this.rewarded});
}

class AdMobAds implements AdsGateway {
  final AdUnitIds _units;
  final ConsentService _consent;
  bool _canRequest = false;

  AdMobAds(this._units, {ConsentService? consent}) : _consent = consent ?? ConsentService();

  /// Flips to true once consent is settled and the SDK started, so banners
  /// built before that (the menu opens first) appear as soon as they can.
  final ValueNotifier<bool> _ready = ValueNotifier(false);
  InterstitialAd? _interstitial;
  RewardedAd? _rewarded;

  @override
  Future<void> init() async {
    _canRequest = await _consent.gather();
    if (!_canRequest) return;
    await MobileAds.instance.initialize();
    _ready.value = true;
    _loadInterstitial();
    _loadRewarded();
  }

  @override
  bool get privacyOptionsRequired => _consent.privacyOptionsRequired;

  @override
  Future<void> showPrivacyOptions() => _consent.showPrivacyOptions();

  void _loadInterstitial() {
    InterstitialAd.load(
      adUnitId: _units.interstitial,
      request: const AdRequest(),
      adLoadCallback: InterstitialAdLoadCallback(
        onAdLoaded: (ad) => _interstitial = ad,
        onAdFailedToLoad: (_) => _interstitial = null,
      ),
    );
  }

  void _loadRewarded() {
    RewardedAd.load(
      adUnitId: _units.rewarded,
      request: const AdRequest(),
      rewardedAdLoadCallback: RewardedAdLoadCallback(
        onAdLoaded: (ad) => _rewarded = ad,
        onAdFailedToLoad: (_) => _rewarded = null,
      ),
    );
  }

  /// A bottom banner that appears once the SDK is ready. Handed to the
  /// presentation layer as its banner builder.
  Widget banner() => ValueListenableBuilder<bool>(
        valueListenable: _ready,
        builder: (context, ready, _) =>
            ready ? _Banner(unitId: _units.banner) : const SizedBox.shrink(),
      );

  @override
  Future<void> showInterstitial() async {
    final ad = _interstitial;
    if (ad == null) {
      if (_canRequest) _loadInterstitial();
      return;
    }
    _interstitial = null;
    final closed = Completer<void>();
    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdDismissedFullScreenContent: (ad) {
        ad.dispose();
        closed.complete();
      },
      onAdFailedToShowFullScreenContent: (ad, _) {
        ad.dispose();
        closed.complete();
      },
    );
    await ad.show();
    await closed.future;
    _loadInterstitial();
  }

  @override
  Future<bool> showRewarded() async {
    final ad = _rewarded;
    if (ad == null) {
      if (_canRequest) _loadRewarded();
      return false;
    }
    _rewarded = null;
    var earned = false;
    final closed = Completer<void>();
    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdDismissedFullScreenContent: (ad) {
        ad.dispose();
        closed.complete();
      },
      onAdFailedToShowFullScreenContent: (ad, _) {
        ad.dispose();
        closed.complete();
      },
    );
    await ad.show(onUserEarnedReward: (_, _) => earned = true);
    await closed.future;
    _loadRewarded();
    return earned;
  }
}

class _Banner extends StatefulWidget {
  final String unitId;
  const _Banner({required this.unitId});

  @override
  State<_Banner> createState() => _BannerState();
}

class _BannerState extends State<_Banner> {
  BannerAd? _ad;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _ad = BannerAd(
      size: AdSize.banner,
      adUnitId: widget.unitId,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (_) => setState(() => _loaded = true),
        onAdFailedToLoad: (ad, _) {
          ad.dispose();
          _ad = null;
        },
      ),
    )..load();
  }

  @override
  void dispose() {
    _ad?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ad = _ad;
    if (ad == null || !_loaded) return SizedBox(height: AdSize.banner.height.toDouble());
    return SizedBox(
      width: ad.size.width.toDouble(),
      height: ad.size.height.toDouble(),
      child: AdWidget(ad: ad),
    );
  }
}
