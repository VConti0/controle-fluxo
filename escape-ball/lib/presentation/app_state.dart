// Private fields set from named parameters: Dart does not allow private
// named initializing formals.
// ignore_for_file: prefer_initializing_formals

/// Presentation state shared by the screens: who is signed in, their coins
/// and items, and what is equipped. Depends only on domain ports and use
/// cases; the implementations are chosen in `di/bootstrap.dart`.
library;

import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../config.dart';
import '../domain/account/app_user.dart';
import '../domain/economy/bet.dart';
import '../domain/economy/catalog.dart';
import '../domain/economy/inventory.dart';
import '../domain/economy/round_ticket.dart';
import '../domain/ports/ads_gateway.dart';
import '../domain/ports/auth_repository.dart';
import '../domain/ports/billing_gateway.dart';
import '../domain/ports/economy_repository.dart';
import '../domain/ports/preferences_store.dart';
import '../domain/usecases/bet_options.dart';
import '../domain/usecases/play_round.dart';
import '../domain/usecases/process_purchase.dart';

enum PurchaseNotice { processing, done, pending, failed }

enum AppMode {
  /// Firebase, Play Store and AdMob.
  online,

  /// No server: offline demo (web or OFFLINE=true), fake coins on the device.
  demo,

  /// Firebase not configured: practice only.
  serverMissing,
}

class AppState extends ChangeNotifier {
  final Catalog catalog;
  final OddsTable odds;
  final AppMode mode;
  final AuthRepository _auth;
  final EconomyRepository? _economy;
  final BillingGateway _billing;
  final AdsGateway _ads;
  final Widget Function() _bannerBuilder;
  final PreferencesStore _prefs;
  final PlayRound _playRound;
  final ProcessPurchase _processPurchase;
  final BetOptions betOptions;

  AppUser? user;
  Profile profile = Profile.empty;
  final Map<ItemKind, String> _equipped = {};

  /// Paid skins lent for the next round by watching an ad.
  final Map<ItemKind, String> _trials = {};

  int _roundsSinceAd = 0;

  final _notices = StreamController<PurchaseNotice>.broadcast();
  Stream<PurchaseNotice> get purchaseNotices => _notices.stream;

  StreamSubscription<AppUser?>? _authSub;
  StreamSubscription<PurchaseUpdate>? _billingSub;

  AppState({
    required this.catalog,
    required this.odds,
    required this.mode,
    required AuthRepository auth,
    required EconomyRepository? economy,
    required BillingGateway billing,
    required AdsGateway ads,
    required Widget Function() bannerBuilder,
    required PreferencesStore prefs,
  })  : _auth = auth,
        _economy = economy,
        _billing = billing,
        _ads = ads,
        _bannerBuilder = bannerBuilder,
        _prefs = prefs,
        _playRound = PlayRound(economy),
        _processPurchase = ProcessPurchase(economy),
        betOptions = BetOptions(catalog) {
    for (final kind in ItemKind.values) {
      final saved = prefs.getString(_prefKey(kind));
      if (saved != null) _equipped[kind] = saved;
    }
  }

  static String _prefKey(ItemKind kind) => kind.name; // 'ball' / 'map'

