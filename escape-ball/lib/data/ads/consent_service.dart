/// Google's consent form (UMP). Required before showing ads to users in the
/// EU, UK and Switzerland; elsewhere it completes without showing anything.
library;

import 'dart:async';

import 'package:google_mobile_ads/google_mobile_ads.dart';

class ConsentService {
  bool privacyOptionsRequired = false;

  /// Updates consent info and shows the form if needed. Completes with
  /// whether ads may be requested.
  Future<bool> gather() async {
    final done = Completer<void>();
    ConsentInformation.instance.requestConsentInfoUpdate(
      ConsentRequestParameters(),
      () async {
        await ConsentForm.loadAndShowConsentFormIfRequired((_) {});
        if (!done.isCompleted) done.complete();
      },
      (_) {
        // Offline or misconfigured: fall back to whatever consent is cached.
        if (!done.isCompleted) done.complete();
      },
    );
    await done.future;
    privacyOptionsRequired = await ConsentInformation.instance.getPrivacyOptionsRequirementStatus() ==
        PrivacyOptionsRequirementStatus.required;
    return ConsentInformation.instance.canRequestAds();
  }

  Future<void> showPrivacyOptions() async {
    final done = Completer<void>();
    await ConsentForm.showPrivacyOptionsForm((_) => done.complete());
    await done.future;
  }
}
