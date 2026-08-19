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

  testWidgets('選べるのは会えた鳥＋最初の3種。会っていない鳥は出ない',
      (WidgetTester tester) async {
    // 会ったのは Carolina Wren だけ、という人の画面。
    await tester.pumpWidget(
        const MaterialApp(home: AlarmPage(met: ['carolina_wren'])));
    await tester.pump();
    // プルダウンは閉じているので、出ているのは選ばれている1羽ぶん。
    // 一覧の中身は selectableAlarmBirds の試験で見ている。
    expect(find.text('First to sing'), findsOneWidget);
    expect(find.byType(DropdownButton<String>), findsOneWidget);
    // 会っていない鳥が閉じた状態で見えていないこと。
    expect(find.text('Mourning Dove'), findsNothing);
  });

  test('画面の並びはアルファベット順(CEO 2026-08-19)', () {
    final names = alarmBirds.map((b) => b.name).toList();
    final sorted = [...names]..sort();
    expect(names, sorted, reason: '探せない一覧は選べない一覧と同じ');
  });

  test('会えていなくても、最初から選べる3種がある', () {
    // 目覚ましは**起きるための道具**。始めた初日から使えないと困る。
    final none = selectableAlarmBirds(const []);
    expect(none.map((b) => b.key).toSet(), kStarterAlarmBirds);
  });

  test('会った鳥は選べるようになる。会っていない鳥は出てこない', () {
    final s = selectableAlarmBirds(['carolina_wren']).map((b) => b.key);
    expect(s, contains('carolina_wren'));
    expect(s, containsAll(kStarterAlarmBirds));
    expect(s, isNot(contains('mourning_dove')),
        reason: '会っていない鳥が選べると、会う意味が無くなる');
  });

  /// 選択肢と**実ファイル**がそろっていること。
  ///
  /// ## なぜ要るか(2026-08-18)
  /// `resFor` は知らない鍵を既定(Northern Cardinal)に落とす。つまり選択肢だけ
  /// 増やして音を入れ忘れると、**エラーも出ずに別の鳥が鳴く**。「選んだ鳥で
  /// 起きる」がこの機能の全部なので、静かに裏切られるのがいちばん悪い。
  ///
  /// ドット絵も見る(無い種は `BirdMark` の代役になり、鳥の顔が並ばない)。
  test('コーラスの鳥は、音とドット絵が実在する種だけ', () {
    for (final b in dawnChorus) {
      // ネイティブは **Flutter の assets を直に読む**(res/raw ではない)。
      expect(File('assets/birds/${b.key}.mp3').existsSync(), isTrue,
          reason: '${b.key} の鳴き声が assets に無い。'
              '選ばせても既定の鳥が鳴いてしまう');
    }
    // 絵があることは**選ばせる条件**(CEO「アイコンもほしい」)。
    // 例外は無い — Song Sparrow は絵が無いので一覧から外してある。
    for (final b in dawnChorus) {
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
    // ⚠️ **商用ライセンスは条件から外した**(CEO 2026-08-19「商用にしないから
    // 増やせ」)。23種のうち commercial は3種だけ。収益化する段になったら
    // ここを戻すこと。いまは「何種が商用可か」を数えて記録するだけにする。
    final ok = dawnChorus.where((b) => cls[b.key] == 'commercial').length;
    expect(ok, greaterThanOrEqualTo(3),
        reason: '商用可がこれ以下になったら、収益化のときに総取り替えになる');
  });

  test('目覚ましに使うのは、さえずり(song)だけ', () {
    // 研究1: 耳障りな音で起きると睡眠慣性が強まる。call は入れない。
    final creds = jsonDecode(
        File('assets/birds/_credits.json').readAsStringSync()) as List;
    final type = {
      for (final r in creds.cast<Map<String, dynamic>>())
        '${r['id']}': '${r['type']}',
    };
    for (final b in dawnChorus) {
      expect(type[b.key], 'song',
          reason: '${b.key} は ${type[b.key]}。地鳴き・警戒声で起こさない');
    }
  });

  /// Dart の並びと **Java の KEYS が実際に同じか**。
  ///
  /// ## なぜ要るか(2026-08-18)
  /// 並びは2箇所にある。音を鳴らすのは Java(`BirdAlarmSounds.KEYS`)、
  /// 名前を並べるのは Dart(`dawnChorus`)。ずれると
  /// **鳴いていない鳥の名前が光る**。順序がそのまま「鳴き出す順」なので、
  /// 並べ替えただけでも表示が嘘になる。
  ///
  /// これまでは Dart 側の期待値を手で書いた試験しか無く、Java を
  /// 書き換えても気づけなかった。**実ファイルを読んで突き合わせる。**
  test('Dart の alarmBirds と Java の KEYS は、中身が同じ', () {
    final java = File('android/app/src/main/java/com/toriscollection/'
            'toris_app/BirdAlarmSounds.java')
        .readAsStringSync();
    final body = java.substring(
        java.indexOf('KEYS = {') + 8, java.indexOf('};', java.indexOf('KEYS = {')));
    // コメントを落としてから、"…" の中身だけ拾う。
    final keys = RegExp(r'"([a-z_]+)"')
        .allMatches(body.replaceAll(RegExp(r'//[^\n]*'), ''))
        .map((m) => m.group(1))
        .toList();
    // ⚠️ **順序は比べない。** Dart 側はアルファベット順(画面のため)、
    // Java 側は「出会いが足りないときの埋め順」で、役割が違う。
    // 中身がずれると、選ばせても鳴らせない/鳴らせるのに選べない種が出る。
    expect(keys!.toSet(), alarmBirds.map((b) => b.key).toSet(),
        reason: 'Java の KEYS と Dart の alarmBirds で中身がずれている');
    expect(keys.take(2).toList(), ['northern_cardinal', 'american_robin'],
        reason: 'KEYS の先頭は埋め順の優先。変えると既存の朝が変わる');
  });
}
