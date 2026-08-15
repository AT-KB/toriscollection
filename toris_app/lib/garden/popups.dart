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
  const AwayReport({
    required this.hoursAway,
    required this.arrivals,
    required this.departures,
    required this.lostPlants,
  });

  /// **何かあった時だけ出す。** 毎回は出さない(Python と同じ条件)。
  bool get worthShowing =>
      arrivals.isNotEmpty || departures.isNotEmpty || lostPlants.isNotEmpty;
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

String _name(Garden g, String birdId) =>
    (g.data.birds[birdId]?['english'] as String?) ?? birdId;

/// 🪶 出会えた。儀式のあと。
Future<void> showMetBirdPopup(
    BuildContext context, Garden g, List<MetBird> met) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('🪶 You met a bird'),
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
                              ? '✨ Nice to meet you! Newly added to your guide'
                              : "Met again. Another mark in your guide's log.",
                          style: const TextStyle(
                              fontSize: 13, height: 1.4, color: kSub),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
      actions: [
        FilledButton(
            onPressed: () => Navigator.pop(ctx), child: const Text('Close')),
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
    BuildContext context, Garden g, AwayReport r) {
  final h = r.hoursAway;
  final lead = h >= 48
      ? "It's been ${(h / 24).floor()} days. While you were away —"
      : (h >= 2 ? "It's been a little while. While you were away —" : null);

  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('🌿 Welcome back'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (lead != null) ...[
              Text(lead,
                  style: const TextStyle(fontSize: 13, color: kSub)),
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
                            ? '✨ Nice to meet you, ${_name(g, a.id)}! '
                                'Newly added to your guide'
                            : '${_name(g, a.id)} had come by',
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
                    '🕊 ${r.departures.take(5).join(', ')} set off on their way',
                    style: const TextStyle(fontSize: 13, color: kSub)),
              ),
            if (r.lostPlants.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('⛈ Lost  ${r.lostPlants.join(' · ')}',
                    style: const TextStyle(fontSize: 13, color: kSub)),
              ),
            // 来た鳥がいれば、ラジオへ誘う(会う→聴くの輪を閉じる)。
            if (r.arrivals.isNotEmpty) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFE8F1DE),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text(
                    "🎙 A new voice has joined the radio's cast. "
                    'Come have a listen.',
                    style: TextStyle(fontSize: 13, height: 1.4, color: kInk)),
              ),
            ],
          ],
        ),
      ),
      actions: [
        FilledButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('View the garden')),
      ],
    ),
  );
}
