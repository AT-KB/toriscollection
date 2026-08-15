/// 図鑑。現行(Streamlit)の「📖 図鑑」に当たる。
///
/// **全37種が折りたたみ(プルダウン)で並ぶ。** 開くと中身が見える。
/// 見た目は3段階で、儀式を経て近くで会うまで正体は分からない:
///   ❓ まだ来ていない  → 名前も「???」
///   🐦 来訪済み        → 名前は分かるが、絵はまだ出ない
///   🪶 近くで出会った  → **ドット絵が出る**
///
/// 並びは「地域別 / レア度順」の2通り(現行の segmented_control と同じ)。
/// 庭が痩せても、ここの記録は減らない(交渉不能の原則2「罰しない」)。
library;

import 'package:flutter/material.dart';
import 'package:toris_core/toris_core.dart' as core;

import '../ui/theme.dart';
import 'garden_state.dart';

/// 「こわいもの」の分類 → 表示名。
const Map<String, String> kPredatorLabels = {
  'raptor': 'Hawks',
  'owl': 'Owls',
  'snake': 'Snakes',
  'mammal': 'Mammals',
  'cat': 'Cats',
  'corvid': 'Crows and jays',
  'other': 'Others',
};

class GuidePage extends StatefulWidget {
  final Garden? garden;
  const GuidePage({super.key, this.garden});

  @override
  State<GuidePage> createState() => _GuidePageState();
}

class _GuidePageState extends State<GuidePage> {
  /// 並び。現行と同じ2通り。
  String _sort = 'region';

  @override
  Widget build(BuildContext context) {
    final g = widget.garden;
    if (g == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Guide')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final ids = g.data.birds.keys.toList();
    if (_sort == 'rarity') {
      ids.sort((a, b) => ((g.data.birds[a]?['rarity'] as num?) ?? 0)
          .compareTo((g.data.birds[b]?['rarity'] as num?) ?? 0));
    } else {
      // 地域別: 好む土地でまとめ、そのなかは名前順
      ids.sort((a, b) {
        final ba =
            ((g.data.birds[a]?['biome_pref'] as List?) ?? const []).join(',');
        final bb =
            ((g.data.birds[b]?['biome_pref'] as List?) ?? const []).join(',');
        final c = ba.compareTo(bb);
        if (c != 0) return c;
        final na = '${g.data.birds[a]?['english']}';
        final nb = '${g.data.birds[b]?['english']}';
        return na.compareTo(nb);
      });
    }

    final found = ids
        .where((b) => g.discovered.contains(b) || (g.observed[b] ?? 0) > 0)
        .length;

    return Scaffold(
      appBar: AppBar(title: Text('Guide  $found/${ids.length}')),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'region', label: Text('By region')),
              ButtonSegment(value: 'rarity', label: Text('By rarity')),
            ],
            selected: {_sort},
            onSelectionChanged: (s) => setState(() => _sort = s.first),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 32),
            itemCount: ids.length,
            itemBuilder: (_, i) => _Entry(g, ids[i]),
          ),
        ),
      ]),
    );
  }
}

/// 1種ぶんの折りたたみ。
class _Entry extends StatelessWidget {
  final Garden g;
  final String id;
  const _Entry(this.g, this.id);

  String _name(Map<String, dynamic> m, String key) =>
      (m[key]?['english'] as String?) ?? key;

