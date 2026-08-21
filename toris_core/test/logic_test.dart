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

  // ラジオは**会った鳥だけ**で鳴る。`radio.py` 冒頭の背骨で、
  // コレクション性の構造的な保証そのもの。
  //
  // 2026-08-21: 移植でこの絞り込みが丸ごと落ちていて、**初回起動から
  // 未観察の鳥が鳴いていた**(CEO が発見)。掲載文の
  // "A radio made only of birds you've met" もここが支えている。
  test('ラジオの顔ぶれ: 会った鳥だけが鳴く(Python 版と一致)', () {
    final fx = json
        .decode(File('test/fixtures/logic.json').readAsStringSync())
        .cast<String, dynamic>();
    var checked = 0;
    for (final c in fx['radio_cast'] as List) {
      final pool = (c['biome_birds'] as List).map((e) => '$e').toList();
      final obs = (c['observed'] as Map)
          .map((k, v) => MapEntry('$k', (v as num).toInt()));
      expect(observedInBiome(pool, obs), c['expected'],
          reason: 'observed=$obs のときの顔ぶれが違う');
      checked++;
    }
    // **記録はあるが count=0** の鳥を弾くところまで見ている(16通り)。
    expect(checked, 16, reason: '16通りを見ているはず');
  });

  // **両言語に書いた定数**そのものを突き合わせる。
  //
  // 2026-08-21: `ITEM_OFFERED` と `kOfferedItems` を両方に書いたのに
  // fixtures へ足すのを忘れ、**抽選プールが 6種 と 3種 でずれていた**。
  // 関数の入出力だけ見ていると、定数のずれは最後まで誰も気づかない。
  test('両言語に書いた定数が一致する', () {
    final fx = json
        .decode(File('test/fixtures/logic.json').readAsStringSync())
        .cast<String, dynamic>();
    final c = fx['constants'] as Map<String, dynamic>;

    expect(kOfferedItems, c['item_offered'], reason: '広告で出す3種がずれている');
    expect(kItemDurationHours, c['item_duration_hours']);
    expect(kNyjerTargets.toList()..sort(), c['nyjer_targets']);
    expect(kFeeders.keys.toList()..sort(), c['feeders']);

    // 餌台の中身(気質・大型アクセス・上限)まで見る。名前だけ合っていても、
    // draws が入れ替わっていたら来る鳥が丸ごと変わる。
    (c['feeder_meta'] as Map<String, dynamic>).forEach((id, meta) {
      final m = kFeeders[id]!;
      final e = meta as Map<String, dynamic>;
      expect(m['offers'], e['offers'], reason: '$id の offers');
      expect(m['large_access'], e['large_access'], reason: '$id の large_access');
      expect(m['draws'], e['draws'], reason: '$id の draws');
      expect((m['bonus_max'] as num).toDouble(),
          closeTo((e['bonus_max'] as num).toDouble(), 1e-12),
          reason: '$id の bonus_max');
    });
  });

  test('餌台の連鎖: 1728通りで Python 版と一致する(抑制・加点・リス返し)', () {
    // 餌台 → リス → タカ → 警戒心の強い鳥を抑制。
    // 分岐が細かい(かご型だけならリスは届かない/堅果は地面なので届く)ので総当たり。
    var checked = 0;
    for (final c in fx['feeder_chain'] as List) {
      final feats = (c['features'] as List).map((e) => '$e').toList();
      final pset = (c['planted'] as List).map((e) => '$e').toList();
      // baffled = リス返しが効いている6時間。餌台由来の large_access だけが
      // 落ち、**地面の堅果は守れない**ところまで突き合わせる(2026-08-21)。
      final baffled = c['baffled'] as bool;
      final label = '餌台=$feats 植えた=$pset baffled=$baffled';

      expect(availableFoods(feats, pset, baffled: baffled).toList()..sort(),
          c['foods'], reason: '$label の食べ物が違う');
      final r = resolveFeeders(feats, pset, baffled: baffled);
      expect(r.animals, c['animals'], reason: '$label の動物が違う');
      expect(r.raptors, c['raptors'], reason: '$label の猛禽が違う');

      (c['mult'] as Map<String, dynamic>).forEach((w, v) {
        expect(waryArrivalMultiplier(double.parse(w), r.raptors),
            closeTo(v as num, 1e-9),
            reason: '$label 警戒心$w の抑制が違う');
        checked++;
      });

      // 餌台の到来加点。**気質と食性で効きが変わる**ので総当たりで見る。
      // ここで Python の `or 0.5`(警戒心0.0 が偽になる)と Dart の
      // `?? 0.5`(null のときだけ)の食い違いを捕まえた(2026-08-20)。
      (c['bonus'] as Map<String, dynamic>).forEach((key, v) {
        final parts = key.split('|');
        final bird = {
          'wariness': double.parse(parts[0]),
          'eats_plants': parts[1] == '1' ? ['x'] : <String>[],
        };
        expect(feederArrivalBonus(feats, bird), closeTo(v as num, 1e-9),
            reason: '$label 警戒心${parts[0]} '
                '${parts[1] == '1' ? '種食' : '虫のみ'} の加点が違う');
        checked++;
      });
    }
    // 288 = 6通りの餌台 × 8通りの庭 × 6通りの警戒心(抑制)。
    // これに餌台の加点(警戒心6 × 種食/虫食2 = 12)が乗って 864。
    // 2026-08-21: リス返しの有無(baffled 2通り)を掛けて 1728 になった。
    // **数が減ったら、突き合わせている範囲が狭まったということ。**
    expect(checked, 1728, reason: '1728通りを見ているはず(減ったら手当てが要る)');
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

  test('今日の顔ぶれ: 種類・ギルドのまとまり・一文が Python 版と一致(207通り)', () {
    // ラジオの「なぜこの3羽が一緒か」。実データの3種組から拾っている。
    // ギルドの偏り(6割)と気候の重なり(0.45)の境目を踏む。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');

    // ギルドの表(絵文字と英語)そのもの
    final gl = (fx['guild_labels'] as Map).cast<String, dynamic>();
    expect(kGuildLabels.keys.toList(), gl.keys.toList(), reason: 'ギルドのキーか並び');
    gl.forEach((k, v) {
      expect(guildIcon(k), (v as List)[0], reason: '$k の絵文字');
      expect(guildLabel(k), v[1], reason: '$k のラベル');
    });
    // 知らないキーは other に落ちる
    expect(guildLabel('zzz'), guildLabel('other'));

    for (final c in fx['lineup'] as List) {
      final trio = (c['birds'] as List).map((e) => '$e').toList();
      final label = trio.join('+');

      final story = lineupStory(trio, birds);
      final e = c['story'];
      if (e == null) {
        expect(story, isNull, reason: '$label は語れることが無いはず');
      } else {
        expect(story?.kind, (e as Map)['kind'], reason: '$label の種類');
        expect(story?.guild, e['guild'], reason: '$label のギルド');
      }
      expect(lineupStoryText(story), c['text'], reason: '$label の一文');

      final groups = guildGroups(trio, birds);
      expect([
        for (final g in groups) [g.guild, g.icon, g.birds.length, g.birds]
      ], c['groups'], reason: '$label のギルドのまとまり(順序も)');
    }
  });

  test('撹乱の一文: 3種類 × 倒れた/持ちこたえた が Python 版と一致', () {
    // **倒れなかった時も語る。** 何も出さないと、嵐が来たこと自体が
    // 無かったことになる。
    for (final c in fx['disturbance_story'] as List) {
      final removed = (c['removed'] as List).map((e) => '$e').toList();
      expect(
          disturbanceStory(c['type'] as String, c['icon'] as String, removed),
          c['text'],
          reason: '${c['type']} / 倒れた ${removed.length} 件');
    }
    // Dart 側の呼び名の表が、撹乱の種類を全部持っているか
    for (final k in kDisturbances.keys) {
      expect(kDisturbanceLabels.containsKey(k), isTrue,
          reason: '$k の呼び名が無い');
    }
  });

  test('留守の要約と相対時刻が Python 版と一致(境目も)', () {
    for (final c in fx['summarize'] as List) {
      final ids = (c['birds'] as List).map((e) => '$e').toList();
      expect(summarizeEvents(ids, (b) => b), c['text'],
          reason: '$ids の要約');
    }
    final now = DateTime(2026, 8, 16, 12, 0, 0);
    for (final c in fx['humanize'] as List) {
      final sec = c['sec'] as int;
      expect(humanizeDelta(now.subtract(Duration(seconds: sec)), now),
          c['text'],
          reason: '$sec 秒前の言い方');
    }
    expect(awayHeadline('XYZ'), fx['away_headline']);
    expect(kSeeWhatHappened, fx['see_what']);
  });

  test('図鑑プロフィール: 37種すべてで Python 版と一致する', () {
    // ⚠️ ここは Dart 側に分類の表を**手で書いて間違えた**ところ。
    // 実データが使う crow/falcon/fox/rodent/weasel が表に無く、逆に
    // mammal/corvid/other という存在しない分類を書いていた。表ごと比べる。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final preds = load('predators');

    // 分類の表そのもの(数・キー・表示名・**並び**まで)
    final expectedLabels =
        (fx['predator_labels'] as Map).cast<String, dynamic>();
    expect(kPredatorLabels.length, expectedLabels.length,
        reason: '分類の数が違う');
    expect(kPredatorLabels.keys.toList(), expectedLabels.keys.toList(),
        reason: '分類のキーか並びが違う');
    expectedLabels.forEach((k, v) {
      expect(kPredatorLabels[k], v, reason: '$k の表示名が違う');
    });

    for (final c in fx['profiles'] as List) {
      final bid = c['bird'] as String;
      final prof = buildBirdProfile(
        birdId: bid,
        bird: (birds[bid] as Map).cast<String, dynamic>(),
        plants: plants,
        insects: insects,
        biomes: biomes,
        predatorsData: preds,
      );
      expect([for (final l in prof.likes) [l.kind, l.id]], c['likes'],
          reason: '$bid の好きなもの(順序も)');
      expect(prof.home, c['home'], reason: '$bid の好きな場所');
      expect(prof.fears.categories, c['categories'], reason: '$bid のこわいもの');
      expect(prof.fears.genusLevel, c['genus_level'],
          reason: '$bid の同属由来かどうか');
      expect(predatorLabels(bid, preds), c['labels'],
          reason: '$bid のこわいものの表示名');
      expect(predatorHasData(bid, preds), c['has_data'],
          reason: '$bid の天敵データの有無');
    }
  });

  test('知らない分類は、画面に出さず静かに落とす', () {
    // データが増えたときに、生のキーが図鑑に出ないための安全弁。
    final u = fx['predator_unknown'] as Map<String, dynamic>;
    final dirty = <String, dynamic>{
      'zzz_unknown': {
        'categories': ['raptor', 'zzz_unknown', 'owl'],
        'level': 'genus',
      }
    };
    expect(predatorCategories('zzz_unknown', dirty), u['categories']);
    expect(predatorIsGenusLevel('zzz_unknown', dirty), u['genus']);
    expect(predatorLabels('zzz_unknown', dirty), u['labels']);
    expect(predatorHasData('zzz_unknown', dirty), u['has_data']);
    // そもそも居ない鳥
    expect(predatorCategories('no_such_bird', dirty), u['missing_bird']);
  });

  test('食物網の統計と「足りないもの」の提案が Python 版と一致する(40状況 × 37種)', () {
    // 「どうすればあの鳥が来るか」。順序も含めて比べる — 提案の順序は
    //   ① 直接食べる植物 → ② 目当ての虫を成り立たせる植物
    // で、そこがズレると案内が変わる。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final season = load('season_offset');

    var checked = 0;
    for (final c in fx['helpers'] as List) {
      final planted = (c['planted'] as List).map((e) => '$e').toList();
      final biome = c['biome'] as String;
      final month = c['month'] as int;
      final label = '$biome $planted $month月';

      final web = buildFoodWeb(
        plantedPlants: planted,
        biomeId: biome,
        month: month,
        plantsData: plants,
        insectsData: insects,
        birdsData: birds,
        biomes: biomes,
        seasonOffset: season,
      );

      final st = networkStats(web);
      final e = c['stats'] as Map<String, dynamic>;
      expect(st.plants, e['plants'], reason: '$label の植物の数');
      expect(st.insects, e['insects'], reason: '$label の虫の数');
      expect(st.birdsActive, e['birds_active'], reason: '$label の来られる鳥の数');
      expect(st.edges, e['edges'], reason: '$label の辺の数');
      if (e['hub'] == null) {
        expect(st.hub, isNull, reason: '$label のハブは無いはず');
      } else {
        final h = e['hub'] as List;
        expect(st.hub?.id, h[0], reason: '$label のハブが違う');
        expect(st.hub?.kind, h[1], reason: '$label のハブの種別が違う');
        expect(st.hub?.degree, h[2], reason: '$label のハブの次数が違う');
      }

      (c['suggest'] as Map<String, dynamic>).forEach((bid, v) {
        final r = suggestForBird(
          targetBirdId: bid,
          plantedPlants: planted,
          biomeId: biome,
          month: month,
          plantsData: plants,
          insectsData: insects,
          birdsData: birds,
          biomes: biomes,
          seasonOffset: season,
        )!;
        final m = v as Map<String, dynamic>;
        expect(r.currentProbability, closeTo(m['prob'] as num, 1e-9),
            reason: '$label $bid の現在の確率');
        expect(r.hasFoodPath, m['has_food_path'],
            reason: '$label $bid の食物経路の有無');
        expect([
          for (final x in r.suggestions) [x.plantId, x.directness, x.insectId]
        ], m['items'], reason: '$label $bid の提案(順序も)');
        checked++;
      });
    }
    expect(checked, greaterThan(1400));
  });

  test('仮に1つ植えたときの確率が Python 版と一致する(96通り)', () {
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final season = load('season_offset');

    for (final c in fx['simulate'] as List) {
      final p = simulateWithAddedPlant(
        targetBirdId: c['bird'] as String,
        plantedPlants: const ['sakura'],
        candidatePlant: c['candidate'] as String,
        biomeId: c['biome'] as String,
        month: 5,
        plantsData: plants,
        insectsData: insects,
        birdsData: birds,
        biomes: biomes,
        seasonOffset: season,
      );
      expect(p, closeTo(c['prob'] as num, 1e-9),
          reason: '${c['bird']} に ${c['candidate']} を足したときの確率');
    }
  });

  test('居ない鳥を指しても落ちない(null が返る)', () {
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    expect(
        suggestForBird(
          targetBirdId: 'not_a_bird',
          plantedPlants: const [],
          biomeId: 'kyoto',
          month: 5,
          plantsData: load('plants'),
          insectsData: load('insects'),
          birdsData: load('birds'),
          biomes: load('biomes'),
          seasonOffset: load('season_offset'),
        ),
        isNull);
  });

  test('中心性: レア度係数の上書きが Python 版と一致する(19状況 × 37種)', () {
    // ⚠️ 元データはリポジトリに無く、ふだんは発動しない道。だから
    // fixtures 側で値を注入して**実際に発動させた**答えと突き合わせる。
    // 「動作が同じだから」と式を省くと、データが来た日にズレる。
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

    var checked = 0;
    for (final c in fx['centrality'] as List) {
      final pr = c['pr'];
      final corrected = c['corrected'];
      // 学名がキャッシュに無い場合(pr が null)は、当たらない表を渡す
      final table = <String, Centrality>{};
      if (pr == null) {
        table['NOT_A_REAL_TAXON'] = const Centrality(prCorrected: 1e-6);
      } else {
        for (final b in birds.values) {
          final sci = (b as Map)['scientific'] as String?;
          if (sci == null || sci.isEmpty) continue;
          table[sci.toUpperCase()] = corrected == true
              ? Centrality(prCorrected: (pr as num).toDouble(), pr: 1e-3)
              : Centrality(pr: (pr as num).toDouble());
        }
      }

      (c['probs'] as Map<String, dynamic>).forEach((bid, v) {
        final a = arrivalProbability(
            birdId: bid,
            web: web,
            biomeId: 'kyoto',
            birdsData: birds,
            centralities: table);
        final e = v as List;
        expect(a.probability, closeTo(e[0] as num, 1e-9),
            reason: '$bid: pr=$pr corrected=$corrected の確率が違う');
        expect(a.rarityFactor, closeTo(e[1] as num, 1e-9),
            reason: '$bid: pr=$pr corrected=$corrected のレア度係数が違う');
        if (e[2] == null) {
          expect(a.centralityUsed, isNull, reason: '$bid: 使っていないはず');
        } else {
          expect(a.centralityUsed, closeTo(e[2] as num, 1e-15));
        }
        checked++;
      });
    }
    expect(checked, greaterThan(600));
  });

  test('中心性: 渡さなければ、確率は今までと1ビットも変わらない', () {
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
      final empty = arrivalProbability(
          birdId: bid,
          web: web,
          biomeId: 'kyoto',
          birdsData: birds,
          centralities: const {});
      expect(empty.probability, bare.probability);
      expect(bare.centralityUsed, isNull);
    }
  });

  test('今日の庭アイテム: 対象・期限・加点が Python 版と一致する', () {
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final g = fx['garden_items'] as Map<String, dynamic>;

    expect(kItemDurationHours, g['duration_hours']);

    // ── 対象種と、選べるかどうか ──
    for (final c in g['targets'] as List) {
      final item = c['item'] as String;
      final biome = c['biome'] as String;
      expect(targetBirdIds(item, biome, birds).toList()..sort(), c['targets'],
          reason: '$item @ $biome の対象種が違う');
      expect(itemIsAvailable(item, biome, birds), c['available'],
          reason: '$item @ $biome の可否が違う');
      // 餌台に依存するアイテム(継ぎ足し=餌台が要る / リス返し=開放型が要る)。
      (c['available_by_feeders'] as Map<String, dynamic>).forEach((k, v) {
        final feeders = k == 'none' ? <String>[] : k.split('|');
        expect(itemIsAvailable(item, biome, birds, placedFeeders: feeders), v,
            reason: '$item @ $biome 餌台=$k の可否が違う');
      });
      expect(kGardenItems[item]!.effectKind, c['effect_kind']);
      expect(kGardenItems[item]!.value, closeTo(c['value'] as num, 1e-12));
      // **絵文字も突き合わせる。** 勘で書いて2件違っていた(🍬→🌺 / 🌰→🌾)。
      expect(kGardenItems[item]!.emoji, c['emoji'], reason: '$item の絵文字');
    }

    // ── 選べない理由の文 ──
    // アイテム名は英訳が無いので、名前を固定の印にして
    // 「文の組み立て」だけを比べる。
    for (final c in g['reasons'] as List) {
      final item = c['item'] as String;
      final got = itemUnavailableReason(item, c['biome'] as String, birds)
          .replaceAll(kItemNames[item]!, 'NAME');
      expect(got, c['text'], reason: '$item @ ${c['biome']} の理由文');
    }

    // ── 効いている時間の境目(両端を含む) ──
    final placedAt = DateTime(2026, 8, 16, 9, 0, 0);
    final plc = placeItem('feeder', now: placedAt);
    for (final c in g['active'] as List) {
      final at = placedAt.add(Duration(seconds: c['offset_sec'] as int));
      expect(itemIsActive(plc, at: at), c['active'],
          reason: '${c['offset_sec']}秒後の有効判定が違う');
      expect(itemHoursRemaining(plc, at: at),
          closeTo(c['hours_left'] as num, 1e-6),
          reason: '${c['offset_sec']}秒後の残り時間が違う');
    }

    // ── 加点の値 ──
    for (final c in g['bonus'] as List) {
      final item = c['item'] as String;
      final p = placeItem(item, now: placedAt);
      final at = placedAt.add(const Duration(hours: 1));
      final fn = makeArrivalBonusFn(p, 'charlotte', birds, at: at);
      (c['arrival'] as Map<String, dynamic>).forEach((bid, v) {
        expect(fn(bid), closeTo(v as num, 1e-12),
            reason: '$item の $bid への加点が違う');
      });
      expect(itemDepartureBonus(p, at: at),
          closeTo(c['departure'] as num, 1e-12), reason: '$item の退去減算');
      expect(isBaffleActive(p, at: at), c['baffle'],
          reason: '$item のリス返し判定が違う');
      expect(
          [
            for (final bid in (c['arrival'] as Map).keys)
              if (isItemBoostedArrival(bid, p, 'charlotte', birds, at: at))
                bid
          ]..sort(),
          c['boosted'],
          reason: '$item の対象判定');
      // 切れたらゼロに戻る
      expect(itemDepartureBonus(p, at: placedAt.add(const Duration(hours: 7))),
          closeTo(c['expired_departure'] as num, 1e-12));
    }
  });

  test('アイテムの加点は、退去には効かない(到着だけ)', () {
    // Python の run_turn は、退去判定に**加点前の p** を使う。
    // 加点を退去にも効かせると、アイテムが「去りにくくする」二重の効果を持つ。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final season = load('season_offset');

    // 退去率 0.3-0.25p は最大 0.3。最初の乱数を 0.99 にすれば誰も去らない。
    // 到着は加点で必ず起きる(加点 1.0 → p は 1.0 に張り付く)。
    final r = runTurn(
      plantedPlants: const ['sakura'],
      biomeId: 'kyoto',
      month: 5,
      residents: {'suzume'},
      rng: _Scripted([0.99, ...List.filled(200, 0.0)]),
      plantsData: plants,
      insectsData: insects,
      birdsData: birds,
      biomes: biomes,
      seasonOffset: season,
      arrivalBonusFn: (_) => 1.0,
    );
    expect(r.departures, isEmpty, reason: '乱数 0.99 では誰も去らないはず');
    expect(r.arrivals.length, 1, reason: '加点で1種は必ず来る');

    // 退去減算の下限 0.02。減算を大きくしても 0.02 未満にはならない。
    final r2 = runTurn(
      plantedPlants: const ['sakura'],
      biomeId: 'kyoto',
      month: 5,
      residents: {'suzume'},
      rng: _Scripted(List.filled(200, 0.019)),
      plantsData: plants,
      insectsData: insects,
      birdsData: birds,
      biomes: biomes,
      seasonOffset: season,
      departureBonus: 10.0,
    );
    expect(r2.departures, ['suzume'],
        reason: '0.019 < 下限 0.02 なので、それでも去る');
  });

  test('なぜ来たか: 実データ1480通りで Python 版と同じ一文になる', () {
    // 「あなたが組んだ関係が鳥を呼んだ」証拠。一番重みの大きい経路を1つだけ
    // 採る、という判断がズレると文が変わる。捏造しないことがここの肝。
    Map<String, dynamic> load(String n) =>
        (jsonDecode(File('test/fixtures/$n.json').readAsStringSync()) as Map)
            .cast<String, dynamic>();
    final birds = load('birds');
    final plants = load('plants');
    final insects = load('insects');
    final biomes = load('biomes');
    final season = load('season_offset');

    FoodWeb? web;
    String? key;
    var checked = 0;
    for (final c in fx['reasons'] as List) {
      final k = '${c['biome']}|${c['planted']}|${c['month']}';
      if (k != key) {
        key = k;
        web = buildFoodWeb(
          plantedPlants: (c['planted'] as List).map((e) => '$e').toList(),
          biomeId: c['biome'] as String,
          month: c['month'] as int,
          plantsData: plants,
          insectsData: insects,
          birdsData: birds,
          biomes: biomes,
          seasonOffset: season,
        );
      }
      final ev = buildReason(
        birdId: c['bird'] as String,
        web: web!,
        arrivedAt: '2026-08-15T09:00:00',
        birdsData: birds,
        plantsData: plants,
        insectsData: insects,
      );
      expect(ev.reasonText, c['text'], reason: '$k ${c['bird']} の一文が違う');
      expect(ev.relatedPlant, c['plant'], reason: '$k ${c['bird']} の植物が違う');
      expect(ev.relatedInsect, c['insect'], reason: '$k ${c['bird']} の虫が違う');
      checked++;
    }
    expect(checked, 1480);
  });

  test('なぜ来たかの記録: 重複を除いて溜まる(Python 版と一致)', () {
    // 同じ鳥の同じ理由は1件だけ。そうでないと「関係の証拠」ではなく履歴になる。
    final evs = [
      const ArrivalEvent('a', 'X', '2026-08-01T10:00:00'),
      const ArrivalEvent('a', 'X', '2026-08-02T10:00:00'),
      const ArrivalEvent('a', 'Y', '2026-08-03T10:00:00'),
      const ArrivalEvent('b', 'X', '2026-07-01T10:00:00'),
      const ArrivalEvent('', 'Z', '2026-08-04T10:00:00'),
      const ArrivalEvent('c', '', '2026-08-05T10:00:00'),
      const ArrivalEvent('d', 'W', ''),
    ];
    for (final c in fx['eco_log'] as List) {
      final n = c['n'] as int;
      final log = appendEvents(null, evs.sublist(0, n));
      expect(log.map((e) => e.toJson()).toList(), c['log'],
          reason: '$n 件流し込んだ結果が違う');
      // 二度流し込んでも増えない
      expect(appendEvents(log, evs.sublist(0, n)).length, c['twice_len'],
          reason: '$n 件を二度流したら増えてしまった');
      expect(entriesForBird(log, 'a').map((e) => e.toJson()).toList(),
          c['for_a']);
      expect(entriesForBird(log, 'zzz'), isEmpty);
    }

    final full = appendEvents(null, evs);
    final ents = entriesForBird(full, 'a');
    for (final c in fx['founding'] as List) {
      final first = c['observed_first'] as String?;
      expect([for (final e in ents) isFoundingRecord(e, ents, first)],
          c['flags'], reason: 'observed_first=$first の判定が違う');
      expect(isFoundingRecord(ents.first, const [], first), c['empty']);
    }
  });

  test('なぜ来たかは消えない: 消す関数を持たない', () {
    // 交渉不能の原則2「罰しない」。撹乱で植物が失われても記録は残る。
    var log = appendEvents(null, [
      const ArrivalEvent('a', 'drawn to Sakura', '2026-08-01T10:00:00'),
    ]);
    // 植物が全部消えた状態で、もう一度進んでも記録は減らない
    log = appendEvents(log, const []);
    expect(log.length, 1);
    expect(log.first.text, 'drawn to Sakura');
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
