/// ポップアップ2つ。`app.py` の `_obs_dialog` / `_welcome_dialog` の決まりごとを
/// 機械で確かめる。
///
/// 実機では「留守に何かあった時」しか出ないので、目で見て確かめるのが難しい。
/// **出る条件と中身は、ここで確かめる。**
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/garden_state.dart';
import 'package:toris_app/garden/popups.dart';

GardenData _data() => const GardenData(
      {
        'blue_jay': {'english': 'Blue Jay'},
        'a': {'english': 'Aaa'},
        'b': {'english': 'Bbb'},
        'c': {'english': 'Ccc'},
        'd': {'english': 'Ddd'},
        'e': {'english': 'Eee'},
        'f': {'english': 'Fff'},
        'g': {'english': 'Ggg'},
      },
      {}, {}, {'kyoto': {'name_en': 'Kyoto', 'max_plants': 4}}, {}, {},
    );

Future<void> _openWelcome(WidgetTester tester, AwayReport r) async {
  final g = Garden(_data());
  await tester.pumpWidget(MaterialApp(
    home: Builder(
      builder: (ctx) => ElevatedButton(
        onPressed: () => showWelcomeBackPopup(ctx, g, r),
        child: const Text('open'),
      ),
    ),
  ));
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
}

void main() {
  group('おかえりなさい', () {
    test('留守に何も起きていなければ、出さない', () {
      const empty = AwayReport(
          hoursAway: 100, arrivals: [], departures: [], lostPlants: []);
      expect(empty.worthShowing, isFalse, reason: '毎回は出さない');

      const withArrival = AwayReport(
          hoursAway: 0.1,
          arrivals: [MetBird('blue_jay', false)],
          departures: [],
          lostPlants: []);
      expect(withArrival.worthShowing, isTrue);

      const withDeparture = AwayReport(
          hoursAway: 0.1, arrivals: [], departures: ['Aaa'], lostPlants: []);
      expect(withDeparture.worthShowing, isTrue);

      const withLoss = AwayReport(
          hoursAway: 0.1, arrivals: [], departures: [], lostPlants: ['Sakura']);
      expect(withLoss.worthShowing, isTrue);
    });

    testWidgets('留守の長さで言い方が変わる(2時間 / 48時間の境目)', (tester) async {
      // 2時間未満は何も言わない
      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 1.9,
              arrivals: [MetBird('blue_jay', false)],
              departures: [],
              lostPlants: []));
      expect(find.textContaining('While you were away'), findsNothing);

      await tester.tap(find.text('View the garden'));
      await tester.pumpAndSettle();

      // 2時間以上
      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 2.0,
              arrivals: [MetBird('blue_jay', false)],
              departures: [],
              lostPlants: []));
      expect(find.text("It's been a little while. While you were away —"),
          findsOneWidget);

      await tester.tap(find.text('View the garden'));
      await tester.pumpAndSettle();

      // 48時間以上は「◯日ぶり」。50時間 → 2日
      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 50,
              arrivals: [MetBird('blue_jay', false)],
              departures: [],
              lostPlants: []));
      expect(find.text("It's been 2 days. While you were away —"),
          findsOneWidget);
    });

    testWidgets('来た鳥は6件まで、去った鳥は5件まで', (tester) async {
      await _openWelcome(
          tester,
          const AwayReport(
            hoursAway: 10,
            arrivals: [
              MetBird('a', false), MetBird('b', false), MetBird('c', false),
              MetBird('d', false), MetBird('e', false), MetBird('f', false),
              MetBird('g', false), // 7件目は出さない
            ],
            departures: ['Aaa', 'Bbb', 'Ccc', 'Ddd', 'Eee', 'Fff'],
            lostPlants: [],
          ));
      expect(find.textContaining('Fff had come by'), findsOneWidget);
      expect(find.textContaining('Ggg had come by'), findsNothing,
          reason: '7件目まで出ている');
      // 去った鳥は5件で切る
      expect(find.textContaining('Aaa, Bbb, Ccc, Ddd, Eee set off'),
          findsOneWidget);
    });

    testWidgets('はじめての鳥と、また来た鳥で文が変わる', (tester) async {
      await _openWelcome(
          tester,
          const AwayReport(
            hoursAway: 10,
            arrivals: [MetBird('a', true), MetBird('b', false)],
            departures: [],
            lostPlants: [],
          ));
      expect(
          find.textContaining(
              '✨ Nice to meet you, Aaa! Newly added to your guide'),
          findsOneWidget);
      expect(find.textContaining('Bbb had come by'), findsOneWidget);
    });

    testWidgets('来た鳥がいるときだけ、ラジオへ誘う', (tester) async {
      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 10,
              arrivals: [],
              departures: ['Aaa'],
              lostPlants: []));
      expect(find.textContaining("joined the radio's cast"), findsNothing);

      await tester.tap(find.text('View the garden'));
      await tester.pumpAndSettle();

      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 10,
              arrivals: [MetBird('a', false)],
              departures: [],
              lostPlants: []));
      expect(find.textContaining("joined the radio's cast"), findsOneWidget);
    });

    testWidgets('倒れた植物は、ここにだけ出る', (tester) async {
      await _openWelcome(
          tester,
          const AwayReport(
              hoursAway: 10,
              arrivals: [],
              departures: [],
              lostPlants: ['Sakura', 'Pine']));
      expect(find.text('⛈ Lost  Sakura · Pine'), findsOneWidget);
    });
  });

  group('鳥に出会えた', () {
    testWidgets('はじめては図鑑への登録、二度目からは観察の記録', (tester) async {
      final g = Garden(_data());
      await tester.pumpWidget(MaterialApp(
        home: Builder(
          builder: (ctx) => ElevatedButton(
            onPressed: () => showMetBirdPopup(ctx, g, const [
              MetBird('a', true),
              MetBird('b', false),
            ]),
            child: const Text('open'),
          ),
        ),
      ));
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();

      expect(find.text('🪶 You met a bird'), findsOneWidget);
      expect(find.text('Aaa'), findsOneWidget);
      expect(find.text('✨ Nice to meet you! Newly added to your guide'),
          findsOneWidget);
      expect(find.text("Met again. Another mark in your guide's log."),
          findsOneWidget);
      expect(find.text('Close'), findsOneWidget);
    });
  });

  group('儀式の歯止め', () {
    test('同じ顔ぶれの二度目は記録されない。顔ぶれが変わればまた記録される', () {
      final g = Garden(_data());
      g.visiting.addAll(['a', 'b']);
      expect(g.ritualCounts, isTrue, reason: '一度目は記録される');

      g.ritualDoneFor = {'a', 'b'};
      expect(g.ritualCounts, isFalse, reason: '同じ顔ぶれの二度目は記録しない');

      // 1羽入れ替わればまた記録される
      g.visiting
        ..clear()
        ..addAll(['a', 'c']);
      expect(g.ritualCounts, isTrue, reason: '顔ぶれが変われば会いに行ける');

      // 増えた場合も
      g.ritualDoneFor = {'a'};
      g.visiting
        ..clear()
        ..addAll(['a', 'b']);
      expect(g.ritualCounts, isTrue);
    });
  });
}
