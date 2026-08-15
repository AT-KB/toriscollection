/// はじめての案内。**進み方と、封じ方**を機械で確かめる。
///
/// 現行は「ブロックしない」作りだったので、ここは移植ではなく作り直し。
/// だからこそ、決めた通りに動くかを試験で押さえる。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/tutorial_overlay.dart';
import 'package:toris_core/toris_core.dart' as core;

void main() {
  group('段の進み方', () {
    test('植えたら、押さなくても次へ進む', () {
      // 「次へ」で進める段と、**実際にやらないと進まない段**がある。
      expect(core.resolveTutorialStep(1, hasPlanted: false), 1,
          reason: 'まだ植えていないので、その場に留まる');
      expect(core.resolveTutorialStep(1, hasPlanted: true), 2,
          reason: '1つ植えたら繰り上がる');
      // 他の段は繰り上げない
      expect(core.resolveTutorialStep(0, hasPlanted: true), 0);
      expect(core.resolveTutorialStep(2, hasPlanted: true), 2);
    });

    test('4段を踏み切ると終わる。それ以上は増えない', () {
      var s = 0;
      for (var i = 0; i < core.kTutorialSteps; i++) {
        expect(core.tutorialIsDone(s), isFalse, reason: '$s 段目でまだ終わり扱い');
        s = core.advanceTutorialStep(s);
      }
      expect(core.tutorialIsDone(s), isTrue);
      expect(core.advanceTutorialStep(s), core.kTutorialSteps,
          reason: '踏み切った後も増えない');
    });

    test('土地と植えるの段には「次へ」が無い(実際にやるまで進めない)', () {
      expect(core.tutorialStepContent(0).nextLabel, isNull);
      expect(core.tutorialStepContent(1).nextLabel, isNull);
      expect(core.tutorialStepContent(2).nextLabel, isNotNull);
      expect(core.tutorialStepContent(3).nextLabel, isNotNull);
    });

    test('虫が湧かなかったときは、嘘をつかない', () {
      final withInsects = core.tutorialStepContent(2, hasInsects: true);
      final without = core.tutorialStepContent(2, hasInsects: false);
      expect(withInsects.title, isNot(without.title));
      expect(without.body.toLowerCase(), contains('temperature'),
          reason: '気温のせいだと正直に言う');
    });

    test('文は短い(1段2行に収まる長さ)', () {
      for (var i = 0; i < core.kTutorialSteps; i++) {
        final c = core.tutorialStepContent(i);
        expect(c.title.length, lessThan(30), reason: '$i 段目の見出しが長い');
        expect(c.body.length, lessThan(90), reason: '$i 段目の本文が長い');
      }
    });
  });

  group('覆い', () {
    testWidgets('穴の外は押せない。穴の中は下まで指が届く', (tester) async {
      var outsideTapped = 0;
      var insideTapped = 0;
      final target = GlobalKey();

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Stack(children: [
            Column(children: [
              const SizedBox(height: 100),
              // 穴を開ける対象
              SizedBox(
                key: target,
                width: 200,
                height: 60,
                child: ElevatedButton(
                    onPressed: () => insideTapped++,
                    child: const Text('inside')),
              ),
              const SizedBox(height: 60),
              SizedBox(
                width: 200,
                height: 60,
                child: ElevatedButton(
                    onPressed: () => outsideTapped++,
                    child: const Text('outside')),
              ),
            ]),
            TutorialOverlay(
                targetKey: target, title: 'T', body: 'B'),
          ]),
        ),
      ));
      // 1度描いてから測る(GlobalKey の位置は描画後に決まる)
      await tester.pumpAndSettle();
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Stack(children: [
            Column(children: [
              const SizedBox(height: 100),
              SizedBox(
                key: target,
                width: 200,
                height: 60,
                child: ElevatedButton(
                    onPressed: () => insideTapped++,
                    child: const Text('inside')),
              ),
              const SizedBox(height: 60),
              SizedBox(
                width: 200,
                height: 60,
                child: ElevatedButton(
                    onPressed: () => outsideTapped++,
                    child: const Text('outside')),
              ),
            ]),
            TutorialOverlay(
                targetKey: target, title: 'T', body: 'B'),
          ]),
        ),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('outside'), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(outsideTapped, 0, reason: '穴の外は押せてはいけない');

      await tester.tap(find.text('inside'));
      await tester.pumpAndSettle();
      expect(insideTapped, 1, reason: '穴の中は下まで届くはず');
    });

    testWidgets('「次へ」が無い段は、ボタンを出さない', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: TutorialOverlay(title: 'Choose your land', body: 'B'),
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Choose your land'), findsOneWidget);
      expect(find.byType(FilledButton), findsNothing,
          reason: '実際に操作するまで進めない段');
    });

    testWidgets('急かす飾りを出さない(残り時間・進捗・段数)', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: TutorialOverlay(
              title: 'Plant something', body: 'Plants bring insects.'),
        ),
      ));
      await tester.pumpAndSettle();
      // 原則1「受動的である」。段の番号すら出さない。
      expect(find.byType(LinearProgressIndicator), findsNothing);
      expect(find.textContaining('1/4'), findsNothing);
      expect(find.textContaining('Step'), findsNothing);
    });
  });
}
