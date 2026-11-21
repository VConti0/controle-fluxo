/// Store catalog: what can be bought and how. Prices and product ids come
/// from `assets/data/catalog.json`, which the server reads too. How each
/// skin looks lives in `skins.dart`.
library;

import '../game/arena.dart';

enum ItemKind { ball, map }

enum PriceType { free, coins, paid }

class CatalogItem {
  final String id;
  final ItemKind kind;
  final PriceType price;

  /// Whole coins, for [PriceType.coins].
  final int coins;

  /// Play product id, for [PriceType.paid].
  final String? productId;

  /// Suggested price in reais, shown when the store price is unavailable.
  final double? brl;

  /// Map shape, for map items.
  final ArenaShape? shape;

  const CatalogItem({
    required this.id,
    required this.kind,
    required this.price,
    this.coins = 0,
    this.productId,
    this.brl,
    this.shape,
  });

  factory CatalogItem.fromJson(Map<String, dynamic> j) => CatalogItem(
        id: j['id'] as String,
        kind: ItemKind.values.byName(j['kind'] as String),
        price: PriceType.values.byName(j['price'] as String),
        coins: (j['coins'] as num?)?.toInt() ?? 0,
        productId: j['productId'] as String?,
        brl: (j['brl'] as num?)?.toDouble(),
        shape: j['shape'] == null ? null : ArenaShape.byName(j['shape'] as String),
      );
}

class CoinPack {
  final String productId;
  final int coins;
  final double brl;
  const CoinPack(this.productId, this.coins, this.brl);

  factory CoinPack.fromJson(Map<String, dynamic> j) => CoinPack(
        j['productId'] as String,
        (j['coins'] as num).toInt(),
        (j['brl'] as num).toDouble(),
      );
}

class Catalog {
  final String removeAdsProductId;
  final double removeAdsBrl;
  final List<CoinPack> coinPacks;
  final List<CatalogItem> items;
  final int minBetCoins;
  final int maxBetCoins;

  const Catalog({
    required this.removeAdsProductId,
    required this.removeAdsBrl,
    required this.coinPacks,
    required this.items,
    required this.minBetCoins,
    required this.maxBetCoins,
  });

  factory Catalog.fromJson(Map<String, dynamic> j) {
    final ra = j['removeAds'] as Map<String, dynamic>;
    final bet = j['bet'] as Map<String, dynamic>;
    return Catalog(
      removeAdsProductId: ra['productId'] as String,
      removeAdsBrl: (ra['brl'] as num).toDouble(),
      coinPacks: [
        for (final p in j['coinPacks'] as List) CoinPack.fromJson(p as Map<String, dynamic>),
      ],
      items: [
        for (final i in j['items'] as List) CatalogItem.fromJson(i as Map<String, dynamic>),
      ],
      minBetCoins: (bet['minCoins'] as num).toInt(),
      maxBetCoins: (bet['maxCoins'] as num).toInt(),
    );
  }

  CatalogItem? item(String id) {
    for (final i in items) {
      if (i.id == id) return i;
    }
    return null;
  }

  List<CatalogItem> ofKind(ItemKind k) => [for (final i in items) if (i.kind == k) i];

  /// Every Play product: coin packs (consumable) and the rest (one-time).
  Set<String> get consumableProductIds => {for (final p in coinPacks) p.productId};

  Set<String> get nonConsumableProductIds => {
        removeAdsProductId,
        for (final i in items)
          if (i.productId != null) i.productId!,
      };

  CoinPack? pack(String productId) {
    for (final p in coinPacks) {
      if (p.productId == productId) return p;
    }
    return null;
  }

  CatalogItem? itemForProduct(String productId) {
    for (final i in items) {
      if (i.productId == productId) return i;
    }
    return null;
  }
}
