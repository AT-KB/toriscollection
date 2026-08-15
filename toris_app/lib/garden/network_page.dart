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
    // 現行と同じ絞り込み: 食べ物の経路がある鳥だけを図に出す
    // (全37種を出すと、来られない鳥で埋まって形が見えない)。
    final birdsNear = web.birdFood.entries
        .where((e) => e.value > 0)
        .map((e) => e.key)
        .toList()
      ..sort((a, b) => web.birdFood[b]!.compareTo(web.birdFood[a]!));

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
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: const [
            _Key(color: Color(0xFF7BA87B), text: 'Plant'),
            _Key(color: Color(0xFFC9A227), text: 'Insect'),
            _Key(color: Color(0xFF3F6FA8), text: 'Bird'),
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
  final Map<String, List<String>> links; // 鳥 → 直接の食べ物
  final Map<String, List<String>> insectEats; // 虫 → 食草
  final String Function(String) label;
  final Set<String> residents;

  _WebPainter({
    required this.plants,
    required this.insects,
    required this.birds,
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
    void shell(List<String> nodes, double r) {
      if (nodes.isEmpty) return;
      final n = nodes.length;
      final offset = n.isEven ? 0.0 : pi / n;
      for (var i = 0; i < n; i++) {
        final th = 2 * pi * i / n + offset;
        pos[nodes[i]] = Offset(cx + r * cos(th), cy + r * sin(th));
      }
    }

    shell(plants, maxR * 0.30);
    shell(insects, maxR * 0.58);
    shell(birds, maxR * 0.85);

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

    void node(String id, Color c, double r, {bool ring = false}) {
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
      final tp = TextPainter(
        text: TextSpan(
            text: label(id),
            style: const TextStyle(fontSize: 10, color: kInk)),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: 90);
      tp.paint(canvas, p + Offset(-tp.width / 2, r + 3));
    }

    for (final p in plants) {
      node(p, const Color(0xFF7BA87B), 7);
    }
    for (final i in insects) {
      node(i, const Color(0xFFC9A227), 6);
    }
    for (final b in birds) {
      // いま来ている鳥は輪で囲う
      node(b, const Color(0xFF3F6FA8), 8, ring: residents.contains(b));
    }
  }

  @override
  bool shouldRepaint(covariant _WebPainter old) =>
      old.plants != plants || old.insects != insects || old.birds != birds;
}
