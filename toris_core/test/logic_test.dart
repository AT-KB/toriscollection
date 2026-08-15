/// 移植したロジックが Python 版と**同じ答えを返す**かを、総当たりで確かめる。
///
/// 手で書き写したテストには、書き写した人の思い込みも一緒に写る。ここでは
/// Python 版に入力を総当たりで食わせた答えの表(`tools/logic_fixtures.py` が作る)
/// を読み、Dart が再現できるかだけを見る。切り捨て除算・型変換・境界の不等号の
/// ズレは、ここで落ちる。
library;

import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

void main() {
  final f = File('test/fixtures/logic.json');
  late Map<String, dynamic> fx;

  setUpAll(() {
    if (!f.existsSync()) {
      fail('先に `py -3 tools/logic_fixtures.py` を実行して、Python 版の答えを'
          '用意すること。');
    }
    fx = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
  });

  test('群れ: Python 版と同じ答えになる(種の書き方 × 観察回数の総当たり)', () {
    var checked = 0;
    for (final c in fx['flock'] as List) {
      final bird = Map<String, dynamic>.from(c['bird'] as Map);
      final data = <String, dynamic>{'x': bird};

      expect(flockCap('x', data), c['cap'],
          reason: 'cap が違う: bird=$bird');
      expect(flockCap('nope', data), c['cap_missing'],
          reason: 'データに無い ID の cap が違う');

      for (final s in c['sizes'] as List) {
        final expected = s['size'];
        // Python 側が例外になった入力は、Dart でも「例外なく既定に落ちる」ことだけ見る
        if (expected is String && expected.startsWith('ERROR:')) {
          expect(() => flockSize('x', s['count'], data), returnsNormally);
          continue;
        }
        expect(flockSize('x', s['count'], data), expected,
            reason: 'size が違う: bird=$bird count=${s['count']}');
        checked++;
      }
    }
    expect(checked, greaterThan(300), reason: '総当たりの件数が想定より少ない');
  });

  test('バッジ: 節目の判定と一言が Python 版と一致する', () {
    for (final c in fx['badges'] as List) {
      final days = c['days'] as int?;
      final tier = badgeForDays(days);
      expect(tier?.threshold, c['threshold'], reason: 'days=$days の節目が違う');
      expect(tier?.icon, c['icon'], reason: 'days=$days のアイコンが違う');
      expect(tier?.label, c['label'], reason: 'days=$days の呼び名が違う');
      expect(badgeMessage('コマドリ', days), c['message'],
          reason: 'days=$days の一言が違う');
    }
  });

  test('生態(共起ネットワーク): 37種の全ペアで Python 版と一致する', () {
    // 顔ぶれの選び方の根っこ。1組でもズレると、出てくる鳥が変わる。
    final birds = jsonDecode(File('test/fixtures/birds.json').readAsStringSync())
        as Map<String, dynamic>;

    (fx['guilds'] as Map<String, dynamic>).forEach((id, g) {
      expect(guild(id, birds), g, reason: '$id のギルドが違う');
    });

    var n = 0;
    for (final c in fx['ecology'] as List) {
      final a = c['a'] as String, b = c['b'] as String;
      expect(climateOverlap(a, b, birds), closeTo(c['clim'] as num, 1e-9),
          reason: '$a×$b の気候の重なりが違う');
      expect(dietJaccard(a, b, birds), closeTo(c['diet'] as num, 1e-9),
          reason: '$a×$b の食べ物の重なりが違う');
      expect(coOccurrence(a, b, birds), closeTo(c['co'] as num, 1e-9),
          reason: '$a×$b の共起しやすさが違う');
      n++;
    }
    expect(n, 666, reason: '37種の全ペア(666組)を見ているはず');
  });

  test('顔ぶれの抽選: 重みが効き、同じ鳥を二度選ばない', () {
    final birds = jsonDecode(File('test/fixtures/birds.json').readAsStringSync())
        as Map<String, dynamic>;
    final ids = birds.keys.toList()..sort();

    // 乱数を固定して、選ばれる顔ぶれが決定的になることを見る
    var i = 0;
    const seq = [0.1, 0.4, 0.7, 0.2, 0.9, 0.05, 0.6, 0.3];
    double rnd() => seq[i++ % seq.length];

    final a = pickLineup(ids, birds, 3, rnd);
    expect(a.length, 3);
    expect(a.toSet().length, 3, reason: '同じ鳥を二度選んではいけない');

    // 重みを極端にすると、その鳥が種(seed)に選ばれる
    i = 0;
    final only = ids.first;
    final b = pickLineup(ids, birds, 3, rnd,
        baseWeight: {for (final x in ids) x: x == only ? 10000.0 : 0.0001});
    expect(b.first, only, reason: '基礎重みが効いていない');
  });

  test('到来の仕組み: 実データ4440通りで Python 版と一致する', () {
    // 「植える→虫→鳥」はこの商品の背骨。ここがズレると別物になる。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final season = load('season_offset');

    var checked = 0;
    for (final c in fx['arrivals'] as List) {
      final web = buildFoodWeb(
        plantedPlants: (c['planted'] as List).map((e) => '$e').toList(),
        biomeId: c['biome'] as String,
        month: c['month'] as int,
        plantsData: plants,
        insectsData: insects,
        birdsData: birds,
        biomes: biomes,
        seasonOffset: season,
      );
      expect(web.temperature, closeTo(c['temp'] as num, 1e-9),
          reason: '${c['biome']} ${c['month']}月 の気温が違う');
      expect(web.plants.keys.toList()..sort(), c['plants'],
          reason: '育つ植物が違う');
      expect(web.insects.keys.toList()..sort(), c['insects'],
          reason: '湧く虫が違う');

      (c['probs'] as Map<String, dynamic>).forEach((bid, v) {
        final a = arrivalProbability(
            birdId: bid, web: web, biomeId: c['biome'] as String,
            birdsData: birds);
        expect(a.probability, closeTo((v as List)[0] as num, 1e-9),
            reason: '$bid の到来確率が違う(${c['biome']} ${c['month']}月)');
        expect(a.foodScore, closeTo(v[1] as num, 1e-9),
            reason: '$bid の食物網スコアが違う');
        checked++;
      });
    }
    expect(checked, 4440, reason: '4440通りを見ているはず');
  });

  group('Python の型変換をまねる部分', () {
    test('int(): 小数は0方向へ切り捨て、整数でない文字列は通さない', () {
      expect(pyInt(2), 2);
      expect(pyInt(2.7), 2);
      expect(pyInt(-2.7), -2);
      expect(pyInt('3'), 3);
      expect(pyInt('2.5'), isNull); // Python の int("2.5") は例外
      expect(pyInt('abc'), isNull);
      expect(pyInt(null), isNull);
      expect(pyInt(true), 1);
    });

    test('float(): 小数の文字列も通る', () {
      expect(pyFloat('0.8'), 0.8);
      expect(pyFloat(1), 1.0);
      expect(pyFloat('abc'), isNull);
      expect(pyFloat(''), isNull);
      expect(pyFloat(null), isNull);
    });
  });
}
