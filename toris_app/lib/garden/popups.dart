/// ポップアップ2つ。`app.py` の `_obs_dialog` / `_welcome_dialog` の移植。
///
/// **想定で作らず、あった仕組みをそのまま移した**(CEO 2026-08-16)。
/// 現行の作りで、写して意味のある決まりごと:
///
///  1. **一度に開くのは1つだけ。出会い(儀式直後)が「おかえり」より優先。**
///     (Python: `if ritual_flash: ... elif welcome_popup: ...`)
///  2. **「おかえり」は、留守のあいだに何かあった時だけ出す。** 毎回は出さない。
///  3. 「はじめまして」の判定は **図鑑への新規登録(discovered)かどうか**。
///     観察回数では見ない — 回数で見ると、既に図鑑に載っている鳥にまで
///     「はじめての観察!」が出てしまう(Python のコメントに残っている不一致)。
///  4. 来た鳥は **6件まで**、去った鳥は **5件まで**(名前は重複を除く)。
///  5. 留守が長いほど言い方が変わる: 48時間以上 → 「{n}日ぶり」、
///     2時間以上 → 「しばらくぶり」、それ未満 → 何も言わない。
///  6. 来た鳥がいれば、最後に**ラジオへ誘う**(会う→聴くの輪を閉じる)。
///
/// 文言は出荷済みの英語(`i18n.py` の TRANSLATIONS)をそのまま使う。
library;

import 'package:flutter/material.dart';
import 'package:toris_core/toris_core.dart' as core;

import '../i18n.dart';
import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import 'garden_state.dart';

/// 出会えた鳥1件。
class MetBird {
  final String id;

  /// **図鑑に新しく載った**か(観察回数ではない)。
  final bool first;
  const MetBird(this.id, this.first);
}

/// 留守のあいだの出来事。
class AwayReport {
  final double hoursAway;
  final List<MetBird> arrivals;

  /// 去った鳥の**表示名**(重複を除いた順)。
  final List<String> departures;

  /// 撹乱で倒れた植物の表示名。
  final List<String> lostPlants;

  /// 起きた撹乱の一文(`disturbance_story`)。倒れなかった回も語る。
  final List<String> disturbanceStories;

  /// 立ち寄りの要約(`summarize_events`)。無ければ空。
  final String summary;
  const AwayReport({
    required this.hoursAway,
    required this.arrivals,
    required this.departures,
    required this.lostPlants,
    this.disturbanceStories = const [],
    this.summary = '',
  });

  /// **何かあった時だけ出す。** 毎回は出さない(Python と同じ条件)。
  bool get worthShowing =>
      arrivals.isNotEmpty ||
      departures.isNotEmpty ||
      lostPlants.isNotEmpty ||
      disturbanceStories.isNotEmpty;
}

Widget _plate(Garden g, String birdId, double size) {
  final sprite = g.spriteFor(birdId);
  if (sprite != null) {
    return Image.asset(sprite,
        width: size, height: size, filterQuality: FilterQuality.none);
  }
  return BirdMark.forBird(
      (g.data.birds[birdId] as Map?)?.cast<String, dynamic>(), size: size);
}

/// 名前のある子が来たら「ルリツグミのピョンタ」(`Garden.labelFor`)。
String _name(Garden g, String birdId) => g.labelFor(birdId);

/// 🪶 出会えた。儀式のあと。
/// 一度きりの一言の札。お知らせの下に、静かに1つだけ出す。
Widget _hintCard(String text) => Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFE8F1DE),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text,
          style: const TextStyle(fontSize: 13, height: 1.45, color: kInk)),
    );

/// 名前をつける / 変える。[rename] があれば変える(空にすると外れる)。
/// 図鑑と、6回目に近くで会えたその場の両方から呼ぶ。
Future<bool> showNameDialog(BuildContext context, Garden g, String id,
    {String? rename}) async {
  final c = TextEditingController(text: rename ?? '');
  final name = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(t("It's used to you now")),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        Row(children: [
          _plate(g, id, 48),
          const SizedBox(width: 12),
          Expanded(
              child: Text(nameOf(g.data.birds[id], id),
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w700, color: kInk))),
        ]),
        const SizedBox(height: 12),
        Text(t('Give it a name. It will show up in your garden and guide.'),
            style: const TextStyle(fontSize: 14, height: 1.5, color: kSub)),
        const SizedBox(height: 8),
        TextField(
          controller: c,
          autofocus: true,
          maxLength: 12,
          decoration: InputDecoration(hintText: t('Name')),
        ),
      ]),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(ctx), child: Text(t('Later'))),
        FilledButton(
            onPressed: () => Navigator.pop(ctx, c.text), child: Text(t('Save'))),
      ],
    ),
  );
  if (name == null) return false;
  if (rename != null) {
    g.renameNickname(id, rename, name);
  } else {
    g.addNickname(id, name);
  }
  return true;
}

