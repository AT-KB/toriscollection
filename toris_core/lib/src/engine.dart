/// 「植える → 虫が来る → その虫を目当てに鳥が来る」の仕組み。
/// `toris_collection/engine.py` の移植。
///
/// この商品の背骨そのもの。植生をつくると虫が湧き、その虫を食べに鳥が来る。
/// 来た鳥は馴染んで近くで鳴くようになり、その声で朝を迎える。
///
/// 交渉不能の原則4「生態に誠実」— 関係は恣意的に足さない。誰が何を食べるかは
/// データ(GloBI 由来)に書いてあるとおりに繋ぐ。
library;

import 'dart:math';

import 'py_coerce.dart';

/// その土地・月の気温。
/// 南半球では季節を半年ずらす(北半球の対応する月のオフセットを使う)。
double currentTemperature(
    String biomeId, int month, Map<String, dynamic> biomes,
    Map<String, dynamic> seasonOffset) {
  final biome = (biomes[biomeId] as Map?) ?? const {};
  final hemisphere = (biome['hemisphere'] ?? 'north') as String;
  final m = hemisphere == 'south' ? ((month - 1 + 6) % 12) + 1 : month;
  final offset = pyFloat(seasonOffset['$m']) ?? 0.0;
  return (pyFloat(biome['temp_mean']) ?? 0.0) + offset;
}

/// 気温適合度(0..1)。適温の幅の中なら 1.0 に近く、外れるほど急に落ちる。
double temperatureFit(double temp, List<dynamic>? fitRange) {
  if (fitRange == null || fitRange.length < 2) return 0.0;
  final lo = pyFloat(fitRange[0]), hi = pyFloat(fitRange[1]);
  if (lo == null || hi == null) return 0.0;
  final center = (lo + hi) / 2;
  final half = (hi - lo) / 2;
  if (half <= 0) return 0.0;
  final distance = (temp - center).abs();
  if (distance <= half) return 1.0 - 0.5 * (distance / half);
  final overshoot = distance - half;
  return max(0.0, 0.5 * pow(0.9, overshoot).toDouble());
}

/// 食物網。植えた植物から、湧く虫、来られる鳥までを繋いだもの。
class FoodWeb {
  /// 気温に耐えて育っている植物 → 適合度
  final Map<String, double> plants;

  /// 依存する植物があって湧いた虫 → 適合度
  final Map<String, double> insects;

  /// 鳥 → その鳥に流れ込む重みの合計(食物網スコア)
  final Map<String, double> birdFood;

  /// 鳥 → 「何を目当てに来られるか」(種別, ID, 重み)
  final Map<String, List<FoodLink>> birdLinks;

  final double temperature;

  const FoodWeb({
    required this.plants,
    required this.insects,
    required this.birdFood,
    required this.birdLinks,
    required this.temperature,
  });
}

class FoodLink {
  final String kind; // 'plant' / 'insect'
  final String id;
  final double weight;
  const FoodLink(this.kind, this.id, this.weight);
}

/// 食物網を組む。`engine.build_network` と同じ判定。
///
/// - 植物: 気温適合が 0.05 未満なら育たない
/// - 虫: 適合 0.1 未満、または食べる植物が1つも無ければ湧かない
/// - 鳥: すべて候補に入るが、繋がりが無ければ食物網スコアは 0
FoodWeb buildFoodWeb({
  required List<String> plantedPlants,
  required String biomeId,
  required int month,
  required Map<String, dynamic> plantsData,
  required Map<String, dynamic> insectsData,
  required Map<String, dynamic> birdsData,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> seasonOffset,
}) {
  final temp = currentTemperature(biomeId, month, biomes, seasonOffset);

  final plants = <String, double>{};
  for (final pid in plantedPlants) {
    final p = plantsData[pid] as Map?;
    if (p == null) continue;
    final fit = temperatureFit(temp, p['temp_fit'] as List?);
    if (fit < 0.05) continue;
    plants[pid] = fit;
  }

  final insects = <String, double>{};
  insectsData.forEach((iid, raw) {
    final ins = raw as Map;
    final fit = temperatureFit(temp, ins['temp_fit'] as List?);
    if (fit < 0.1) return;
    final eats = ((ins['eats_plants'] as List?) ?? const [])
        .map((e) => '$e')
        .where(plants.containsKey);
    if (eats.isEmpty) return;
    insects[iid] = fit;
  });

  final birdFood = <String, double>{};
  final birdLinks = <String, List<FoodLink>>{};
  birdsData.forEach((bid, raw) {
    final bird = raw as Map;
    var score = 0.0;
    final links = <FoodLink>[];
    for (final p in ((bird['eats_plants'] as List?) ?? const [])) {
      final w = plants['$p'];
      if (w != null) {
        score += w;
        links.add(FoodLink('plant', '$p', w));
      }
    }
    for (final i in ((bird['eats_insects'] as List?) ?? const [])) {
      final w = insects['$i'];
      if (w != null) {
        score += w;
        links.add(FoodLink('insect', '$i', w));
      }
    }
    birdFood[bid] = score;
    birdLinks[bid] = links;
  });

  return FoodWeb(
    plants: plants,
    insects: insects,
    birdFood: birdFood,
    birdLinks: birdLinks,
    temperature: temp,
  );
}

/// 鳥が来る確率の内訳。
class Arrival {
  final double probability;
  final double tempFit;
  final double biomeBonus;
  final double foodScore;
  final double foodFactor;
  final double rarityFactor;
  const Arrival({
    required this.probability,
    required this.tempFit,
    required this.biomeBonus,
    required this.foodScore,
    required this.foodFactor,
    required this.rarityFactor,
  });
}

/// 出現確率 = 気温適合 × 土地 × 食物網 × レア度 × 0.5。
///
/// `engine.calculate_arrival_probability` と同じ式。最後の 0.5 は
/// 「滞在2〜4種の落ち着いた庭」に収めるための引き締め。
///
/// 中心性(Sony CSL の PageRank 補正)による上書きは**移していない**。
/// 現行もデータが無ければシードの rarity を使う作りで、そちらに合わせている。
Arrival arrivalProbability({
  required String birdId,
  required FoodWeb web,
  required String biomeId,
  required Map<String, dynamic> birdsData,
}) {
  final bird = (birdsData[birdId] as Map?) ?? const {};
  final tFit = temperatureFit(web.temperature, bird['temp_fit'] as List?);
  final prefs =
      ((bird['biome_pref'] as List?) ?? const []).map((e) => '$e').toList();
  final biomeBonus = prefs.contains(biomeId) ? 1.0 : 0.15;

  final foodScore = web.birdFood[birdId] ?? 0.0;
  final foodFactor =
      foodScore <= 0 ? 0.0 : 1.0 - pow(0.6, foodScore).toDouble();

  final rarity = pyFloat(bird['rarity']) ?? 0.5;
  final rarityFactor = (1.0 - rarity * 0.85) * 0.9;

  var prob = tFit * biomeBonus * foodFactor * rarityFactor * 0.5;
  prob = prob.clamp(0.0, 1.0);

  return Arrival(
    probability: prob,
    tempFit: tFit,
    biomeBonus: biomeBonus,
    foodScore: foodScore,
    foodFactor: foodFactor,
    rarityFactor: rarityFactor,
  );
}
