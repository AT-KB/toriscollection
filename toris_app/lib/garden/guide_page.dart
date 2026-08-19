/// 図鑑。現行(Streamlit)の「📖 図鑑」に当たる。
///
/// **全37種が折りたたみ(プルダウン)で並ぶ。** 開くと図鑑の1ページが出る。
/// 見出しの印は3段階で、儀式を経て近くで会うまで正体は分からない:
///   ❓ まだ来ていない  → 名前も「???」、中身も明かさない
///   🐦 来訪済み        → 名前と中身が出る。図版は**小さなアイコン**
///   🪶 近くで出会った  → 図版が**詳細画に入れ替わる**
///
/// 会う前を白紙にはしない(CEO 2026-08-16「近くで会っていない鳥はアイコンを
/// 表示、それを近くで会ったらディテールに入れ替えるイメージ」)。
/// **会うと絵が育つ**、が伝わればよい。
///
/// 並びは「地域別 / レア度順」の2通り(現行の segmented_control と同じ)。
/// 庭が痩せても、ここの記録は減らない(交渉不能の原則2「罰しない」)。
library;

import 'package:flutter/material.dart';
import 'package:toris_core/toris_core.dart' as core;

import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import 'garden_state.dart';

/// 図鑑の版面の色。紙・図版の枠・罫線。
const Color kPage = Color(0xFFFBFAF3);
const Color kPlate = Color(0xFFF1F4E8);
const Color kRule = Color(0xFFE1E6D4);

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

    // **表を自分で書かない。** `toris_core` の移植をそのまま使う。
    // 以前は Dart 側に7分類を手で書いていて、実データが使う
    // crow/falcon/fox/rodent/weasel が抜け、図鑑に生のキーが出ていた。
    final prof = core.buildBirdProfile(
      birdId: id,
      bird: b.cast<String, dynamic>(),
      plants: g.data.plants,
      insects: g.data.insects,
      biomes: g.data.biomes,
      predatorsData: g.data.predators,
    );
    final likes = <String>[
      for (final l in prof.likes)
        if (l.kind == 'plant')
          '${g.data.plants[l.id]?['icon'] ?? '🌱'} ${_name(g.data.plants, l.id)}'
        else
          '🐛 ${_name(g.data.insects, l.id)}',
    ];
    final home = <String>[
      for (final x in prof.home) '${g.data.biomes[x]?['name_en'] ?? x}',
    ];
    final fears = core.predatorLabels(id, g.data.predators);
    // 属レベル(同属の近縁種の記録から採ったもの)は、**黙って種の事実にしない**。
    // Python 側は同じ場所で「(from records of close relatives)」と断っていたのに、
    // 移植で落ちていた(2026-08-18 の監査で発覚)。原則4「生態に誠実」。
    // 文言は i18n.py の出荷済みの英語をそのまま使う。
    final fearsNote = core.predatorIsGenusLevel(id, g.data.predators)
        ? '(from records of close relatives)'
        : null;

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
            padding: const EdgeInsets.fromLTRB(12, 0, 12, 14),
            child: !discovered
                // まだ来ていない鳥は、何も明かさない。
                ? const Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: EdgeInsets.fromLTRB(4, 0, 4, 10),
                      child: Text('Not yet in your garden.',
                          style: TextStyle(color: kSub)),
                    ),
                  )
                // ── 図鑑の1ページ ──
                : Container(
                    decoration: BoxDecoration(
                      color: kPage,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: kRule),
                    ),
                    padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // 見出し: 図版 + 英名 + 学名。図鑑の版面らしく左に絵。
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _plate(observed),
                            const SizedBox(width: 14),
                            Expanded(child: _heading(b, stars, days, observed)),
                          ],
                        ),
                        const _Rule(),
                        _Row('Likes', likes),
                        _Row('Home', home),
                        _Row('Fears', fears, note: fearsNote),
                        // **なぜ来たか**の記録。あなたが組んだ関係が呼んだ証拠。
                        // 庭が痩せても、ここは消えない(原則2「罰しない」)。
                        ..._whyItCame(),
                        if (b['description_en'] != null) ...[
                          const _Rule(),
                          Text(b['description_en'] as String,
                              style: const TextStyle(
                                  fontSize: 14, color: kInk, height: 1.7)),
                        ],
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  /// 見出し。英名 → 学名(斜体)→ レア度と会った日数。
  Widget _heading(Map b, String stars, int days, bool observed) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text((b['english'] as String?) ?? id,
              style: const TextStyle(
                  fontSize: 19,
                  height: 1.2,
                  fontWeight: FontWeight.w700,
                  color: kInk)),
          if (b['scientific'] != null)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(b['scientific'] as String,
                  style: const TextStyle(
                      fontSize: 13,
                      fontStyle: FontStyle.italic,
                      color: kSub)),
            ),
          const SizedBox(height: 8),
          Text(days > 0 ? '$stars   ${_badge(days)}' : stars,
              style: const TextStyle(fontSize: 12, color: kSub)),
          if (!observed)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Listen closely in the garden to see it up close.',
                  style: TextStyle(fontSize: 12, height: 1.45, color: kSub)),
            ),
        ],
      );

  /// この鳥について記録された「なぜ来たか」。古い順。
  ///
  /// 最初の1件には印を付ける — **その関係が、この鳥と出会うきっかけだった**という
  /// 意味。近くで出会った鳥にだけ付ける(`is_founding_record` と同じ判定)。
  List<Widget> _whyItCame() {
    final entries = core.entriesForBird(g.ecoLog, id);
    if (entries.isEmpty) return const [];
    final observedFirst = (g.observed[id] ?? 0) > 0 ? 'yes' : null;
    return [
      const _Rule(),
      const Text('WHY IT CAME',
          style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.0,
              color: kSub)),
      const SizedBox(height: 6),
      for (final e in entries)
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            (core.isFoundingRecord(e, entries, observedFirst) ? '🌱 ' : '·  ') +
                e.text,
            style: const TextStyle(fontSize: 13, color: kInk, height: 1.6),
          ),
        ),
    ];
  }

  /// 図版。**近くで会う前はアイコン、会ったら詳細画に入れ替わる。**
  ///
  /// 会う前を白紙にする必要はない(CEO 2026-08-16)。会うと絵が育つ、が
  /// 伝わればよい。詳細画が無い種は、会ってもアイコンが少し大きくなるだけ。
  Widget _plate(bool observed) {
    const box = 112.0;
    final detail = g.detailSpriteFor(id);
    final small = g.spriteFor(id);

    Widget art;
    if (observed && detail != null) {
      art = Image.asset(detail,
          height: box - 14, filterQuality: FilterQuality.none);
    } else if (small != null) {
      art = Image.asset(small,
          height: observed ? box - 30 : 54, filterQuality: FilterQuality.none);
    } else {
      art = BirdMark.forBird((g.data.birds[id] as Map?)?.cast<String, dynamic>(),
          size: observed ? 74 : 50);
    }

    return Container(
      width: box,
      height: box,
      decoration: BoxDecoration(
        color: kPlate,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: kRule),
      ),
      alignment: Alignment.center,
      // 会った瞬間に、静かに入れ替わる。
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: SizedBox(key: ValueKey(observed), child: art),
      ),
    );
  }

  /// 会った日数の節目。`badges.py` と同じ区切り。
  String _badge(int days) {
    if (days >= 100) return '🏅 $days days together';
    if (days >= 30) return '🌿 $days days together';
    if (days >= 10) return '🌱 $days days together';
    return '$days days';
  }
}

/// 項目のあいだの罫線。図鑑らしい区切り。
class _Rule extends StatelessWidget {
  const _Rule();
  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 11),
        child: Divider(height: 1, thickness: 1, color: kRule),
      );
}

class _Row extends StatelessWidget {
  final String label;
  final List<String> items;

  /// 値のあとに小さく添える但し書き。無ければ null。
  final String? note;
  const _Row(this.label, this.items, {this.note});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          width: 62,
          child: Text(label.toUpperCase(),
              style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.0,
                  height: 2.1,
                  color: kSub)),
        ),
        Expanded(
          child: Text.rich(
            TextSpan(children: [
              TextSpan(text: items.join('   ·   ')),
              if (note != null)
                TextSpan(
                  text: '  $note',
                  style: const TextStyle(fontSize: 11, color: kSub),
                ),
            ]),
            style: const TextStyle(fontSize: 14, color: kInk, height: 1.6),
          ),
        ),
      ]),
    );
  }
}
