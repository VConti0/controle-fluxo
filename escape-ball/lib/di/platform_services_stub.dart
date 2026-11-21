import 'package:material_ui/material_ui.dart';

import '../data/ads/no_ads.dart';
import '../data/billing/fake_billing_gateway.dart';
import '../domain/ports/ads_gateway.dart';
import '../domain/ports/billing_gateway.dart';

typedef Ads = (AdsGateway gateway, Widget Function() banner);

Ads createAds({required bool offline}) => (const NoAds(), () => const SizedBox.shrink());

BillingGateway createBilling({required bool fake}) => FakeBillingGateway();
