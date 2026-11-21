import '../config.dart';
import 'ads_admob.dart';
import 'ads_service.dart';
import 'billing_play.dart';
import 'billing_service.dart';

AdsService createAdsService() =>
    AppConfig.offline ? const NoAdsService() : AdMobAdsService();

BillingService createBillingService() =>
    AppConfig.offline || AppConfig.fakeBilling ? FakeBillingService() : PlayBillingService();