  @override
  Widget build(BuildContext context) {
    final b = (g.data.birds[id] as Map?) ?? const {};
    final observed = (g.observed[id] ?? 0) > 0; // 近くで出会った
    // 近くで会えた鳥は、当然「来た鳥」でもある(app.py 図鑑タブと同じ判定)。
    final discovered = g.discovered.contains(id) || observed;
    final rarity = ((b['rarity'] as num?) ?? 0.5).toDouble();
    final stars = '★' * (1 + (rarity * 5).toInt());
    final days = g.birdDays[id] ?? 0;

    final icon = observed ? '🪶' : (discovered ? '🐦' : '❓');
    final title = discovered ? ((b['english'] as String?) ?? id) : '???';

    final likes = <String>[
      for (final p in ((b['eats_plants'] as List?) ?? const []))
        if (g.data.plants[p] != null)
          '${g.data.plants[p]?['icon'] ?? '🌱'} ${_name(g.data.plants, '$p')}',
      for (final i in ((b['eats_insects'] as List?) ?? const []))
        if (g.data.insects[i] != null) '🐛 ${_name(g.data.insects, '$i')}',
    ];
    final home = <String>[
      for (final x in ((b['biome_pref'] as List?) ?? const []))
        if (g.data.biomes[x] != null) '${g.data.biomes[x]?['name_en'] ?? x}',
    ];
    final fears = <String>[
      for (final f
          in ((g.data.predators[id]?['categories'] as List?) ?? const []))
        kPredatorLabels['$f'] ?? '$f',
    ];

    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 12),
        leading: Text(icon, style: const TextStyle(fontSize: 22)),
        title: Text(title,
            style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: discovered ? kInk : kSub)),
        subtitle: Text(
          discovered && days > 0 ? '$stars  ·  ${_badge(days)}' : stars,
          style: const TextStyle(fontSize: 12, color: kSub),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: !discovered
                // まだ来ていない鳥は、何も明かさない。
                ? const Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Not yet in your garden.',
                        style: TextStyle(color: kSub)),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // **絵が出るのは、近くで出会ってから。**
                      if (observed) ...[
                        Center(child: _picture()),
                        const SizedBox(height: 12),
                      ] else
                        const Padding(
                          padding: EdgeInsets.only(bottom: 12),
                          child: Text(
                              'Listen closely in the garden to see it up close.',
                              style: TextStyle(color: kSub, fontSize: 13)),
                        ),
                      _Row('Likes', likes),
                      _Row('Home', home),
                      _Row('Fears', fears),
                      // **なぜ来たか**の記録。あなたが組んだ関係が呼んだ証拠。
                      // 庭が痩せても、ここは消えない(原則2「罰しない」)。
                      ..._whyItCame(),
                      if (b['description_en'] != null) ...[
                        const SizedBox(height: 10),
                        Text(b['description_en'] as String,
                            style: const TextStyle(
                                fontSize: 14, color: kSub, height: 1.5)),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  /// この鳥について記録された「なぜ来たか」。古い順。
  ///
  /// 最初の1件には印を付ける — **その関係が、この鳥と出会うきっかけだった**という
  /// 意味。近くで出会った鳥にだけ付ける(`is_founding_record` と同じ判定)。
  List<Widget> _whyItCame() {
    final entries = core.entriesForBird(g.ecoLog, id);
    if (entries.isEmpty) return const [];
    final observedFirst = (g.observed[id] ?? 0) > 0 ? 'yes' : null;
    return [
      const SizedBox(height: 12),
      const Text('Why it came',
          style: TextStyle(
              fontSize: 12, fontWeight: FontWeight.w700, color: kSub)),
      const SizedBox(height: 4),
      for (final e in entries)
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            (core.isFoundingRecord(e, entries, observedFirst) ? '🌱 ' : '· ') +
                e.text,
            style: const TextStyle(fontSize: 13, color: kInk, height: 1.5),
          ),
        ),
    ];
  }

  Widget _picture() {
    final detail = g.detailSpriteFor(id);
    if (detail != null) {
      return Image.asset(detail, height: 140, filterQuality: FilterQuality.none);
    }
    final small = g.spriteFor(id);
    if (small != null) {
      return Image.asset(small, height: 96, filterQuality: FilterQuality.none);
    }
    return const Text('🐦', style: TextStyle(fontSize: 64));
  }

  /// 会った日数の節目。`badges.py` と同じ区切り。
  String _badge(int days) {
    if (days >= 100) return '🏅 $days days together';
    if (days >= 30) return '🌿 $days days together';
    if (days >= 10) return '🌱 $days days together';
    return '$days days';
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
