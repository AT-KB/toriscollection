/// 図鑑。**会った鳥だけ**が並ぶ。会うほど近くなる(回数がそのまま出る)。
///
/// 交渉不能の原則2「罰しない」— 庭が痩せても、ここの記録は減らない。
library;

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'garden_state.dart';

class GuidePage extends StatelessWidget {
  final Garden? garden;
  const GuidePage({super.key, this.garden});

  @override
  Widget build(BuildContext context) {
    final g = garden;
    final met = (g?.observed.keys.toList() ?? [])
      ..sort((a, b) => (g!.observed[b] ?? 0).compareTo(g.observed[a] ?? 0));

    return Scaffold(
      appBar: AppBar(title: const Text('Guide')),
      body: met.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('No birds yet.\nPlant something and look outside.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: kSub, height: 1.6)),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
              itemCount: met.length,
              separatorBuilder: (_, _) => const Divider(height: 22),
              itemBuilder: (_, i) {
                final id = met[i];
                final b = g!.data.birds[id] as Map?;
                final count = g.observed[id] ?? 0;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(
                        child: Text((b?['english'] as String?) ?? id,
                            style: const TextStyle(
                                fontSize: 19,
                                fontWeight: FontWeight.w600,
                                color: kInk)),
                      ),
                      Text('met $count', style: const TextStyle(color: kSub)),
                    ]),
                    const SizedBox(height: 4),
                    // 会うほど近くで鳴く。その段階をそのまま出す。
                    Text(_closeness(count),
                        style: const TextStyle(fontSize: 13, color: kGreen)),
                    if (b?['description_en'] != null) ...[
                      const SizedBox(height: 8),
                      Text(b!['description_en'] as String,
                          style: const TextStyle(
                              fontSize: 14, color: kSub, height: 1.5)),
                    ],
                  ],
                );
              },
            ),
    );
  }

  /// 近さの段階。`radio.py` の _obs_to_depth と同じ区切り。
  String _closeness(int count) {
    if (count >= 6) return 'Sings right beside you';
    if (count >= 3) return 'Comes a little closer';
    return 'Still keeping its distance';
  }
}
