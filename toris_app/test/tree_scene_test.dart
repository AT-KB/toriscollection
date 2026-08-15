/// 木の情景。**鳥が重ならないこと**を見る。
///
/// ## なぜ要るか(2026-08-15)
/// 枝の上の位置を鳥ごとの乱数で決めていたため、近い値を引くと2羽が重なり、
/// どちらも読めなくなっていた(実機で Blue Jay と Song Sparrow が重なった)。
/// 直しただけでは同じことが起きるので、機械で見る。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/tree_scene.dart';

List<PerchedBird> _birds(int n, String depth) => [
      for (var i = 0; i < n; i++)
        PerchedBird(id: 'b$i', english: 'Bird $i', depth: depth),
    ];

Future<List<double>> _lefts(WidgetTester tester, List<PerchedBird> birds) async {
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: SizedBox(width: 400, child: TreeScene(birds: birds))),
  ));
  await tester.pumpAndSettle();
  final out = <double>[];
  for (final b in birds) {
    final f = find.byKey(ValueKey('perch_${b.id}'));
    expect(f, findsOneWidget, reason: '${b.id} が描かれていない');
    out.add(tester.getTopLeft(f).dx);
  }
  out.sort();
  return out;
}

/// その枝での鳥の大きさ(tree_scene.dart と同じ式)。
double _size(String depth) {
  final spec = kTreeSpecs.firstWhere((t) => t.depth == depth);
  return 34.0 * (spec.opacity * 0.5 + 0.6);
}

void main() {
  // 奥の枝(b3)がいちばん細い。**滞在は最大4種**なので4羽まで見る。
  // 位置には乱数のゆらぎが入るので、**何度引いても**重ならないことを見る
  // (1回だけ通っても意味がない。実際、1回では通って監査で落ちた)。
  for (final depth in ['b3', 'b2', 'b1']) {
    for (final n in [2, 3, 4]) {
      testWidgets('$depth の枝に$n羽、何度置いても重ならない', (tester) async {
        final want = _size(depth);
        for (var trial = 0; trial < 25; trial++) {
          final birds = _birds(n, depth);
          final lefts = await _lefts(tester, birds);
          for (var i = 1; i < lefts.length; i++) {
            expect(lefts[i] - lefts[i - 1], greaterThanOrEqualTo(want - 0.01),
                reason: '$depth に$n羽($trial回目): '
                    '${i - 1}番目と$i番目が重なっている '
                    '(${lefts[i - 1]} と ${lefts[i]}、絵の幅 $want)');
          }
        }
      });
    }
  }

  testWidgets('奥・中・手前に分かれていれば、高さが違う', (tester) async {
    final birds = [
      const PerchedBird(id: 'far', english: 'Far', depth: 'b3'),
      const PerchedBird(id: 'mid', english: 'Mid', depth: 'b2'),
      const PerchedBird(id: 'near', english: 'Near', depth: 'b1'),
    ];
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: SizedBox(width: 400, child: TreeScene(birds: birds))),
    ));
    await tester.pumpAndSettle();
    final tops = {
      for (final b in birds)
        b.id: tester.getTopLeft(find.byKey(ValueKey('perch_${b.id}'))).dy
    };
    expect(tops['far']! < tops['mid']!, isTrue, reason: '奥ほど上にいるはず');
    expect(tops['mid']! < tops['near']!, isTrue, reason: '手前ほど下にいるはず');
  });

  testWidgets('誰も居なければ、木だけが立っている', (tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: SizedBox(width: 400, child: TreeScene(birds: []))),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(TreeScene), findsOneWidget);
  });
}
