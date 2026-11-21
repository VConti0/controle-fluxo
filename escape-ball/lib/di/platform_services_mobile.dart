import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:material_ui/material_ui.dart';

import '../config.dart';
import '../data/ads/admob_ads.dart';
import '../data/ads/no_ads.dart';
import '../data/billing/fake_billing_gateway.dart';
import '../data/billing/play_billing_gateway.dart';
import '../domain/ports/ads_gateway.dart';
import '../domain/ports/billing_gateway.dart';

typedef Ads = (AdsGateway gateway, Widget Function() banner);

Ads createAds({required bool offline}) {
  if (offline) return (const NoAds(), () => const SizedBox.shrink());
  final admob = AdMobAds(const AdUnitIds(
    banner: AppConfig.admobBannerAndroid,
    interstitial: AppConfig.admobInterstitialAndroid,
    rewarded: AppConfig.admobRewardedAndroid,
  ));
  return (admob, admob.banner);
}

BillingGateway createBilling({required bool fake}) =>
    fake ? FakeBillingGateway() : PlayBillingGateway(InAppPurchase.instance);
