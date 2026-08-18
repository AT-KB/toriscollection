// 目覚まし画面の最低限の確認。
// 実際に鳴るかは実機でしか分からないので、ここでは「画面が組み上がること」と
// 「さえずりだけを選ばせていること」を見る。
import 'dart:convert';
import 'dart:io';

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

  testWidgets('選べる鳥はネイティブに音がある種だけで、すべてさえずり', (WidgetTester tester) async {
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
      'eastern_bluebird',
    ]);
  });

  /// 選択肢と**実ファイル**がそろっていること。
  ///
  /// ## なぜ要るか(2026-08-18)
  /// `resFor` は知らない鍵を既定(Northern Cardinal)に落とす。つまり選択肢だけ
  /// 増やして音を入れ忘れると、**エラーも出ずに別の鳥が鳴く**。「選んだ鳥で
  /// 起きる」がこの機能の全部なので、静かに裏切られるのがいちばん悪い。
  ///
  /// ドット絵も見る(無い種は `BirdMark` の代役になり、鳥の顔が並ばない)。
  test('選べる鳥は、音とドット絵が実在する種だけ', () {
    for (final b in alarmBirds) {
      expect(File('android/app/src/main/res/raw/alarm_${b.key}.mp3').existsSync(),
          isTrue,
          reason: '${b.key} の目覚まし音が res/raw に無い。'
              '選ばせても Northern Cardinal が鳴いてしまう');
    }
    // 絵は**まだ描けていない種がある**。無い種は `BirdMark` の代役になる
    // (Flutter のマスコットではない)。ここでは「増やすときに気づける」
    // ようにするだけで、既にある種を落とさない。
    const noArtYet = {'song_sparrow'};
    for (final b in alarmBirds) {
      if (noArtYet.contains(b.key)) continue;
      expect(File('assets/sprites/${b.key}.png').existsSync(), isTrue,
          reason: '${b.key} のドット絵が無い。選択肢に顔が並ばない');
    }
  });

  /// 目覚ましに使う音は**商用に使えるものだけ**。
  ///
  /// 鳴き声36件のうち商用可は6件しかなく、残りは NC(非商用)や ND(改変不可)。
  /// 目覚まし音は res/raw に置くため**切り出し=改変**が入る。ND のものは
  /// 無料配布でも本来置けない。ここで固定して、増やすときに気づけるようにする。
  test('目覚まし音は license_class が commercial の録音だけ', () {
    final creds = jsonDecode(
        File('assets/birds/_credits.json').readAsStringSync()) as List;
    final cls = {
      for (final r in creds.cast<Map<String, dynamic>>())
        '${r['id']}': '${r['license_class']}',
    };
    // ⚠️ **既に出荷してしまっている1件**。Carolina Wren の録音は
    // CC BY-NC-ND で、非商用かつ改変不可。res/raw の音は切り出してあるため
    // ND にも触れる。CEO 判断待ち(差し替えるか、外すか)。
    // ここに足してよいのは「CEO が承知している既存の負債」だけで、
    // **新しく選択肢を増やすときの逃げ道にはしない。**
    const known = {'carolina_wren'};
    for (final b in alarmBirds) {
      if (known.contains(b.key)) continue;
      expect(cls[b.key], 'commercial',
          reason: '${b.key} は ${cls[b.key]}。目覚まし音は切り出して res/raw に'
              '置くので、NC/ND のままでは使えない');
    }
    expect(known.every((k) => cls[k] != 'commercial'), isTrue,
        reason: '差し替えが済んだら known から外すこと');
  });
}
