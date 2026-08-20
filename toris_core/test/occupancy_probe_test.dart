/// **アプリ自身のエンジンで**、庭に鳥が居る割合を測る。
///
/// ## なぜ書いたか(2026-08-20)
/// CEO「なんでこんな鳥が誰も来ないんだろう」。
/// Python 側を模した計算では「開けたとき誰も居ない確率は10%」だったのに、
/// 実機はほぼ空だった。**模型とアプリのどちらかが間違っている。**
/// 推測で片付けず、`toris_core` の `evolveWhileAway` を実データで回す。
///
/// これは合否を決める試験ではなく**測るための試験**。数字を出して読む。
library;

import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

Map<String, dynamic> _load(String name) => (jsonDecode(
        File('test/fixtures/$name.json').readAsStringSync()) as Map)
    .cast<String, dynamic>();

void main() {
  test('実機と同じ庭で、居る/居ないの割合を測る', () {
    final birds = _load('birds');
    final plants = _load('plants');
    final insects = _load('insects');
    final biomes = _load('biomes');
    final season = jsonDecode(
        File('test/fixtures/season_offset.json').readAsStringSync());

    // Pixel 6a の庭そのもの。
    const planted = ['beautyberry', 'buttonbush', 'dogwood', 'loblolly'];
    const biome = 'charlotte';

    for (final feeders in [
      <String>['feeder_open'],
      <String>['feeder_cage'],
      <String>[],
    ]) {
      var empty = 0, total = 0, sumRes = 0, arrivals = 0;
      // 200回ぶん「閉じて、しばらくして開く」を繰り返す。
      for (var seed = 0; seed < 200; seed++) {
        final rng = Random(seed);
        var residents = <String>{};
        var last = DateTime(2026, 8, 20, 8, 0);
        for (var open = 0; open < 40; open++) {
          // 30分ごとに開く(estimateTickCount で 2コマ)。
          final now = last.add(const Duration(minutes: 40));
          final r = evolveWhileAway(
            plantedPlants: planted,
            biomeId: biome,
            month: 8,
            residents: residents,
            lastSeenAt: last,
            now: now,
            rng: rng,
            plantsData: plants,
            insectsData: insects,
            birdsData: birds,
            biomes: biomes,
            seasonOffset: (season as Map).cast<String, dynamic>(),
            placedFeatures: feeders,
          );
          residents = r.residents;
          arrivals += r.arrivals.length;
          if (residents.isEmpty) empty++;
          sumRes += residents.length;
          total++;
          last = now;
        }
      }
      final label = feeders.isEmpty ? '餌台なし' : feeders.first;
      // ignore: avoid_print
      print('【$label】 誰も居ない ${(empty / total * 100).toStringAsFixed(0)}% / '
          '平均 ${(sumRes / total).toStringAsFixed(2)}羽 / '
          '1回あたりの到来 ${(arrivals / total).toStringAsFixed(2)}羽');
    }
  });
}
