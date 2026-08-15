/// ネットワーク。**なぜその鳥が来たのか**を、食べ物のつながりで見せる。
///
/// 交渉不能の原則4「生態に誠実」— 関係は恣意的に足さない。
/// 誰が何を食べるかはデータのとおりに繋ぐ。
library;

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
    // 食物網スコアの高い順。いま来られる見込みが強い鳥から見せる。
    final birds = web.birdFood.entries.where((e) => e.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    String name(Map<String, dynamic> m, String id) =>
        (m[id]?['english'] as String?) ?? id;

    return Scaffold(
      appBar: AppBar(title: const Text('Network')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          for (final e in birds) ...[
            Text(name(g.data.birds, e.key),
                style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w600, color: kInk)),
            const SizedBox(height: 6),
            // その鳥が「何を目当てに来られるか」。植えたものから虫を経て繋がる。
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final l in (web.birdLinks[e.key] ?? const []))
                  Chip(
                    avatar: Text(l.kind == 'plant'
                        ? ((g.data.plants[l.id]?['icon'] as String?) ?? '🌱')
                        : '🐛'),
                    label: Text(l.kind == 'plant'
                        ? name(g.data.plants, l.id)
                        : name(g.data.insects, l.id)),
                  ),
              ],
            ),
            const SizedBox(height: 20),
          ],
        ],
      ),
    );
  }
}
