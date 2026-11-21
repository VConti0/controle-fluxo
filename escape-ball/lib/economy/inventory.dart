/// What the player owns and has equipped.
library;

import 'catalog.dart';

/// Account state as the server reports it.
class Profile {
  final int balanceCents;
  final Set<String> owned;
  final bool removeAds;

  const Profile({this.balanceCents = 0, this.owned = const {}, this.removeAds = false});

  static const empty = Profile();

  factory Profile.fromJson(Map<String, dynamic> j) => Profile(
        balanceCents: (j['balance'] as num?)?.toInt() ?? 0,
        owned: {for (final o in (j['owned'] as List? ?? const [])) o as String},
        removeAds: j['removeAds'] as bool? ?? false,
      );

  Map<String, dynamic> toJson() => {
        'balance': balanceCents,
        'owned': owned.toList()..sort(),
        'removeAds': removeAds,
      };

  Profile copyWith({int? balanceCents, Set<String>? owned, bool? removeAds}) => Profile(
        balanceCents: balanceCents ?? this.balanceCents,
        owned: owned ?? this.owned,
        removeAds: removeAds ?? this.removeAds,
      );
}

class Inventory {
  final Catalog catalog;
  final Profile profile;
  final String equippedBall;
  final String equippedMap;

  const Inventory({
    required this.catalog,
    required this.profile,
    required this.equippedBall,
    required this.equippedMap,
  });

  bool owns(String itemId) {
    final item = catalog.item(itemId);
    if (item == null) return false;
    return item.price == PriceType.free || profile.owned.contains(itemId);
  }

  /// Equipped ids, falling back to the free default if the player no longer
  /// owns what was saved (for example after signing out).
  String get ball => owns(equippedBall) ? equippedBall : 'ball_white';
  String get map => owns(equippedMap) ? equippedMap : 'map_pentagon';
}
