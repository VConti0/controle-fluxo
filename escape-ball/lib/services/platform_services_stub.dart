import 'ads_service.dart';
import 'billing_service.dart';

AdsService createAdsService() => const NoAdsService();

BillingService createBillingService() => FakeBillingService();
