/// App-wide state: who is signed in, their coins and items, what is equipped,
/// and the services behind them.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'economy/bet.dart';
import 'economy/catalog.dart';
import 'economy/inventory.dart';
import 'game/arena.dart';
import 'services/ads_service.dart';
import 'services/auth_service.dart';
import 'services/backend.dart';
import 'services/billing_service.dart';

enum PurchaseNotice { processing, done, pending, failed }

class AppState extends ChangeNotifier {
  final Catalog catalog;
  final OddsTable odds;
  final AuthService auth;
  final Backend? backend;
  final BillingService billing;
  final AdsService ads;

  /// True when there is no real server: offline demo or Firebase missing.
  final bool demo;

  /// True when the app expected Firebase but it is not configured, so only
  /// practice mode works.
  final bool serverMissing;

  final SharedPreferences? _prefs;

  AppUser? user;
  Profile profile = Profile.empty;
  String _equippedBall;
  String _equippedMap;

  /// A paid skin unlocked for the next round by watching an ad.
  String? trialBall;
  String? trialMap;

  int _roundsSinceAd = 0;
  bool busy = false;

  final _notices = StreamController<PurchaseNotice>.broadcast();
  Stream<PurchaseNotice> get purchaseNotices => _notices.stream;

  StreamSubscription<AppUser?>? _authSub;
  StreamSubscription<PurchaseUpdate>? _billingSub;

  AppState({
    required this.catalog,
    required this.odds,
    required this.auth,
    required this.backend,
    required this.billing,
    required this.ads,
    required this.demo,
    this.serverMissing = false,
    SharedPreferences? prefs,
  })  : _prefs = prefs,
        _equippedBall = prefs?.getString('ball') ?? 'ball_white',
        _equippedMap = prefs?.getString('map') ?? 'map_pentagon';

  static Future<(Catalog, OddsTable)> loadData() async {
    final catalog = Catalog.fromJson(
        jsonDecode(await rootBundle.loadString('assets/data/catalog.json')) as Map<String, dynamic>);
    final odds = OddsTable.fromJson(
        jsonDecode(await rootBundle.loadString('assets/data/odds.json')) as Map<String, dynamic>);
    return (catalog, odds);
  }

  Future<void> init() async {
    user = auth.user;
    _authSub = auth.changes.listen((u) {
      user = u;
      if (u == null) {
        profile = Profile.empty;
        notifyListeners();
      } else {
        unawaited(refreshProfile());
      }
    });
    _billingSub = billing.updates.listen(_onPurchase);
    await billing.init(
      consumables: catalog.consumableProductIds,
      nonConsumables: catalog.nonConsumableProductIds,
    );
    if (user != null) {
      await refreshProfile();
      // Picks up coin packs bought but not credited (app closed mid-purchase).
      unawaited(billing.restore());
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

  bool get signedIn => user != null;
  bool get canBet => signedIn && backend != null;
  bool get adsEnabled => !profile.removeAds;

  Inventory get inventory => Inventory(
        catalog: catalog,
        profile: profile,
        equippedBall: _equippedBall,
        equippedMap: _equippedMap,
      );

  /// Skins for the next round: a trial overrides what is equipped.
  String get roundBall => trialBall ?? inventory.ball;
  String get roundMap => trialMap ?? inventory.map;
  ArenaShape get roundShape => catalog.item(roundMap)?.shape ?? ArenaShape.pentagon;

  Future<void> refreshProfile() async {
    final b = backend;
    if (b == null || user == null) return;
    try {
      profile = await b.getProfile();
    } catch (_) {
      // Keep the last known profile; screens retry on their own.
    }
    notifyListeners();
  }

  Future<void> signIn() async {
    final u = await auth.signInWithGoogle();
    user = u;
    await refreshProfile();
    unawaited(billing.restore());
    notifyListeners();
  }

  Future<void> signOut() async {
    await auth.signOut();
    user = null;
    profile = Profile.empty;
    notifyListeners();
  }

  Future<void> deleteAccount() async {
    await backend?.deleteAccount();
    await auth.signOut();
    user = null;
    profile = Profile.empty;
    await _prefs?.remove('ball');
    await _prefs?.remove('map');
    _equippedBall = 'ball_white';
    _equippedMap = 'map_pentagon';
    notifyListeners();
  }

  void equip(String itemId) {
    if (!inventory.owns(itemId)) return;
    final item = catalog.item(itemId)!;
    if (item.kind == ItemKind.ball) {
      _equippedBall = itemId;
      _prefs?.setString('ball', itemId);
    } else {
      _equippedMap = itemId;
      _prefs?.setString('map', itemId);
    }
    notifyListeners();
  }

  /// Watches a rewarded ad and, if it completes, lends [itemId] for one round.
  Future<bool> tryWithAd(String itemId) async {
    final ok = await ads.showRewarded();
    if (!ok) return false;
    final item = catalog.item(itemId)!;
    if (item.kind == ItemKind.ball) {
      trialBall = itemId;
    } else {
      trialMap = itemId;
    }
    notifyListeners();
    return true;
  }

  Future<RoundTicket> startRound({required int band, required int betCents}) async {
    final shape = roundShape;
    if (betCents == 0 || !canBet) {
      return practiceTicket(shape: shape, band: band);
    }
    final t = await backend!.startRound(shape: shape, band: band, betCents: betCents);
    profile = profile.copyWith(balanceCents: t.balanceCents);
    notifyListeners();
    return t;
  }

  /// Called when a round's result screen opens. Clears trials and shows an
  /// interstitial every few rounds.
  Future<void> onRoundFinished() async {
    trialBall = null;
    trialMap = null;
    _roundsSinceAd++;
    notifyListeners();
    if (adsEnabled && _roundsSinceAd >= AppConfig.interstitialEveryRounds) {
      _roundsSinceAd = 0;
      await ads.showInterstitial();
    }
  }

  Future<void> buyWithCoins(String itemId) async {
    profile = await backend!.buyWithCoins(itemId);
    equip(itemId);
    notifyListeners();
  }

  Future<void> buyProduct(String productId) async {
    _notices.add(PurchaseNotice.processing);
    await billing.buy(productId);
  }

  Future<void> restorePurchases() => billing.restore();

  Future<void> _onPurchase(PurchaseUpdate u) async {
    switch (u.result) {
      case PurchaseResult.pending:
        _notices.add(PurchaseNotice.pending);
        return;
      case PurchaseResult.cancelled:
      case PurchaseResult.error:
        _notices.add(PurchaseNotice.failed);
        return;
      case PurchaseResult.purchased:
      case PurchaseResult.restored:
        break;
    }
    final b = backend;
    if (b == null || user == null || u.token == null) {
      // Not signed in: leave it uncompleted; it is redelivered after sign-in.
      return;
    }
    try {
      profile = await b.verifyPurchase(productId: u.productId, purchaseToken: u.token!);
      await u.complete();
      if (u.result == PurchaseResult.purchased) {
        final item = catalog.itemForProduct(u.productId);
        if (item != null) equip(item.id);
        _notices.add(PurchaseNotice.done);
      }
      notifyListeners();
    } catch (_) {
      // Not completed, so Google redelivers it and we retry on next launch.
      if (u.result == PurchaseResult.purchased) _notices.add(PurchaseNotice.failed);
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
