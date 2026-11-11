/// 鳥が来るペース(`lib/src/pacing.dart`)。Python には無い、Flutter 版だけの調整。
///
/// ## なぜ足したか(CEO 2026-11-07)
/// 「鳥の来る頻度をちょっと落として」「ログインし続けると鳥が来やすくなる」
/// 「警戒心が下がると名前をつけられる」。
/// 前の `estimateTickCount` は経過時間に比例せず、5分おきに開くと
/// 1日放っておくより何倍も早く図鑑が埋まった。
library;

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

void main() {
  test('コマは実時間に比例する(3時間で1コマ、上限6コマ)', () {
    expect(pacedTickCount(0), 0);
    expect(pacedTickCount(5 / 60), 0, reason: '5分おきに開いても進まない');
    expect(pacedTickCount(2.9), 0);
    expect(pacedTickCount(3.0), 1);
    expect(pacedTickCount(9.5), 3);
    expect(pacedTickCount(18), 6);
    expect(pacedTickCount(72), 6, reason: '上限');
  });

  test('こまめに開いても、1日放っておいても、進むコマ数は同じ', () {
    // 前は 5分おきに開くと1時間で12コマ、1日放っておくと5コマだった。
    var ticks = 0;
    var last = DateTime(2026, 11, 7, 6);
    for (var m = 5; m <= 12 * 60; m += 5) {
      final now = DateTime(2026, 11, 7, 6).add(Duration(minutes: m));
      final n = pacedTickCount(now.difference(last).inSeconds / 3600);
      if (n > 0) {
        last = pacedLastSeen(last, now, n);
        ticks += n;
      }
    }
    expect(ticks, pacedTickCount(12), reason: '12時間ぶんは、開き方によらず4コマ');
  });

  test('端数は持ち越す(1時間おきに開く人の庭も止まらない)', () {
    final t0 = DateTime(2026, 11, 7, 9);
    final now = t0.add(const Duration(hours: 4));
    expect(pacedTickCount(4), 1);
    // 1コマ(3時間)ぶんだけ進め、残りの1時間は次へ持ち越す
    expect(pacedLastSeen(t0, now, 1), t0.add(const Duration(hours: 3)));
  });

  test('上限を超えて離れていたぶんは持ち越さない', () {
    final t0 = DateTime(2026, 11, 1, 9);
    final now = DateTime(2026, 11, 7, 9);
    expect(pacedLastSeen(t0, now, 6), now);
  });

  test('庭のなじみは、開いた日数の合計で上がる(連続でなくてよい)', () {
    expect(gardenFamiliarityLevel(0), 0);
    expect(gardenFamiliarityLevel(3), 1);
    expect(gardenFamiliarityLevel(7), 2);
    expect(gardenFamiliarityLevel(14), 3);
    expect(gardenFamiliarityLevel(30), 4);
    expect(gardenFamiliarityLevel(400), 4);
    expect(daysToNextFamiliarity(5), 2);
    expect(daysToNextFamiliarity(30), isNull);
  });

  test('珍しい鳥ほど来にくく、なじみの効き目は珍しい鳥ほど大きい', () {
    const common = {'rarity': 0.2, 'wariness': 0.3};
    const rare = {'rarity': 0.8, 'wariness': 0.3};
    final c0 = arrivalScale(common, openDays: 0, meets: 0);
    final r0 = arrivalScale(rare, openDays: 0, meets: 0);
    expect(r0, lessThan(c0));
    final c4 = arrivalScale(common, openDays: 30, meets: 0);
    final r4 = arrivalScale(rare, openDays: 30, meets: 0);
    expect(r4 / r0, greaterThan(c4 / c0), reason: '珍しい鳥のほうが、なじみで伸びる');
    expect(c0, closeTo(0.5 * (1 - 0.7 * 0.2), 1e-9));
  });

  test('慣れると来やすくなり、警戒心の強い鳥ほど効き目が大きい', () {
    const shy = {'rarity': 0.5, 'wariness': 0.9};
    const bold = {'rarity': 0.5, 'wariness': 0.1};
    double gain(Map b) =>
        arrivalScale(b, openDays: 0, meets: kTameMeets) /
        arrivalScale(b, openDays: 0, meets: 0);
    expect(gain(shy), greaterThan(gain(bold)));
    expect(gain(shy), closeTo(1 + 0.5 * 0.9, 1e-9));
  });

  test('名前の枠は、慣れに応じて3つまで開く', () {
    expect(nicknameSlots(5), 0);
    expect(nicknameSlots(6), 1);
    expect(nicknameSlots(12), 2);
    expect(nicknameSlots(18), 3);
    expect(nicknameSlots(99), 3, reason: '1種につき3羽まで');
    expect(meetsToNextSlot(4), 2);
    expect(meetsToNextSlot(7), 5);
    expect(meetsToNextSlot(18), isNull);
  });

  test('名前をつけられるのは、慣れきってから', () {
    expect(canNickname(kNicknameMeets - 1), isFalse);
    expect(canNickname(kNicknameMeets), isTrue);
    expect(tameness(0), 0);
    expect(tameness(3), 0.5);
    expect(tameness(99), 1);
  });

  test('係数を渡さなければ、エンジンは Python と同じ(既定の引数)', () {
    // runTurn / evolveWhileAway の arrivalScaleFn と tickCountFn は省略可能。
    // 省略時に estimateTickCount を使うことは logic_test の差分テストが守る。
    expect(estimateTickCount(10 / 60), 1);
  });
}
