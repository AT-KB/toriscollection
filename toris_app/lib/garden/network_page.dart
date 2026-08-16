/// ネットワーク図。現行(Streamlit)の「🕸️ ネットワーク」に当たる。
///
/// **図として描く。** 一覧では「誰が誰を支えているか」の形が見えない。
/// 配置は現行の `force_directed_layout` と同じ同心円(シェル):
///   内側から  植物 → 虫 → 来られる鳥 → 来られない鳥
/// 各円のなかは、つながりの多い順に並べる。
///
/// 交渉不能の原則4「生態に誠実」— 線は食べる/食べられるの記録だけで引く。
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'garden_state.dart';

class NetworkPage extends StatelessWidget {
  final Garden? garden;
  const NetworkPage({super.key, this.garden});

  @override
  Widget build(BuildContext context) {
    final g = garden;
    if (g == null || g.planted.isEmpty) {
      return Scaffold(
        appBar: AppBar(title: const Text('Network')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(32),
            child: Text('Plant something first.\nThen you can see who it feeds.',
                textAlign: TextAlign.center,
                style: TextStyle(color: kSub, height: 1.6)),
          ),
        ),
      );
    }

    final web = g.web;
    // 現行と同じ: **届く鳥は外周に、届かない鳥は最外周に極小で**置く。
    // 「どれだけの鳥に手が届いていないか」も含めて図なので、消さない。
    final birdsNear = web.birdFood.entries
        .where((e) => e.value > 0)
        .map((e) => e.key)
        .toList()
      ..sort((a, b) => web.birdFood[b]!.compareTo(web.birdFood[a]!));
    final birdsFar = web.birdFood.entries
        .where((e) => e.value <= 0)
        .map((e) => e.key)
        .toList()
      ..sort();

    return Scaffold(
      appBar: AppBar(title: const Text('Network')),
      body: Column(children: [
        Expanded(
          child: InteractiveViewer(
            minScale: 0.6,
            maxScale: 3.0,
            child: CustomPaint(
              size: Size.infinite,
              painter: _WebPainter(
                plants: web.plants.keys.toList(),
                insects: web.insects.keys.toList(),
                birds: birdsNear,
                birdsFar: birdsFar,
                birdColor: (id) {
                  final c = g.data.birds[id]?['color'] as String?;
                  if (c == null || !c.startsWith('#')) return null;
                  return Color(int.parse('FF${c.substring(1)}', radix: 16));
                },
                links: {
                  for (final b in birdsNear)
                    b: (web.birdLinks[b] ?? const []).map((l) => l.id).toList()
                },
                insectEats: {
                  for (final i in web.insects.keys)
                    i: ((g.data.insects[i]?['eats_plants'] as List?) ?? const [])
                        .map((e) => '$e')
                        .where(web.plants.containsKey)
                        .toList()
                },
                label: (id) =>
                    (g.data.plants[id]?['english'] ??
                            g.data.insects[id]?['english'] ??
                            g.data.birds[id]?['english'] ??
                            id) as String,
                residents: g.visiting.toSet(),
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 18),
          // ⚠️ **凡例の色は、図で実際に使っている色にすること。**
          // 以前は虫が黄・鳥が青と書いてあったが、図では虫は肌色、
          // 来た鳥はその鳥自身の色で描いていた(2026-08-16 の監査で発覚)。
          child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: const [
                _Key(color: Color(0xFF4A8A4A), text: 'Plant'),
                _Key(color: Color(0xFFE8C0A0), text: 'Insect'),
                _Key(color: Color(0xFFC8D4E4), text: 'Bird'),
              ]),
        ),
      ]),
    );
  }
}

class _Key extends StatelessWidget {
  final Color color;
  final String text;
  const _Key({required this.color, required this.text});
  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(text, style: const TextStyle(fontSize: 13, color: kSub)),
      ]);
}

class _WebPainter extends CustomPainter {
  final List<String> plants;
  final List<String> insects;
  final List<String> birds;
  final List<String> birdsFar;
  final Color? Function(String) birdColor;
  final Map<String, List<String>> links; // 鳥 → 直接の食べ物
  final Map<String, List<String>> insectEats; // 虫 → 食草
  final String Function(String) label;
  final Set<String> residents;

