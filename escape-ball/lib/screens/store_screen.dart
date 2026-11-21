import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:material_ui/material_ui.dart';

import '../app_state.dart';
import '../economy/catalog.dart';
import '../game/skins.dart';
import '../l10n/strings.dart';
import '../services/auth_service.dart';
import '../services/backend.dart';
import 'common.dart';

const _names = <String, (String, String)>{
  'ball_white': ('Clássica', 'Classic'),
  'ball_neon': ('Neon', 'Neon'),
  'ball_ice': ('Gelo', 'Ice'),
  'ball_ghost': ('Fantasma', 'Ghost'),
  'ball_fire': ('Fogo', 'Fire'),
  'ball_rainbow': ('Arco-íris', 'Rainbow'),
  'map_pentagon': ('Pentágono Verde', 'Green Pentagon'),
  'map_square': ('Quadrado Laranja', 'Orange Square'),
  'map_octagon': ('Octógono Azul', 'Blue Octagon'),
  'map_hexagon': ('Hexágono Roxo', 'Purple Hexagon'),
  'map_triangle': ('Triângulo Vermelho', 'Red Triangle'),
};

String itemName(String id, bool pt) {
  final n = _names[id];
  return n == null ? id : (pt ? n.$1 : n.$2);
}

String _brl(double v) => 'R\$ ${v.toStringAsFixed(2).replaceAll('.', ',')}';

class StoreScreen extends StatefulWidget {
  final int initialTab;
  const StoreScreen({super.key, this.initialTab = 1});

  @override
  State<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends State<StoreScreen> {
  StreamSubscription<PurchaseNotice>? _sub;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sub ??= AppScope.read(context).purchaseNotices.listen((n) {
      if (!mounted) return;
      final s = S.of(context);
      switch (n) {
        case PurchaseNotice.processing:
          showSnack(context, s.processing);
        case PurchaseNotice.done:
          showSnack(context, s.purchaseDone);
        case PurchaseNotice.pending:
          showSnack(context, s.purchasePending);
        case PurchaseNotice.failed:
          showSnack(context, s.purchaseFailed);
      }
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return DefaultTabController(
      length: 4,
      initialIndex: widget.initialTab,
      child: Scaffold(
        appBar: AppBar(
          title: Text(s.store),
          actions: const [Padding(padding: EdgeInsets.only(right: 12), child: CoinChip())],
          bottom: TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              Tab(text: s.coinsTab),
              Tab(text: s.balls),
              Tab(text: s.maps),
              Tab(text: s.noAds),
            ],
          ),
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: TabBarView(
                  children: [
                    const _CoinsTab(),
                    const _ItemsTab(kind: ItemKind.ball),
                    const _ItemsTab(kind: ItemKind.map),
                    const _NoAdsTab(),
                  ],
                ),
              ),
              const BannerSlot(),
            ],
          ),
        ),
      ),
    );
  }
}

/// Runs [action] after making sure the player is signed in.
Future<void> _signedIn(BuildContext context, Future<void> Function() action) async {
  final app = AppScope.read(context);
  final s = S.of(context);
  try {
    if (!app.signedIn) await app.signIn();
    await action();
  } on SignInCancelled {
    return;
  } on BackendException catch (e) {
    if (context.mounted) {
      showSnack(context, e.message == 'insufficient-funds' ? s.notEnoughCoins : s.genericError);
    }
  } catch (_) {
    if (context.mounted) showSnack(context, s.genericError);
  }
}

