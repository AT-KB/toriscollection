/// 環境音の設定が、閉じても残ること。
///
/// ## なぜ要るか(2026-08-18 の監査)
/// ラジオは **SharedPreferences を一度も使っていなかった**。環境音の入切も
/// 音量も、毎回作り直されるだけで、アプリを閉じるたびに「Wind だけ・0.55」に
/// 戻っていた。図鑑が白紙に戻っていたのと**同じ種類**の見落とし
/// (書いているつもりで、どこにも書いていない)。
///
/// Streamlit 版はセッションが短いので同じ挙動でも目立たなかったが、
/// 携帯のアプリは1日に何度も開く。開くたびに混ぜ直すのは「受動的である」から遠い。
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:toris_app/radio/radio_engine.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('何も保存していなければ、既定のまま(Wind だけ)', () async {
    final e = RadioEngine();
    await e.restorePrefs();
    expect(e.ambOn['wind'], isTrue);
    // ⚠️ 2026-09-22 に 0.55 から下げた。**保存済みの人は変わらない**
    // (下の試験)。効くのは新規と、まだ触っていない人だけ。
    expect(e.ambVol, closeTo(kAmbVolDefault, 1e-9));
    expect(kAmbVolDefault, closeTo(0.45, 1e-9));
  });

  test('鳥の音量は、既定 0.80 で、触れば次に開いた時も残る', () async {
    // ## なぜ要るか(CEO 実機 2026-09-22「鳥の声が全然聞こえない」)
    // 音量つまみは環境音にしかかかっておらず、鳥の音量はユーザーが触れる
    // 手段が無かった。つまみを足した以上、**環境音と同じように覚える**。
    final a = RadioEngine();
    await a.restorePrefs();
    expect(a.birdVol, closeTo(kBirdVolDefault, 1e-9));
    expect(kBirdVolDefault, closeTo(0.80, 1e-9),
        reason: 'つまみが端に寄っていると「もう上げられない」と見える。'
            '上にも下にも動かせる位置に置く');
    // 触らなくても現行(1.00)より大きい。CEO はつまみを探さなくてよい。
    expect(kBirdVolDefault * kBirdGainMax, greaterThan(1.0),
        reason: '既定で現行より小さくなると、直したことにならない');

    a.birdVol = 0.35;
    await a.savePrefs();

    final b = RadioEngine();
    await b.restorePrefs();
    expect(b.birdVol, closeTo(0.35, 1e-9),
        reason: '毎回また下げ直すことになる');
    // 環境音のつまみを巻き込んでいないこと。
    expect(b.ambVol, closeTo(kAmbVolDefault, 1e-9));
  });

  test('既定値を下げても、保存済みの人の環境音は変わらない', () async {
    final a = RadioEngine();
    await a.restorePrefs();
    a.ambVol = 0.55;   // 前の既定をそのまま使っていた人
    await a.savePrefs();

    final b = RadioEngine();
    await b.restorePrefs();
    expect(b.ambVol, closeTo(0.55, 1e-9),
        reason: '保存値より既定が優先されると、人が決めた音量を勝手に変える');
  });

  test('選んだ環境音と音量が、次に開いた時も残る', () async {
    final a = RadioEngine();
    await a.restorePrefs();
    a.ambOn['wind'] = false;
    a.ambOn['rain'] = true;
    a.ambOn['stream'] = true;
    a.ambVol = 0.2;
    await a.savePrefs();

    // 別の個体＝アプリを開き直したのと同じ
    final b = RadioEngine();
    await b.restorePrefs();
    expect(b.ambOn['rain'], isTrue);
    expect(b.ambOn['stream'], isTrue);
    expect(b.ambOn['wind'], isFalse,
        reason: '切ったものが復活すると、毎回また切ることになる');
    expect(b.ambVol, closeTo(0.2, 1e-9));
  });

  _observedTests();

  test('全部切った状態も、ちゃんと「全部切り」で残る', () async {
    final a = RadioEngine();
    await a.restorePrefs();
    for (final k in kAmbienceKeys) {
      a.ambOn[k] = false;
    }
    await a.savePrefs();

    final b = RadioEngine();
    await b.restorePrefs();
    expect(b.ambOn.values.any((v) => v), isFalse,
        reason: '空で保存したのを「未保存」と取り違えると、既定に戻ってしまう');
  });
}

// ── 会った鳥がラジオに乗るか ────────────────────────────────
//
// ## なぜ要るか(2026-08-25 実機で発覚)
// **ラジオは起動のたび、顔ぶれが空のままだった。** `RadioPage` は
// `initState` で1回だけ `load` するが、そのとき `main.dart` の `_garden` は
// まだ null で、渡ってくる `observed` は `const {}`。庭を読み終えて
// `observed` が入っても engine は読み直さず、**Listen が一度も出なかった**。
//
// ストア掲載文とLPは「会った鳥の声が聴けるラジオ」と言っている。
// 2026-08-21 の "A radio made only of birds you've met" と**同じ種類**の事故で、
// あのときは「会っていない鳥まで鳴る」、今回は「会った鳥が鳴かない」。
// **どちらも、掲載文と実装のあいだを見る人がいなかった。**
//
// ⚠️ ここで見ているのは **engine が新しい observed を受け取り直すか**だけ。
// 画面の配線(`didUpdateWidget`)そのものは、この試験では捕まえられない。
// **実機で Listen が出ることの確認は、まだ手作業**(主張台帳に「未整備」と記録)。

void _observedTests() {
  test('observed が後から入ってきたら、engine は読み直す', () async {
    final e = RadioEngine();
    // 起動直後と同じ状態 — 何も会っていない。
    expect(e.lastObservedForTest, isEmpty);

    // 庭を読み終えて、会った鳥が入ってくる。
    final changed = e.observedChangedForTest(const {'northern_cardinal': 1});
    expect(changed, isTrue,
        reason: '空から1羽に増えたのに「変わっていない」と判断している');

    // 同じものが来ても読み直さない(鳴っている最中に組み直さないため)。
    e.rememberObservedForTest(const {'northern_cardinal': 1});
    expect(e.observedChangedForTest(const {'northern_cardinal': 1}), isFalse);

    // 回数が増えたら読み直す(近さと群れの厚みが変わる)。
    expect(e.observedChangedForTest(const {'northern_cardinal': 2}), isTrue);
  });
}
