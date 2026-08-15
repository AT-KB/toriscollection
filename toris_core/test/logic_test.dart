/// 移植したロジックが Python 版と**同じ答えを返す**かを、総当たりで確かめる。
///
/// 手で書き写したテストには、書き写した人の思い込みも一緒に写る。ここでは
/// Python 版に入力を総当たりで食わせた答えの表(`tools/logic_fixtures.py` が作る)
/// を読み、Dart が再現できるかだけを見る。切り捨て除算・型変換・境界の不等号の
/// ズレは、ここで落ちる。
library;

import 'dart:convert';
import 'dart:math';
import 'dart:io';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

/// 決めた順に値を返す乱数。境目の試験用。
class _Scripted implements Random {
  final List<double> _v;
  int _i = 0;
  _Scripted(this._v);
  @override
  double nextDouble() => _v[_i++ % _v.length];
  @override
  int nextInt(int max) => 0;
  @override
  bool nextBool() => false;
}

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

  test('餌台の連鎖: 288通りで Python 版と一致する', () {
    // 餌台 → リス → タカ → 警戒心の強い鳥を抑制。
    // 分岐が細かい(かご型だけならリスは届かない/堅果は地面なので届く)ので総当たり。
    var checked = 0;
    for (final c in fx['feeder_chain'] as List) {
      final feats = (c['features'] as List).map((e) => '$e').toList();
      final pset = (c['planted'] as List).map((e) => '$e').toList();
      final label = '餌台=$feats 植えた=$pset';

      expect(availableFoods(feats, pset).toList()..sort(), c['foods'],
          reason: '$label の食べ物が違う');
      final r = resolveFeeders(feats, pset);
      expect(r.animals, c['animals'], reason: '$label の動物が違う');
      expect(r.raptors, c['raptors'], reason: '$label の猛禽が違う');

      (c['mult'] as Map<String, dynamic>).forEach((w, v) {
        expect(waryArrivalMultiplier(double.parse(w), r.raptors),
            closeTo(v as num, 1e-9),
            reason: '$label 警戒心$w の抑制が違う');
        checked++;
      });
    }
    expect(checked, 288, reason: '288通りを見ているはず');
  });

  test('餌台: かご型ならリスは来ず、臆病な鳥も抑えられない', () {
    // 唯一の駆け引き。かご型を選べばタカは来ない。
    expect(resolveFeeders(['feeder_cage'], []).animals, isEmpty);
    expect(resolveFeeders(['feeder_cage'], []).raptors, isEmpty);
    expect(resolveFeeders(['feeder_open'], []).raptors, ['cooper_hawk']);
    // 堅果は地面に落ちるので、かご型でもリスは食べられる
    expect(resolveFeeders(['feeder_cage'], ['white_oak']).animals,
        ['gray_squirrel']);
    // 餌台を置かなければ、確率は今まで通り(1.0 倍)
    expect(waryArrivalMultiplier(1.0, const []), 1.0);
  });

  test('餌台を置かない庭の到来確率は、今までと1ビットも変わらない', () {
    // 配線を足したせいで既存の庭が変わっていないことを、実データで確かめる。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final web = buildFoodWeb(
      plantedPlants: const ['sakura', 'kunugi'],
      biomeId: 'kyoto',
      month: 5,
      plantsData: load('plants'),
      insectsData: load('insects'),
      birdsData: birds,
      biomes: load('biomes'),
      seasonOffset: load('season_offset'),
    );
    for (final bid in birds.keys) {
      final bare = arrivalProbability(
          birdId: bid, web: web, biomeId: 'kyoto', birdsData: birds);
      final withRaptor = arrivalProbability(
          birdId: bid,
          web: web,
          biomeId: 'kyoto',
          birdsData: birds,
          raptors: const ['cooper_hawk']);
      expect(bare.waryFactor, 1.0, reason: '$bid: 猛禽が居なければ 1.0 倍');
      // 警戒心 0 の鳥は抑制を受けない。それ以外は必ず下がる。
      final w = pyFloat(birds[bid]['wariness']) ?? 0.5;
      if (w > 0) {
        expect(withRaptor.probability, lessThan(bare.probability + 1e-12),
            reason: '$bid: タカが居れば上がることはない');
      }
    }
  });

  test('留守のあいだの進み方: 区切りが Python 版と同じ', () {
    // 急かさない設計の根っこ。**時間は勝手に進む**(原則1「受動的である」)。
    expect(estimateTickCount(0.0), 0);
    expect(estimateTickCount(4 / 60), 0); // 5分未満は何も起きない
    expect(estimateTickCount(10 / 60), 1);
    expect(estimateTickCount(1.0), 2);
    expect(estimateTickCount(3.0), 3);
    expect(estimateTickCount(8.0), 4);
    expect(estimateTickCount(20.0), 5);
    expect(estimateTickCount(48.0), 6); // 上限
  });

  test('撹乱: 定数と判定の境目が Python 版と同じ', () {
    // 乱数列は言語で違うので、結果ではなく**判定の境目**を確かめる。
    final d = fx['disturbance'] as Map<String, dynamic>;
    expect(kDisturbanceP, closeTo(d['base_p'] as num, 1e-12));
    expect(kDefaultSensitivity, closeTo(d['default_sensitivity'] as num, 1e-12));
    (d['weights'] as Map<String, dynamic>).forEach((k, v) {
      expect(kDisturbanceWeights[k], closeTo(v as num, 1e-12), reason: '$k の頻度');
    });
    (d['severity'] as Map<String, dynamic>).forEach((k, v) {
      expect(kDisturbances[k]!.severity, closeTo(v as num, 1e-12),
          reason: '$k の強さ');
    });

    // 境目: 確率ちょうどでは起きない(>= で弾く)
    expect(rollDisturbance(_Scripted([0.10])), isNull);
    expect(rollDisturbance(_Scripted([0.0999, 0.0])), isNotNull);

    // 全滅させない: 全部倒れる判定でも1本は残る
    final planted = ['a', 'b', 'c'];
    final removed = applyDisturbance(planted, kDisturbances['logging']!,
        const {}, _Scripted([0.0, 0.0, 0.0, 0.0]));
    expect(removed.length, planted.length - 1, reason: '最後の1本は残すはず');
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