  _WebPainter({
    required this.plants,
    required this.insects,
    required this.birds,
    required this.birdsFar,
    required this.birdColor,
    required this.links,
    required this.insectEats,
    required this.label,
    required this.residents,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    final maxR = min(size.width, size.height) * 0.42;
    final pos = <String, Offset>{};

    // 同心円に並べる。現行の shells と同じ半径比。
    //
    // ⚠️ **輪ごとに開始角をずらすこと。** ずらさないと、植物2・虫2・鳥1の
    // ような**小さい庭で全部が同じ軸(0°と180°)に乗り、横一直線になる**。
    // 庭は常に小さい(植物は最大4)ので、これが例外ではなく常態だった
    // (2026-08-16 の実機監査で発覚)。
    void shell(List<String> nodes, double r, double phase) {
      if (nodes.isEmpty) return;
      final n = nodes.length;
      for (var i = 0; i < n; i++) {
        final th = 2 * pi * i / n + phase;
        pos[nodes[i]] = Offset(cx + r * cos(th), cy + r * sin(th));
      }
    }

    // 現行と同じ半径比。内側から 植物 → 虫 → 届く鳥 → 届かない鳥。
    // 開始角は輪ごとに黄金角ずつ回す(何羽・何株でも重なりにくい)。
    const golden = 2.399963229728653; // 黄金角(ラジアン)
    shell(plants, maxR * 0.30, -pi / 2);
    shell(insects, maxR * 0.58, -pi / 2 + golden);
    shell(birds, maxR * 0.85, -pi / 2 + golden * 2);
    shell(birdsFar, maxR * 1.00, -pi / 2 + golden * 3);

    // 線: 植物 → 虫 → 鳥
    final line = Paint()
      ..color = const Color(0x33556B4F)
      ..strokeWidth = 1.4;
    insectEats.forEach((i, ps) {
      for (final p in ps) {
        if (pos[i] != null && pos[p] != null) {
          canvas.drawLine(pos[p]!, pos[i]!, line);
        }
      }
    });
    links.forEach((b, srcs) {
      for (final s in srcs) {
        if (pos[b] != null && pos[s] != null) {
          canvas.drawLine(pos[s]!, pos[b]!, line);
        }
      }
    });

    void node(String id, Color c, double r,
        {bool ring = false, bool label = false}) {
      final p = pos[id];
      if (p == null) return;
      canvas.drawCircle(p, r, Paint()..color = c);
      if (ring) {
        canvas.drawCircle(
            p,
            r + 3,
            Paint()
              ..color = c
              ..style = PaintingStyle.stroke
              ..strokeWidth = 2);
      }
      // 名前は、植物・虫・来た鳥にだけ。全部に付けると図が読めない。
      if (!label) return;
      final tp = TextPainter(
        text: TextSpan(
            text: this.label(id),
            style: const TextStyle(fontSize: 10, color: kInk)),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: 90);
      // 名前は**中心から外向き**に置く。節の真下に固定すると、
      // 内側の輪の名前が外側の節と重なる(実機で重なった)。
      final away = (p - Offset(cx, cy));
      final dir = away.distance < 1 ? const Offset(0, 1) : away / away.distance;
      final anchor = p + dir * (r + 6);
      tp.paint(
          canvas,
          anchor +
              Offset(-tp.width / 2, dir.dy >= 0 ? 0 : -tp.height));
    }

    // 大きさと濃さは現行の node_style と同じ考え方:
    //   植物は大きく濃い緑 / 虫は小さい肌色 /
    //   来た鳥はその鳥の色で大きく / 届く鳥は淡く / 届かない鳥は極小のグレー
    for (final p in plants) {
      node(p, const Color(0xFF4A8A4A), 9, label: true);
    }
    for (final i in insects) {
      node(i, const Color(0xFFE8C0A0), 6, label: true);
    }
    for (final b in birds) {
      final resident = residents.contains(b);
      node(b, resident ? (birdColor(b) ?? const Color(0xFF2A5AA8)) : const Color(0xFFC8D4E4),
          resident ? 10 : 6,
          ring: resident, label: resident);
    }
    for (final b in birdsFar) {
      node(b, const Color(0xFFECECEC), 3);
    }
  }

  @override
  bool shouldRepaint(covariant _WebPainter old) =>
      old.plants != plants || old.insects != insects || old.birds != birds;
}
