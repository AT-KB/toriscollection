/// 「今の庭」— **いま庭に来ている鳥を、絵で**出す一筆。
///
/// 現行の `daily.py`(今日の庭・Wordle 型の「今日の一羽」)に代わるもの。
/// 日付シードで全員共通の一羽を配るのはやめ、**あなたの庭にいま居る鳥**を出す
/// (CEO 2026-08-15「絵を出すようにして、今日ってか今の庭ね」)。
///
/// ⚠️ **ラジオの画面には置かないこと。** ラジオの顔ぶれは共起ネットワークからの
/// 抽選で、庭に居る鳥とは無関係。並べると「これから鳴く鳥」に読めて嘘になる
/// (CEO 2026-08-15「そこの Jay いたけど、ラジオにはいない」)。ここは庭の画面。
///
/// 交渉不能の原則:
///  - **1「受動的」** — 押させない。開けば見えているだけ。
///  - **5「かわいさ最優先」** — 名前の羅列ではなく、まず絵。
library;

import 'package:flutter/material.dart';

import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import 'garden_state.dart';

class NowInGarden extends StatelessWidget {
  final Garden? garden;

  /// 「庭を見に行く」— 押すと庭のタブへ。
  final VoidCallback? onOpenGarden;
  const NowInGarden({super.key, this.garden, this.onOpenGarden});

  @override
  Widget build(BuildContext context) {
    final g = garden;
    if (g == null) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F7EC),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Expanded(
              child: Text('In your garden now',
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.8,
                      color: kSub)),
            ),
            if (onOpenGarden != null)
              InkWell(
                onTap: onOpenGarden,
                borderRadius: BorderRadius.circular(8),
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  child: Icon(Icons.chevron_right_rounded, color: kSub),
                ),
              ),
          ]),
          const SizedBox(height: 10),
          if (g.visiting.isEmpty)
            // 誰も居ない日を、失敗のように書かない。植えれば来る、とだけ言う。
            const Text('No one yet. Plant something and they will come.',
                style: TextStyle(fontSize: 14, color: kSub))
          else
            Wrap(
              spacing: 18,
              runSpacing: 12,
              children: [for (final b in g.visiting) _Bird(g, b)],
            ),
        ],
      ),
    );
  }
}

/// 1羽ぶん。**絵が主役**で、名前はその下に小さく。
class _Bird extends StatelessWidget {
  final Garden g;
  final String id;
  const _Bird(this.g, this.id);

  @override
  Widget build(BuildContext context) {
    final name = (g.data.birds[id]?['english'] as String?) ?? id;
    // 近くで出会った鳥は、図鑑用の大きい絵を持っていればそちらを使う。
    final art = g.detailSpriteFor(id) ?? g.spriteFor(id);
    final met = (g.observed[id] ?? 0) > 0;

    return SizedBox(
      width: 84,
      child: Column(children: [
        SizedBox(
          height: 56,
          child: art != null
              ? Image.asset(art, height: 56, filterQuality: FilterQuality.none)
              // 絵が無い種は、その鳥の色をした小鳥のかたちで代える。
              : BirdMark.forBird(
                  g.data.birds[id] as Map<String, dynamic>?, size: 52),
        ),
        const SizedBox(height: 6),
        Text(name,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
                fontSize: 11,
                height: 1.25,
                color: met ? kInk : kSub)),
      ]),
    );
  }
}
