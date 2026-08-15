/// 図鑑。現行(Streamlit)の「📖 図鑑」に当たる。
///
/// 現行と同じものを出す:
///   詳細のドット絵 / 会った日数と近さ / **プロフィール3行**
///   (好きなもの・好きな場所・こわいもの) / 説明文
///
/// 「こわいもの」は GloBI の実際の捕食記録から。恣意的に足さない
/// (交渉不能の原則4「生態に誠実」)。
/// 庭が痩せても、ここの記録は減らない(原則2「罰しない」)。
library;

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'garden_state.dart';

/// 「こわいもの」の分類 → 表示名。現行 predators.py のラベルに合わせる。
const Map<String, String> kPredatorLabels = {
  'raptor': 'Hawks',
  'owl': 'Owls',
  'snake': 'Snakes',
  'mammal': 'Mammals',
  'cat': 'Cats',
  'corvid': 'Crows and jays',
  'other': 'Others',
};

class GuidePage extends StatelessWidget {
  final Garden? garden;
  const GuidePage({super.key, this.garden});

  @override
  Widget build(BuildContext context) {
    final g = garden;
    final met = (g?.observed.keys.toList() ?? [])
      ..sort((a, b) => (g!.observed[b] ?? 0).compareTo(g.observed[a] ?? 0));

    return Scaffold(
      appBar: AppBar(title: Text('Guide  ${met.length}/37')),
      body: met.isEmpty
          ? const Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('Plant something.\nThe birds will come on their own.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: kSub, height: 1.6)),
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
              itemCount: met.length,
              itemBuilder: (_, i) => _Card(g!, met[i]),
            ),
    );
  }
}

class _Card extends StatelessWidget {
  final Garden g;
  final String id;
  const _Card(this.g, this.id);

  String _name(Map<String, dynamic> m, String key) =>
      (m[key]?['english'] as String?) ?? key;

  @override
  Widget build(BuildContext context) {
    final b = (g.data.birds[id] as Map?) ?? const {};
    final count = g.observed[id] ?? 0;
    final detail = g.detailSpriteFor(id);
    final fears = (g.data.predators[id]?['categories'] as List?) ?? const [];

    return Card(
      elevation: 0,
      color: Colors.white,
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              if (detail != null)
                Image.asset(detail,
                    width: 64, height: 64, filterQuality: FilterQuality.none)
              else
                const Icon(Icons.flutter_dash, size: 48, color: kBar),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text((b['english'] as String?) ?? id,
                        style: const TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w600,
                            color: kInk)),
                    const SizedBox(height: 2),
                    Text(_closeness(count),
                        style: const TextStyle(fontSize: 13, color: kGreen)),
                  ],
                ),
              ),
              Text('$count days', style: const TextStyle(color: kSub)),
            ]),
            const SizedBox(height: 12),

            // ── プロフィール3行(現行と同じ並び) ──
            _Row('Likes', [
              for (final p in ((b['eats_plants'] as List?) ?? const []))
                if (g.data.plants[p] != null)
                  '${g.data.plants[p]?['icon'] ?? '🌱'} ${_name(g.data.plants, '$p')}',
              for (final i in ((b['eats_insects'] as List?) ?? const []))
                if (g.data.insects[i] != null) '🐛 ${_name(g.data.insects, '$i')}',
            ]),
            _Row('Home', [
              for (final x in ((b['biome_pref'] as List?) ?? const []))
                if (g.data.biomes[x] != null)
                  '${g.data.biomes[x]?['name_en'] ?? x}',
            ]),
            if (fears.isNotEmpty)
              _Row('Fears',
                  [for (final f in fears) kPredatorLabels['$f'] ?? '$f']),

            if (b['description_en'] != null) ...[
              const SizedBox(height: 10),
              Text(b['description_en'] as String,
                  style: const TextStyle(
                      fontSize: 14, color: kSub, height: 1.5)),
            ],
          ],
        ),
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

class _Row extends StatelessWidget {
  final String label;
  final List<String> items;
  const _Row(this.label, this.items);

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          width: 58,
          child: Text(label,
              style: const TextStyle(
                  fontSize: 12, fontWeight: FontWeight.w700, color: kSub)),
        ),
        Expanded(
          child: Text(items.join('  ·  '),
              style: const TextStyle(fontSize: 14, color: kInk, height: 1.5)),
        ),
      ]),
    );
  }
}
