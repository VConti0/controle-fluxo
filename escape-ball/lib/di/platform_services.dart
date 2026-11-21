/// Picks the real store and ad implementations on Android/iOS, and offline
/// ones on the web, where the ad and billing plugins do not exist.
library;

export 'platform_services_stub.dart'
    if (dart.library.io) 'platform_services_mobile.dart';
