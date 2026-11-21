/// Picks the real store and ad services on Android/iOS, and the offline ones
/// on the web, where the ad and billing plugins do not exist.
library;

import 'ads_service.dart';
import 'billing_service.dart';
import 'platform_services_stub.dart'
    if (dart.library.io) 'platform_services_mobile.dart' as impl;

AdsService createAdsService() => impl.createAdsService();

BillingService createBillingService() => impl.createBillingService();
