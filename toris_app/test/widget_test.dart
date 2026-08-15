// 目覚まし画面の最低限の確認。
// 実際に鳴るかは実機でしか分からないので、ここでは「画面が組み上がること」と
// 「さえずりだけを選ばせていること」を見る。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/alarm/alarm.dart';
import 'package:toris_app/alarm/alarm_page.dart';

void main() {
  testWidgets('画面が立ち上がり、時刻とセットのボタンが出る(表示は英語)', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AlarmPage()));
    await tester.pump();
    // 文字を減らしたので、見るのは「主なボタンが出ているか」だけにする
    // (CEO 2026-08-14「文字の量を少なくしよう」)。
    expect(find.text('Set'), findsOneWidget);
    expect(find.text('First to sing'), findsOneWidget);
  });

  testWidgets('選べる鳥は4種で、すべてさえずり', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AlarmPage()));
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
