/// 図鑑の大きい絵(`Garden.detailSpriteFor`)。Python の
/// `detail_sprites.detail_image_path` / `has_detail_image` に当たる(2026-11-10)。
///
/// 同梱している `*_detail.png` が全部実在の種のもので、その種では絵の道を返し、
/// 絵の無い種では null を返す(図鑑はアイコンで代わりに描く)ことを見る。
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/garden_state.dart';

void main() {
  test('detailSpriteFor: 絵のある種は道を、無い種は null を返す', () {
    final files = Directory('assets/sprites')
        .listSync()
        .map((f) => f.uri.pathSegments.last)
        .where((n) => n.endsWith('_detail.png'))
        .toList();
    expect(files, isNotEmpty);
    final ids = {for (final f in files) f.substring(0, f.length - '_detail.png'.length)};
    final birds = (jsonDecode(File('assets/data/birds.json').readAsStringSync())
            as Map)
        .keys
        .map((e) => '$e')
        .toSet();
    expect(birds.containsAll(ids), isTrue,
        reason: '種データに無い鳥の詳細画がある: ${ids.difference(birds)}');

    Garden.detailIds = ids;
    final g = Garden(GardenData(
        {for (final b in birds) b: {}}, const {}, const {}, const {}, const {}, const {}));
    for (final id in ids) {
      final p = g.detailSpriteFor(id);
      expect(p, 'assets/sprites/${id}_detail.png');
      expect(File(p!).existsSync(), isTrue);
    }
    final without = birds.difference(ids);
    expect(without, isNotEmpty);
    for (final id in without) {
      expect(g.detailSpriteFor(id), isNull, reason: '$id には詳細画が無い');
    }
  });
}