class _CoinsTab extends StatelessWidget {
  const _CoinsTab();

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                const Icon(Icons.info_outline, color: Colors.white54),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(s.coinsDisclaimer,
                      style: const TextStyle(color: Colors.white70, fontSize: 13)),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        for (final p in app.catalog.coinPacks)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Card(
              child: ListTile(
                leading: const Icon(Icons.monetization_on, color: Color(0xFFFFD34D), size: 32),
                title: Text(s.coinPack(p.coins),
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
                trailing: FilledButton(
                  onPressed: app.serverMissing
                      ? null
                      : () => _signedIn(context, () => app.buyProduct(p.productId)),
                  child: Text(app.billing.prices[p.productId] ?? _brl(p.brl)),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ItemsTab extends StatelessWidget {
  final ItemKind kind;
  const _ItemsTab({required this.kind});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final items = app.catalog.ofKind(kind);
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 220,
        mainAxisSpacing: 12,
        crossAxisSpacing: 12,
        childAspectRatio: 0.62,
      ),
      itemCount: items.length,
      itemBuilder: (context, i) => _ItemCard(item: items[i]),
    );
  }
}

class _ItemCard extends StatelessWidget {
  final CatalogItem item;
  const _ItemCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    final inv = app.inventory;
    final owns = inv.owns(item.id);
    final equipped = item.kind == ItemKind.ball ? inv.ball == item.id : inv.map == item.id;
    final onTrial = app.trialBall == item.id || app.trialMap == item.id;

    Widget action;
    if (equipped) {
      action = OutlinedButton(onPressed: null, child: Text(s.equipped));
    } else if (owns) {
      action = FilledButton(onPressed: () => app.equip(item.id), child: Text(s.equip));
    } else if (item.price == PriceType.coins) {
      action = FilledButton.icon(
        onPressed: app.serverMissing
            ? null
            : () => _signedIn(context, () => app.buyWithCoins(item.id)),
        icon: const Icon(Icons.monetization_on, size: 18),
        label: Text('${item.coins}'),
      );
    } else {
      action = FilledButton(
        onPressed: app.serverMissing
            ? null
            : () => _signedIn(context, () => app.buyProduct(item.productId!)),
        child: Text(app.billing.prices[item.productId] ?? _brl(item.brl ?? 0)),
      );
    }

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: equipped ? kNeon : const Color(0xFF1C2B24), width: equipped ? 2 : 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: CustomPaint(
                painter: item.kind == ItemKind.ball
                    ? _BallPreview(ballSkin(item.id))
                    : _MapPreview(mapSkin(item.id)),
              ),
            ),
            const SizedBox(height: 6),
            Text(itemName(item.id, s.pt),
                textAlign: TextAlign.center,
                maxLines: 2,
                style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            action,
            if (!owns)
              TextButton(
                onPressed: onTrial
                    ? null
                    : () async {
                        final ok = await app.tryWithAd(item.id);
                        if (context.mounted) showSnack(context, ok ? s.trialActive : s.adNotReady);
                      },
                child: Text(onTrial ? s.trialActive : s.tryWithAd,
                    textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }
}

class _BallPreview extends CustomPainter {
  final BallSkin skin;
  _BallPreview(this.skin);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = math.min(size.width, size.height) * 0.16;
    for (var i = 0; i < 6; i++) {
      final f = (i + 1) / 7;
      final color = switch (skin.trail) {
        TrailStyle.fire => Color.lerp(const Color(0xFFFF2A00), const Color(0xFFFFD34D), f)!,
        TrailStyle.rainbow => HSVColor.fromAHSV(1, i * 55.0, 0.9, 1).toColor(),
        _ => skin.glow,
      };
      canvas.drawCircle(c + Offset(-(6 - i) * r * 0.55, -(6 - i) * r * 0.35),
          r * (0.4 + 0.6 * f), Paint()..color = color.withValues(alpha: 0.4 * f));
    }
    canvas.drawCircle(
        c,
        r * 2,
        Paint()
          ..color = skin.glow.withValues(alpha: 0.4 * skin.opacity)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10));
    canvas.drawCircle(c, r, Paint()..color = skin.core.withValues(alpha: skin.opacity));
  }

  @override
  bool shouldRepaint(covariant _BallPreview old) => old.skin != skin;
}

class _MapPreview extends CustomPainter {
  final MapSkin skin;
  _MapPreview(this.skin);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final R = math.min(size.width, size.height) * 0.42;
    final n = skin.shape.sides;
    canvas.drawRRect(
        RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(10)),
        Paint()..color = skin.background);
    final path = Path();
    final phase = -math.pi / 2 - math.pi / n;
    for (var k = 0; k <= n; k++) {
      final a = phase + 2 * math.pi * k / n;
      final p = c + Offset(math.cos(a), math.sin(a)) * R;
      if (k == 0) {
        path.moveTo(p.dx, p.dy);
      } else {
        path.lineTo(p.dx, p.dy);
      }
    }
    final shader = ui.Gradient.linear(c - Offset(R, R), c + Offset(R, R), [skin.wallA, skin.wallB]);
    canvas.drawPath(
        path,
        Paint()
          ..shader = shader
          ..style = PaintingStyle.stroke
          ..strokeWidth = 6
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4));
    canvas.drawPath(
        path,
        Paint()
          ..shader = shader
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5);
    canvas.drawCircle(c, 5, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant _MapPreview old) => old.skin != skin;
}

class _NoAdsTab extends StatelessWidget {
  const _NoAdsTab();

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final s = S.of(context);
    final owned = app.profile.removeAds;
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(owned ? Icons.verified : Icons.block, size: 72, color: kNeon),
          const SizedBox(height: 16),
          Text(s.removeAdsTitle, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Text(owned ? s.removeAdsOwned : s.removeAdsBody,
              textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: 24),
          if (!owned)
            NeonButton(
              label: app.billing.prices[app.catalog.removeAdsProductId] ?? _brl(app.catalog.removeAdsBrl),
              onPressed: app.serverMissing
                  ? null
                  : () => _signedIn(context, () => app.buyProduct(app.catalog.removeAdsProductId)),
            ),
        ],
      ),
    );
  }
}
