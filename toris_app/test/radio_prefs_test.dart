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
    expect(e.ambVol, closeTo(0.55, 1e-9));
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