Future<void> showMetBirdPopup(
    BuildContext context, Garden g, List<MetBird> met, {String? hint}) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(t('🪶 You met a bird')),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final m in met)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _plate(g, m.id, 56),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_name(g, m.id),
                            style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: kInk)),
                        const SizedBox(height: 4),
                        Text(
                          m.first
                              ? t('✨ Nice to meet you! Newly added to your guide')
                              : t("Met again. Another mark in your guide's log."),
                          style: const TextStyle(
                              fontSize: 13, height: 1.4, color: kSub),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          if (hint != null) _hintCard(hint),
        ],
      ),
      actions: [
        FilledButton(
            onPressed: () => Navigator.pop(ctx), child: Text(t('Close'))),
      ],
    ),
  );
}

/// 🌿 おかえりなさい。留守のあいだの出来事。
///
/// **「Lost」「Left」はここにだけ出す**(CEO 2026-08-16「ガーデンの lost left
/// とかはポップにだけあればいい」)。庭の画面に常設すると、痩せたことを
/// ずっと突きつけることになる。
Future<void> showWelcomeBackPopup(
    BuildContext context, Garden g, AwayReport r, {String? hint}) {
  final h = r.hoursAway;
  final ja = L10n.lang.value == Lang.ja;
  final lead = h >= 48
      ? (ja
          ? awayLeadJa(h)
          : "It's been ${(h / 24).floor()} days. While you were away —")
      : (h >= 2
          ? (ja
              ? awayLeadJa(h)
              : "It's been a little while. While you were away —")
          : null);

  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(t('🌿 Welcome back')),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (lead != null) ...[
              Text(lead,
                  style: const TextStyle(fontSize: 13, color: kSub)),
              const SizedBox(height: 8),
            ],
            // 立ち寄りの要約(1種なら名前で、複数種なら件数と種数で)
            if (r.summary.isNotEmpty) ...[
              Text(
                  ja
                      ? awayHeadlineJa(r.summary)
                      : core.awayHeadline(r.summary),
                  style: const TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w600, color: kInk)),
              const SizedBox(height: 12),
            ],
            // 来た鳥は6件まで
            for (final a in r.arrivals.take(6))
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    _plate(g, a.id, 44),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        a.first
                            ? '✨ ${L10n.lang.value == Lang.ja ? "はじめまして、" : "Nice to meet you, "}'
                                '${_name(g, a.id)}'
                                '${L10n.lang.value == Lang.ja ? "。" : "! "}'
                                '${t('Newly added to your guide')}'
                            : (L10n.lang.value == Lang.ja
                                ? '${_name(g, a.id)} が来ていました'
                                : '${_name(g, a.id)} had come by'),
                        style: const TextStyle(
                            fontSize: 14, height: 1.4, color: kInk),
                      ),
                    ),
                  ],
                ),
              ),
            // 去った鳥は5件まで
            if (r.departures.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                    L10n.lang.value == Lang.ja
                        ? departuresJa(r.departures.take(5).toList())
                        : '🕊 ${r.departures.take(5).join(', ')} set off on their way',
                    style: const TextStyle(fontSize: 13, color: kSub)),
              ),
            // 撹乱は**一文で語る**。倒れなかった回も語る — 黙ると、
            // 嵐が来たこと自体が無かったことになる。
            for (final story in r.disturbanceStories)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(story,
                    style: const TextStyle(
                        fontSize: 13, height: 1.45, color: kSub)),
              ),
            // ⚠️ 前はここで、鳥が来るたびに「ラジオに新しい声が加わりました」と
            // 出していた。**ラジオで鳴くのは近くで会えた鳥だけ**なので、来ただけの
            // 鳥では嘘になる(2026-11-08 に気づいた)。代わりに、その時いちばん
            // 役に立つ一言を**一度だけ**出す(説明戦略。`garden_page` が選ぶ)。
            if (hint != null) ...[
              const SizedBox(height: 14),
              _hintCard(hint),
            ],
          ],
        ),
      ),
      actions: [
        FilledButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(t('View the garden'))),
      ],
    ),
  );
}