  Future<void> init() async {
    user = _auth.user;
    _authSub = _auth.changes.listen((u) {
      user = u;
      if (u == null) {
        profile = Profile.empty;
        notifyListeners();
      } else {
        unawaited(refreshProfile());
      }
    });
    _billingSub = _billing.updates.listen(_onPurchase);
    await _billing.init(
      consumables: catalog.consumableProductIds,
      nonConsumables: catalog.nonConsumableProductIds,
    );
    if (user != null) {
      await refreshProfile();
      // Picks up coin packs bought but not credited (app closed mid-purchase).
      unawaited(_billing.restore());
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _authSub?.cancel();
    _billingSub?.cancel();
    _notices.close();
    super.dispose();
  }

  // ----- read models for the screens -------------------------------------

  bool get signedIn => user != null;
  bool get canBet => signedIn && _playRound.canBet;
  bool get serverMissing => mode == AppMode.serverMissing;
  bool get isDemo => mode != AppMode.online;
  bool get adsEnabled => !profile.removeAds;
  bool get privacyOptionsRequired => _ads.privacyOptionsRequired;

  Inventory get inventory => Inventory(catalog: catalog, profile: profile, equipped: _equipped);
  RoundLoadout get loadout => RoundLoadout.from(inventory, _trials);
  bool onTrial(String itemId) => _trials.containsValue(itemId);

  /// The store's localised price, or null if the store has not loaded it.
  String? storePrice(String productId) => _billing.prices[productId];

  Widget banner() => adsEnabled ? _bannerBuilder() : const SizedBox.shrink();

  // ----- account ------------------------------------------------------------

  Future<void> refreshProfile() async {
    final economy = _economy;
    if (economy == null || user == null) return;
    try {
      profile = await economy.getProfile();
    } catch (_) {
      // Keep the last known profile; screens retry on their own.
    }
    notifyListeners();
  }

  /// Throws `SignInCancelled` or another `Failure`.
  Future<void> signIn() async {
    user = await _auth.signInWithGoogle();
    await refreshProfile();
    unawaited(_billing.restore());
    notifyListeners();
  }

  Future<void> signOut() async {
    await _auth.signOut();
    user = null;
    profile = Profile.empty;
    notifyListeners();
  }

  Future<void> deleteAccount() async {
    await _economy?.deleteAccount();
    await _auth.signOut();
    user = null;
    profile = Profile.empty;
    _equipped.clear();
    for (final kind in ItemKind.values) {
      await _prefs.remove(_prefKey(kind));
    }
    notifyListeners();
  }

  Future<void> showPrivacyOptions() => _ads.showPrivacyOptions();

  // ----- skins --------------------------------------------------------------

  void equip(String itemId) {
    if (!inventory.owns(itemId)) return;
    final kind = catalog.item(itemId)!.kind;
    _equipped[kind] = itemId;
    _prefs.setString(_prefKey(kind), itemId);
    notifyListeners();
  }

  /// Watches a rewarded ad and, if it completes, lends [itemId] for one round.
  Future<bool> tryWithAd(String itemId) async {
    final ok = await _ads.showRewarded();
    if (!ok) return false;
    _trials[catalog.item(itemId)!.kind] = itemId;
    notifyListeners();
    return true;
  }

  /// Throws `InsufficientFunds` or another `Failure`.
  Future<void> buyWithCoins(String itemId) async {
    profile = await _economy!.buyWithCoins(itemId);
    equip(itemId);
    notifyListeners();
  }

  // ----- rounds -------------------------------------------------------------

  /// Throws `InsufficientFunds` or another `Failure`.
  Future<RoundTicket> startRound({required int band, required int betCents}) async {
    final t = await _playRound(
      shape: loadout.shape,
      band: band,
      betCents: betCents,
      signedIn: signedIn,
    );
    if (t.balanceCents != null) {
      profile = profile.copyWith(balanceCents: t.balanceCents);
      notifyListeners();
    }
    return t;
  }

  /// Called by the round flow when a round ends: clears trials and shows an
  /// interstitial every few rounds.
  Future<void> finishRound() async {
    _trials.clear();
    _roundsSinceAd++;
    notifyListeners();
    if (adsEnabled && _roundsSinceAd >= AppConfig.interstitialEveryRounds) {
      _roundsSinceAd = 0;
      await _ads.showInterstitial();
    }
  }

  // ----- store purchases ----------------------------------------------------

  Future<void> buyProduct(String productId) async {
    _notices.add(PurchaseNotice.processing);
    await _billing.buy(productId);
  }

  Future<void> restorePurchases() => _billing.restore();

  Future<void> _onPurchase(PurchaseUpdate u) async {
    final outcome = await _processPurchase(u, signedIn: signedIn);
    switch (outcome) {
      case PurchaseCredited(:final profile, :final productId, :final isNew):
        this.profile = profile;
        if (isNew) {
          final item = catalog.itemForProduct(productId);
          if (item != null) equip(item.id);
          _notices.add(PurchaseNotice.done);
        }
        notifyListeners();
      case PurchaseAwaitingPayment():
        _notices.add(PurchaseNotice.pending);
      case PurchaseFailed(:final userVisible):
        if (userVisible) _notices.add(PurchaseNotice.failed);
      case PurchaseDeferred():
        break;
    }
  }
}

/// Gives widgets access to [AppState] and rebuilds them when it changes.
class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
      : super(notifier: state);

  static AppState of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;

  static AppState read(BuildContext context) =>
      context.getInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
