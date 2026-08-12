// スパイクの最低限の確認。
// 音そのものは実機でしか判断できないので、ここでは「画面が組み上がること」と
// 「休符の計算が現行版(radio.py の restDuration)と同じ形になっていること」だけを見る。
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_radio_spike/main.dart';

void main() {
  testWidgets('画面が立ち上がり、開始ボタンと環境音タイルが出る', (WidgetTester tester) async {
    await tester.pumpWidget(const SpikeApp());
    await tester.pump();

    expect(find.text('🎙 ラジオを始める'), findsOneWidget);
    expect(find.text('🍃 Wind'), findsOneWidget);
    expect(find.text('🌧 Rain'), findsOneWidget);
    // 3羽ぶんの名前が並ぶのは音源の読み込み後なので、ここでは見ない
    // (テスト環境には音のプラグインが無く、読み込みは失敗する)。
  });

  test('休符は羽数が増えるほど長くなり、上下限に収まる', () {
    final v = BirdVoice(kBirds.first, Random(1));
    // 3羽で回したときの休符が、現行版と同じ範囲に入ること
    for (var i = 0; i < 200; i++) {
      final r = v.restDurationForTest(3);
      expect(r, greaterThanOrEqualTo(kRestMinS * 0.7));
      expect(r, lessThanOrEqualTo(kRestMaxS * 1.3));
    }
    // 羽数が増えれば休符は伸びる(同時発声を一定に保つため)
    final rng = Random(7);
    double mean(int n) {
      final w = BirdVoice(kBirds.first, rng);
      var s = 0.0;
      for (var i = 0; i < 500; i++) {
        s += w.restDurationForTest(n);
      }
      return s / 500;
    }

    expect(mean(6), greaterThan(mean(2)));
  });
}
