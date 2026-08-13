// 目覚まし画面の最低限の確認。
// 実際に鳴るかは実機でしか分からないので、ここでは「画面が組み上がること」と
// 「さえずりだけを選ばせていること」を見る。
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/alarm.dart';
import 'package:toris_app/main.dart';

void main() {
  testWidgets('画面が立ち上がり、時刻とセットのボタンが出る(表示は英語)', (WidgetTester tester) async {
    await tester.pumpWidget(const TorisApp());
    await tester.pump();
    expect(find.text('Wake at'), findsOneWidget);
    expect(find.text('Set for this time'), findsOneWidget);
    expect(find.text('Turn off'), findsOneWidget);
  });

  testWidgets('選べる鳥は4種で、すべてさえずり', (WidgetTester tester) async {
    await tester.pumpWidget(const TorisApp());
    await tester.pump();
    for (final b in alarmBirds) {
      expect(find.text(b.name), findsOneWidget);
    }
  });

  test('鳥の並びはネイティブ側 BirdAlarmSounds.KEYS と同じ順序', () {
    // 順序がそのまま「夜明けのコーラスで加わる順」になるため、ずれてはいけない。
    expect(alarmBirds.map((b) => b.key).toList(), [
      'northern_cardinal',
      'american_robin',
      'song_sparrow',
      'carolina_wren',
    ]);
  });
}
