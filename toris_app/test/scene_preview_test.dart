/// 庭の情景を **PNG に描き出す**。見た目を、端末なしで見るための道具。
///
/// ## なぜ要るか(2026-08-16)
/// 見た目の間違い(Flutter のマスコットが木に止まる、鳥が重なる)は、
/// **絵を見ないと分からない**。実機は繋がっていないことも、ロックされている
/// ことも、画面が消えることもある。それで確認を飛ばして、何度も見逃した。
///
/// これを走らせると `build/preview/*.png` に情景が出る。
///
///     flutter test test/scene_preview_test.dart
///
/// 判定はしない(絵の良し悪しは人が見る)。描けずに落ちたらそれは不具合。
///
/// ⚠️ **植えたもののアイコン(絵文字)は □ になる。** テスト環境に絵文字の
/// フォントが無いため。実機では出る。絵文字の見え方だけは実機で見ること。
library;

import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/tree_scene.dart';

Future<void> _shoot(WidgetTester tester, String name, Widget child) async {
  final key = GlobalKey();
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      backgroundColor: const Color(0xFFF2F6EC),
      body: Center(
        child: RepaintBoundary(
          key: key,
          child: SizedBox(width: 380, child: child),
        ),
      ),
    ),
  ));
  await tester.pumpAndSettle();

  final boundary =
      key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
  // ⚠️ `toImage` は本物の非同期。テストの偽の時計の中で待つと止まったままになる
  // (実際に7分で打ち切られた)。`runAsync` の中で待つこと。
  await tester.runAsync(() async {
    final image = await boundary.toImage(pixelRatio: 3.0);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    final dir = Directory('build/preview')..createSync(recursive: true);
    File('${dir.path}/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
  });
}

List<PerchedBird> _birds() => const [
      PerchedBird(
          id: 'blue_jay',
          english: 'Blue Jay',
          depth: 'b3',
          data: {'color': '#5B84C4'}),
      PerchedBird(
          id: 'song_sparrow',
          english: 'Song Sparrow',
          depth: 'b3',
          data: {'color': '#9A7B58'}),
      PerchedBird(
          id: 'cardinal',
          english: 'Northern Cardinal',
          depth: 'b2',
          data: {'color': '#C1362F'}),
      PerchedBird(
          id: 'wren',
          english: 'Carolina Wren',
          depth: 'b1',
          data: {'color': '#A9743F'}),
    ];

void main() {
  testWidgets('裏庭を描き出す(空の庭 / 植生あり / 開放型 / かご型)', (tester) async {
    // 植えたものは `plants.json` の icon をそのまま置く。
    const plants = ['🟣', '🌸', '🌲', '🍇'];

    await _shoot(tester, '01_empty', const TreeScene(birds: []));

    await _shoot(tester, '02_planted',
        TreeScene(birds: _birds(), plants: plants));

    // 開放型 → リスが来て、リスがタカを呼ぶ
    await _shoot(
        tester,
        '03_open_feeder',
        TreeScene(
            birds: _birds(),
            plants: plants,
            feeder: 'feeder_open',
            hasSquirrel: true,
            hasRaptor: true));

    // かご型 → リスは届かず、タカも来ない
    await _shoot(
        tester,
        '04_caged_feeder',
        TreeScene(
            birds: _birds(), plants: plants, feeder: 'feeder_cage'));

    for (final n in ['01_empty', '02_planted', '03_open_feeder',
                     '04_caged_feeder']) {
      expect(File('build/preview/$n.png').existsSync(), isTrue,
          reason: '$n が描けていない');
    }
  });
}
