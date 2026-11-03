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
import 'package:url_launcher/url_launcher.dart';
import 'package:toris_core/toris_core.dart' as core;

import '../i18n.dart';
import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import '../ui/lang_button.dart';
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
        appBar: AppBar(title: Text(t('Guide'))),
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
        final na = nameOf(g.data.birds[a], a);
        final nb = nameOf(g.data.birds[b], b);
        return na.compareTo(nb);
      });
    }

    final found = ids
        .where((b) => g.discovered.contains(b) || (g.observed[b] ?? 0) > 0)
        .length;

    return Scaffold(
      appBar: AppBar(
          title: Text('${t('Guide')}  $found/${ids.length}'),
          actions: const [LangButton()]),
      body: Column(children: [
        // ── 言語の切り替え ──
        // 設定画面が無く、図鑑は**文字を読む画面**なので、言語の切替はここが
        // いちばん自然に収まる。庭やラジオの上に出すと、静かな画面に操作子が
        // 増えて原則5「かわいさ優先」に障る(PJ管理部長 2026-10-19)。
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Row(children: [
            const Icon(Icons.translate_rounded, size: 18, color: kSub),
            const SizedBox(width: 8),
            SegmentedButton<Lang>(
              segments: const [
                ButtonSegment(value: Lang.en, label: Text('English')),
                ButtonSegment(value: Lang.ja, label: Text('日本語')),
              ],
              selected: {L10n.lang.value},
              showSelectedIcon: false,
              onSelectionChanged: (v) => L10n.set(v.first),
            ),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: SegmentedButton<String>(
            segments: [
              ButtonSegment(value: 'region', label: Text(t('By region'))),
              ButtonSegment(value: 'rarity', label: Text(t('By rarity'))),
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

  String _name(Map<String, dynamic> m, String key) => nameOf(m[key], key);

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
    final title = discovered ? nameOf(b, id) : '???';

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
      for (final x in prof.home) nameOf(g.data.biomes[x], x, enKey: 'name_en'),
    ];
    final fears = [for (final f in core.predatorLabels(id, g.data.predators)) t(f)];
    // 属レベル(同属の近縁種の記録から採ったもの)は、**黙って種の事実にしない**。
    // Python 側は同じ場所で「(from records of close relatives)」と断っていたのに、
    // 移植で落ちていた(2026-08-18 の監査で発覚)。原則4「生態に誠実」。
    // 文言は i18n.py の出荷済みの英語をそのまま使う。
    final fearsNote = core.predatorIsGenusLevel(id, g.data.predators)
        ? t('(from records of close relatives)')
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
                ? Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(4, 0, 4, 10),
                      child: Text(t('Not yet in your garden.'),
                          style: const TextStyle(color: kSub)),
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
                        _Row(t('Likes'), likes),
                        _Row(t('Home'), home),
                        _Row(t('Fears'), fears, note: fearsNote),
                        _OutLinks(b),
                        // 説明文は**種データに両方入っている**(`export_data.py` の
                        // FIELDS)。和文が欠けている種は英文に落とす。
                        if (b['description_en'] != null) ...[
                          const _Rule(),
                          Text(
                              (L10n.lang.value == Lang.ja
                                      ? (b['description'] ?? b['description_en'])
                                      : b['description_en'])
                                  as String,
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
          Text(nameOf(b, id),
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
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                  t('Listen closely in the garden to see it up close.'),
                  style: const TextStyle(
                      fontSize: 12, height: 1.45, color: kSub)),
            ),
        ],
      );

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
  ///
  /// ⚠️ **「1 days」と出ていた**(2026-10-20、ストア用スクショを撮って発覚)。
  /// 英語は1日だけ単数。日本語は助数詞なので単複の区別が無い。
  String _badge(int days) {
    final ja = L10n.lang.value == Lang.ja;
    final unit = ja ? '日' : (days == 1 ? 'day' : 'days');
    final together = ja ? 'いっしょに$days$unit' : '$days $unit together';
    if (days >= 100) return '🏅 $together';
    if (days >= 30) return '🌿 $together';
    if (days >= 10) return '🌱 $together';
    return ja ? '$days$unit' : '$days $unit';
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
          // ⚠️ 幅は**言語で変える**。62 は英語の LIKES / HOME / FEARS に
          // 合わせた値で、日本語の「好きな場所」「苦手なもの」は入らず
          // 値とくっついて出る(2026-10-20 に実機で発覚)。
          // 日本語は字間を詰めず、大文字化もしない(漢字かなには効かない)。
          width: L10n.lang.value == Lang.ja ? 84 : 62,
          child: Text(
              L10n.lang.value == Lang.ja ? label : label.toUpperCase(),
              style: TextStyle(
                  fontSize: L10n.lang.value == Lang.ja ? 11 : 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: L10n.lang.value == Lang.ja ? 0 : 1.0,
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

/// 実物を見に行くための2つの入口。
///
/// ## なぜ足したか(2026-08-19 CEO)
/// 「画像やウィキに飛ぶ奴、移行漏れてるよね図鑑の」。そのとおりで、
/// `app.py` の図鑑には最初からこの2つが並んでいたのに、Flutter に来ていなかった。
///
/// **なぜ監査で気づけなかったか。** 台帳が数えているのは *公開関数* で、
/// この2つは `app.py` の関数の**中に直接書かれた HTML**だった。関数ではないので
/// 台帳に載りようがない。同じ穴を塞ぐ規則を `migration_audit.py` に足した
/// (app.py の URL が、アプリ側かドロップ一覧のどちらかに必ずあること)。
///
/// 文言は `i18n.py` の出荷済みの英語をそのまま使う。
///
/// ⚠️ 画像検索の語だけは Python と変えてある。Python は **和名**＋学名で
/// 引いていたが、アプリの表示は全部英語なので、英名＋学名で引く。
/// 和名のまま引くと、英語で使っている人に日本語の検索結果が出る。
class _OutLinks extends StatelessWidget {
  final Map bird;
  const _OutLinks(this.bird);

  /// 外のブラウザで開く。
  ///
  /// ⚠️ `canLaunchUrl` の結果だけで諦めない。Android 11 以降は
  /// AndroidManifest の `<queries>` に VIEW/https を宣言しないと false が
  /// 返り、**押しても無言で何も起きない**(2026-08-19 に実機で発覚)。
  /// 宣言は入れたが、ここでも**まず開いてみる**ようにして、同じ抜け方を防ぐ。
  Future<void> _open(String url) async {
    final u = Uri.parse(url);
    try {
      final ok = await launchUrl(u, mode: LaunchMode.externalApplication);
      if (ok) return;
    } catch (_) {
      // 落ちたら下の道へ
    }
    if (await canLaunchUrl(u)) {
      await launchUrl(u);
    }
  }

  @override
  Widget build(BuildContext context) {
    final en = '${bird['english'] ?? ''}'.trim();
    final sci = '${bird['scientific'] ?? ''}'.trim();
    if (en.isEmpty && sci.isEmpty) return const SizedBox.shrink();
    final photoQ = Uri.encodeComponent('$en $sci'.trim());
    final wikiQ = Uri.encodeComponent(sci.isNotEmpty ? sci : en);
    // 日本語の人には日本語版を和名で開く。和名が無ければ英語版のまま。
    final jaName = '${bird['name'] ?? ''}'.trim();
    final jaWiki = L10n.lang.value == Lang.ja && jaName.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Wrap(spacing: 8, runSpacing: 8, children: [
        _Chip(t('🖼️ See a real photo'),
            () => _open('https://www.google.com/search?tbm=isch&q=$photoQ')),
        jaWiki
            ? _Chip(
                t('📖 Wikipedia (JA)'),
                () => _open('https://ja.wikipedia.org/wiki/Special:Search'
                    '?search=${Uri.encodeComponent(jaName)}'))
            : _Chip(
                t('📖 Wikipedia (EN)'),
                () => _open('https://en.wikipedia.org/wiki/Special:Search'
                    '?search=$wikiQ')),
      ]),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _Chip(this.label, this.onTap);

  @override
  Widget build(BuildContext context) => InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: const Color(0xFFF0F4EC),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(label,
              style: const TextStyle(fontSize: 13, color: Color(0xFF3A5A3A))),
        ),
      );
}
