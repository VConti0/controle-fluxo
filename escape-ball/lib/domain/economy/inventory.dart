/// What the player owns and has equipped.
library;

import '../game/arena.dart';
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

  /// Saved choice per kind; may name something no longer owned.
  final Map<ItemKind, String> equipped;

  const Inventory({required this.catalog, required this.profile, required this.equipped});

  bool owns(String itemId) {
    final item = catalog.item(itemId);
    if (item == null) return false;
    return item.price == PriceType.free || profile.owned.contains(itemId);
  }

  /// Equipped item of a kind, falling back to the default if the player no
  /// longer owns what was saved (for example after signing out).
  String equippedOf(ItemKind kind) {
    final id = equipped[kind];
    return id != null && owns(id) ? id : catalog.defaultOf(kind).id;
  }

  String get ball => equippedOf(ItemKind.ball);
  String get map => equippedOf(ItemKind.map);
}

/// Skins used for one round: a trial unlocked by an ad overrides what is
/// equipped.
class RoundLoadout {
  final String ball;
  final String map;
  final ArenaShape shape;
  const RoundLoadout(this.ball, this.map, this.shape);

  factory RoundLoadout.from(Inventory inv, Map<ItemKind, String> trials) {
    final ball = trials[ItemKind.ball] ?? inv.ball;
    final map = trials[ItemKind.map] ?? inv.map;
    return RoundLoadout(ball, map, inv.catalog.item(map)?.shape ?? ArenaShape.pentagon);
  }
}
