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

import 'centrality.dart';
import 'eco_log.dart';
import 'feeder_chain.dart';
import 'py_coerce.dart';
import 'save_code.dart' show isoSeconds;

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

  /// 虫 → その虫が食べている**育っている植物**。
  /// `build_network` は植物→虫の辺も張るので、辺を数えるのに要る。
  final Map<String, List<String>> insectLinks;

  /// 鳥 → その鳥に流れ込む重みの合計(食物網スコア)
  final Map<String, double> birdFood;

  /// 鳥 → 「何を目当てに来られるか」(種別, ID, 重み)
  final Map<String, List<FoodLink>> birdLinks;

  final double temperature;

  const FoodWeb({
    required this.plants,
    required this.insects,
    this.insectLinks = const {},
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
  final insectLinks = <String, List<String>>{};
  insectsData.forEach((iid, raw) {
    final ins = raw as Map;
    final fit = temperatureFit(temp, ins['temp_fit'] as List?);
    if (fit < 0.1) return;
    final eats = ((ins['eats_plants'] as List?) ?? const [])
        .map((e) => '$e')
        .where(plants.containsKey)
        .toList();
    if (eats.isEmpty) return;
    insects[iid] = fit;
    insectLinks[iid] = eats;
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
    insectLinks: insectLinks,
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

  /// 猛禽が居るときの抑制。居なければ 1.0。`feeder_chain` 由来。
  final double waryFactor;

  /// レア度係数を上書きした中心性(補正済み PageRank)。使わなければ null。
  final double? centralityUsed;
  const Arrival({
    required this.probability,
    required this.tempFit,
    required this.biomeBonus,
    required this.foodScore,
    required this.foodFactor,
    required this.rarityFactor,
    this.waryFactor = 1.0,
    this.centralityUsed,
  });
}

/// 出現確率 = 気温適合 × 土地 × 食物網 × レア度 × 0.5。
///
/// `engine.calculate_arrival_probability` と同じ式。最後の 0.5 は
/// 「滞在2〜4種の落ち着いた庭」に収めるための引き締め。
///
/// [centralities] があると、レア度係数が **Sony CSL の補正済み PageRank で
/// 上書きされる**(`centrality.dart`)。元データはリポジトリに無いので Python 側
/// でも発動していないが、式は持っている — 動作が同じだからと省くのは推測で
/// 決めることになる(CEO 2026-08-16)。
///
/// [raptors] に猛禽が居ると、警戒心の強い鳥ほど来にくくなる(`feeder_chain`)。
/// **省略すれば 1.0 倍**なので、餌台を置いていない庭の確率は今までと変わらない。
Arrival arrivalProbability({
  required String birdId,
  required FoodWeb web,
  required String biomeId,
  required Map<String, dynamic> birdsData,
  List<String> raptors = const [],
  Map<String, Centrality>? centralities,
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
  var rarityFactor = (1.0 - rarity * 0.85) * 0.9;
  // 中心性があれば**上書き**する(足すのではない)。
  double? centralityUsed;
  final fromCentrality =
      centralityRarityFactor(bird['scientific'] as String?, centralities);
  if (fromCentrality != null) {
    rarityFactor = fromCentrality;
    centralityUsed = centralities![
            (bird['scientific'] as String).toUpperCase()]!
        .value;
  }

  // 恐怖の景観。猛禽が居なければ 1.0 で、式は今まで通り。
  final wary =
      waryArrivalMultiplier(pyFloat(bird['wariness']) ?? 0.5, raptors);

  var prob = tFit * biomeBonus * foodFactor * rarityFactor * 0.5 * wary;
  prob = prob.clamp(0.0, 1.0);

  return Arrival(
    probability: prob,
    tempFit: tFit,
    biomeBonus: biomeBonus,
    foodScore: foodScore,
    foodFactor: foodFactor,
    rarityFactor: rarityFactor,
    waryFactor: wary,
    centralityUsed: centralityUsed,
  );
}

/// 1サイクルの結果。
class TurnResult {
  final Set<String> residents;
  final List<String> arrivals;
  final List<String> departures;

  /// このサイクルで使った食物網。「なぜ来たか」を組むのに要る
  /// (撹乱で植生が変わるので、**サイクルごとに違う**)。
  final FoodWeb web;
  const TurnResult(this.residents, this.arrivals, this.departures, this.web);
}

/// 1サイクル進める。`engine.run_turn` と同じ手順・同じ順序。
///
/// 落ち着いた庭に保つための上限がある(自然観察としても、画面の静けさとしても):
///   滞在は最大4種 / 1サイクルの新規到着は最大1種。
///
/// 順序が結果を左右するので変えないこと:
///   ① 先に退去判定(滞在中の各鳥、退去率 = 0.3 - 0.25 × 到来確率)
///   ② 次に到着判定(候補をシャッフルしてから、上限まで)
TurnResult runTurn({
  required List<String> plantedPlants,
  required String biomeId,
  required int month,
  required Set<String> residents,
  required Random rng,
  required Map<String, dynamic> plantsData,
  required Map<String, dynamic> insectsData,
  required Map<String, dynamic> birdsData,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> seasonOffset,
  List<String> placedFeatures = const [],
  Map<String, Centrality>? centralities,
  /// 「今日の庭アイテム」の到来加点。省略すると一切呼ばれない。
  double Function(String)? arrivalBonusFn,
  /// 同・退去率の減算。0 なら一切効かない。
  double departureBonus = 0.0,
  /// リス返し(`garden_items`)が効いている間は、開放型でもリスが餌台に届かない。
  bool baffled = false,
  int maxResidents = 4,
  int maxArrivalsPerTurn = 1,
}) {
  // 餌台の連鎖。開放型を置くとリスが来て、リスがタカを呼ぶ。
  // 空なら猛禽は居らず、確率は今まで通り。
  final raptors =
      resolveFeeders(placedFeatures, plantedPlants, baffled: baffled).raptors;

  final web = buildFoodWeb(
    plantedPlants: plantedPlants,
    biomeId: biomeId,
    month: month,
    plantsData: plantsData,
    insectsData: insectsData,
    birdsData: birdsData,
    biomes: biomes,
    seasonOffset: seasonOffset,
  );

  final next = Set<String>.from(residents);
  final arrivals = <String>[];
  final departures = <String>[];

  for (final bid in residents.toList()) {
    final p = arrivalProbability(
            birdId: bid,
            web: web,
            biomeId: biomeId,
            birdsData: birdsData,
            raptors: raptors,
            centralities: centralities)
        .probability;
    // 退去はアイテムの**到来加点を受けない**(Python も加点前の p を使う)。
    var depRate = 0.3 - 0.25 * p;
    if (departureBonus != 0.0) {
      depRate = max(0.02, depRate - departureBonus);
    }
    if (rng.nextDouble() < depRate) {
      next.remove(bid);
      departures.add(bid);
    }
  }

  final candidates = <MapEntry<String, double>>[];
  for (final bid in birdsData.keys) {
    if (next.contains(bid)) continue;
    var p = arrivalProbability(
            birdId: bid,
            web: web,
            biomeId: biomeId,
            birdsData: birdsData,
            raptors: raptors,
            centralities: centralities)
        .probability;
    // 餌台の加点。**到来にだけ効く**(上の退去判定は加点前の p を使う)。
    // 置いていなければ 0 なので、今までの庭は1ビットも変わらない。
    p = min(1.0, p + feederArrivalBonus(placedFeatures, birdsData[bid]));
    if (arrivalBonusFn != null) {
      p = min(1.0, p + arrivalBonusFn(bid));
    }
    if (p > 0) candidates.add(MapEntry(bid, p));
  }
  candidates.shuffle(rng);

  for (final c in candidates) {
    if (arrivals.length >= maxArrivalsPerTurn) break;
    if (next.length >= maxResidents) break;
    if (rng.nextDouble() < c.value) {
      next.add(c.key);
      arrivals.add(c.key);
    }
  }

  return TurnResult(next, arrivals, departures, web);
}

/// 離れていた時間から、進めるサイクル数を決める。
/// `absence_loop.estimate_tick_count` と同じ区切り。
///
/// **時間は勝手に進む。** 急かす仕掛け(スタミナ・時短課金)は入れない
/// (交渉不能の原則1「受動的である」)。留守のあいだに庭が動いているだけ。
int estimateTickCount(double hoursPassed) {
  final minutes = hoursPassed * 60;
  if (minutes < 5) return 0; // ほぼ即の再訪では何も起こさない
  if (minutes < 30) return 1; // コーヒー休憩
  if (hoursPassed < 2) return 2; // ちょっと外出
  if (hoursPassed < 6) return 3; // 半日
  if (hoursPassed < 12) return 4; // 仕事前 → 仕事後
  if (hoursPassed < 24) return 5; // 1日
  return 6; // 上限
}

/// 留守のあいだの出来事。
class AbsenceResult {
  final Set<String> residents;
  final List<String> arrivals;
  final List<String> departures;
  final int ticks;

  /// 撹乱で倒れた植物(純減。自動では植え直さない)。
  final List<String> lostPlants;

  /// 起きた撹乱。
  final List<Disturbance> disturbances;

  /// 撹乱を反映した最終的な植生。
  final List<String> plantedFinal;

  /// 到来イベント(「なぜ来たか」の一文つき)。到着した順。
  final List<ArrivalEvent> reasons;

  const AbsenceResult(this.residents, this.arrivals, this.departures,
      this.ticks, this.lostPlants, this.disturbances, this.plantedFinal,
      [this.reasons = const []]);
}

/// 前回見たときから今までを進める。`absence_loop.evolve_state` に当たる。
///
/// 到着した鳥には「なぜ来たか」の一文が付く(`reasons`)。理由は
/// **そのサイクルの食物網**から組む — 撹乱で植生が変わるので、あとから
/// まとめて組むと嘘になる。
AbsenceResult evolveWhileAway({
  required List<String> plantedPlants,
  required String biomeId,
  required int month,
  required Set<String> residents,
  required DateTime lastSeenAt,
  required DateTime now,
  required Random rng,
  required Map<String, dynamic> plantsData,
  required Map<String, dynamic> insectsData,
  required Map<String, dynamic> birdsData,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> seasonOffset,
  List<String> placedFeatures = const [],
  Map<String, Centrality>? centralities,
  double Function(String)? arrivalBonusFn,
  double departureBonus = 0.0,
  bool baffled = false,
}) {
  final hours = now.difference(lastSeenAt).inSeconds / 3600.0;
  final ticks = hours <= 0 ? 0 : estimateTickCount(hours);
  var cur = Set<String>.from(residents);
  final arrivals = <String>[];
  final departures = <String>[];
  final planted = List<String>.from(plantedPlants);
  final lost = <String>[];
  final events = <Disturbance>[];
  final reasons = <ArrivalEvent>[];
  if (planted.isEmpty || ticks == 0) {
    return AbsenceResult(cur, arrivals, departures, 0, lost, events, planted);
  }
  // 何コマぶんを、いつの出来事として記録するか。
  // 均等割りにして、古い到来ほど古い時刻になるようにする。
  final span = now.difference(lastSeenAt);
  for (var i = 0; i < ticks; i++) {
    // 現行と同じ順序: 先に撹乱、そのあとで1サイクル。植生が変わるので、
    // **確率はコマごとに計算し直される**(runTurn が毎回 buildFoodWeb する)。
    final d = rollDisturbance(rng);
    if (d != null) {
      final removed = applyDisturbance(planted, d, plantsData, rng);
      planted.removeWhere(removed.contains);
      lost.addAll(removed);
      events.add(d);
    }
    final r = runTurn(
      plantedPlants: planted,
      biomeId: biomeId,
      month: month,
      residents: cur,
      rng: rng,
      plantsData: plantsData,
      insectsData: insectsData,
      birdsData: birdsData,
      biomes: biomes,
      seasonOffset: seasonOffset,
      placedFeatures: placedFeatures,
      centralities: centralities,
      arrivalBonusFn: arrivalBonusFn,
      departureBonus: departureBonus,
      baffled: baffled,
    );
    cur = r.residents;
    arrivals.addAll(r.arrivals);
    departures.addAll(r.departures);
    final at = isoSeconds(
        lastSeenAt.add(Duration(seconds: span.inSeconds * (i + 1) ~/ ticks)));
    for (final bid in r.arrivals) {
      reasons.add(buildReason(
        birdId: bid,
        web: r.web,
        arrivedAt: at,
        birdsData: birdsData,
        plantsData: plantsData,
        insectsData: insectsData,
      ));
    }
  }
  return AbsenceResult(
      cur, arrivals, departures, ticks, lost, events, planted, reasons);
}

/// 撹乱(嵐・落雷・伐採)。`toris_collection/disturbance.py` の移植。
///
/// 庭は痩せることがある。ただし**罰ではない** — 図鑑も会った日数も減らない
/// (交渉不能の原則2)。そして**最後の1本は必ず残す**。緑がゼロにはならない。
class Disturbance {
  final String type;
  final String icon;
  final double severity;
  const Disturbance(this.type, this.icon, this.severity);
}

/// 1サイクルあたりの発生確率。低頻度にして日常を壊さない。
const double kDisturbanceP = 0.10;

const Map<String, Disturbance> kDisturbances = {
  'storm': Disturbance('storm', '🌀', 0.50),
  'lightning': Disturbance('lightning', '⚡', 0.30),
  'logging': Disturbance('logging', '🪓', 0.60),
};

/// 種類の相対頻度。自然の撹乱が主で、人の手(伐採)はまれ。
const Map<String, double> kDisturbanceWeights = {
  'storm': 0.55,
  'lightning': 0.30,
  'logging': 0.15,
};

/// 植物ごとの倒れやすさ。データに無ければ 0.5(現行の DEFAULT_SENSITIVITY)。
const double kDefaultSensitivity = 0.5;

double plantSensitivity(String plantId, Map<String, dynamic> plantsData) {
  final v = pyFloat((plantsData[plantId] as Map?)?['sensitivity']);
  if (v == null) return kDefaultSensitivity;
  return v.clamp(0.0, 1.0);
}

/// 撹乱が起きるかを引く。起きなければ null。
Disturbance? rollDisturbance(Random rng) {
  if (rng.nextDouble() >= kDisturbanceP) return null;
  final types = kDisturbanceWeights.keys.toList();
  final weights = [for (final t in types) kDisturbanceWeights[t]!];
  final total = weights.fold<double>(0, (a, b) => a + b);
  var r = rng.nextDouble() * total;
  var acc = 0.0;
  for (var i = 0; i < types.length; i++) {
    acc += weights[i];
    if (r <= acc) return kDisturbances[types[i]];
  }
  return kDisturbances[types.last];
}

/// 撹乱で倒れる植物を返す。倒れる確率 = 強さ × その植物の倒れやすさ。
/// **全滅しそうなら1本残す**(最後の緑は失わせない)。
List<String> applyDisturbance(List<String> planted, Disturbance event,
    Map<String, dynamic> plantsData, Random rng) {
  if (planted.isEmpty) return const [];
  final removed = <String>[];
  for (final pid in planted) {
    if (rng.nextDouble() < event.severity * plantSensitivity(pid, plantsData)) {
      removed.add(pid);
    }
  }
  if (removed.isNotEmpty && removed.length >= planted.length) {
    final keep = planted[rng.nextInt(planted.length)];
    removed.removeWhere((r) => r == keep);
  }
  return removed;
}

// ─────────────────────────────────────────────────────────────
// 「どうすればあの鳥が来るか」を答える部分。`engine.py` の
// network_stats / simulate_with_added_plant / suggest_for_bird。
//
// 確率そのものを変えるわけではないが、**確率の読み方**を客に見せる部分なので、
// 推測で作らず同じ判定を移す(CEO 2026-08-16)。
// ─────────────────────────────────────────────────────────────

/// 食物網の規模。`network_stats` と同じ数え方。
class NetworkStats {
  final int plants;
  final int insects;

  /// エサ経路がある鳥の数(流入が1本でもある鳥)。
  final int birdsActive;

  /// 相互作用(辺)の数。
  final int edges;

  /// いちばん次数の大きいノード。誰も居なければ null。
  final NetworkHub? hub;
  const NetworkStats(
      this.plants, this.insects, this.birdsActive, this.edges, this.hub);
}

class NetworkHub {
  final String id;
  final String kind; // 'plant' / 'insect' / 'bird'
  final int degree;
  const NetworkHub(this.id, this.kind, this.degree);
}

/// 食物網を数える。`network_stats` と同じ。
///
/// 辺は **植物→虫 / 植物→鳥 / 虫→鳥** の3種類(`build_network` が張るのと同じ)。
/// 植物→虫を数え落とすと、辺の数もハブも変わる。
///
/// **エサ経路の無い鳥はハブの候補から外す**(Python も `in_degree == 0` の鳥を
/// skip する)。外さないと、繋がっていない鳥が最大次数になりうる。
NetworkStats networkStats(FoodWeb web) {
  final degree = <String, int>{}; // 入次数 + 出次数
  void bump(String a, String b) {
    degree[a] = (degree[a] ?? 0) + 1;
    degree[b] = (degree[b] ?? 0) + 1;
  }

  var edges = 0;
  web.insectLinks.forEach((iid, ps) {
    for (final p in ps) {
      bump(p, iid);
      edges++;
    }
  });

  var birdsActive = 0;
  final birdIn = <String, int>{};
  web.birdLinks.forEach((bid, links) {
    birdIn[bid] = links.length;
    if (links.isNotEmpty) birdsActive++;
    for (final l in links) {
      bump(l.id, bid);
      edges++;
    }
  });

  NetworkHub? hub;
  var maxDeg = 0;
  void consider(String id, String kind) {
    final deg = degree[id] ?? 0;
    if (deg > maxDeg) {
      maxDeg = deg;
      hub = NetworkHub(id, kind, deg);
    }
  }

  // Python は G.nodes の順に見る: 植物 → 虫 → 鳥(追加順)。
  // 同点なら**先に見たほう**が残るので、順序を合わせる。
  for (final p in web.plants.keys) {
    consider(p, 'plant');
  }
  for (final i in web.insects.keys) {
    consider(i, 'insect');
  }
  for (final b in web.birdLinks.keys) {
    if ((birdIn[b] ?? 0) == 0) continue; // 繋がっていない鳥は候補にしない
    consider(b, 'bird');
  }

  return NetworkStats(
      web.plants.length, web.insects.length, birdsActive, edges, hub);
}

/// 「これを植えたら、あの鳥はどれだけ来やすくなるか」。
/// `simulate_with_added_plant` と同じ — 仮に足して確率を出し直すだけ。
double simulateWithAddedPlant({
  required String targetBirdId,
  required List<String> plantedPlants,
  required String candidatePlant,
  required String biomeId,
  required int month,
  required Map<String, dynamic> plantsData,
  required Map<String, dynamic> insectsData,
  required Map<String, dynamic> birdsData,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> seasonOffset,
  Map<String, Centrality>? centralities,
}) {
  final web = buildFoodWeb(
    plantedPlants: [...plantedPlants, candidatePlant],
    biomeId: biomeId,
    month: month,
    plantsData: plantsData,
    insectsData: insectsData,
    birdsData: birdsData,
    biomes: biomes,
    seasonOffset: seasonOffset,
  );
  return arrivalProbability(
          birdId: targetBirdId,
          web: web,
          biomeId: biomeId,
          birdsData: birdsData,
          centralities: centralities)
      .probability;
}

/// 「あの鳥を呼ぶには、何が足りないか」の1件。
///
/// **文言は持たない。** 表示は画面側の仕事(Python も i18n 漏れを防ぐため
/// 構造だけを返す)。
class PlantSuggestion {
  final String plantId;

  /// 'direct' = その鳥が直接食べる / 'indirect' = 目当ての虫を成り立たせる
  final String directness;
  final String birdId;

  /// indirect のときの、目当ての虫。
  final String? insectId;
  const PlantSuggestion(this.plantId, this.directness, this.birdId,
      {this.insectId});
}

class BirdSuggestion {
  final double currentProbability;
  final bool hasFoodPath;
  final List<PlantSuggestion> suggestions;
  const BirdSuggestion(
      this.currentProbability, this.hasFoodPath, this.suggestions);
}

/// `suggest_for_bird` と同じ順序・同じ判定。
///
/// 順序が結果を左右する:
///   ① その鳥が**直接食べる植物**のうち、まだ植えていないもの
///   ② 食べる**虫を成り立たせる植物**(その虫の食草が1つも無いときだけ)
/// どちらも「この土地に植えられる」「気温に耐える」ものに限る。
/// 同じ植物は二度出さない。②は虫1匹につき**最初の1つだけ**。
BirdSuggestion? suggestForBird({
  required String targetBirdId,
  required List<String> plantedPlants,
  required String biomeId,
  required int month,
  required Map<String, dynamic> plantsData,
  required Map<String, dynamic> insectsData,
  required Map<String, dynamic> birdsData,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> seasonOffset,
  Map<String, Centrality>? centralities,
}) {
  final bird = birdsData[targetBirdId] as Map?;
  if (bird == null) return null;

  final temp = currentTemperature(biomeId, month, biomes, seasonOffset);
  final web = buildFoodWeb(
    plantedPlants: plantedPlants,
    biomeId: biomeId,
    month: month,
    plantsData: plantsData,
    insectsData: insectsData,
    birdsData: birdsData,
    biomes: biomes,
    seasonOffset: seasonOffset,
  );
  final info = arrivalProbability(
      birdId: targetBirdId,
      web: web,
      biomeId: biomeId,
      birdsData: birdsData,
      centralities: centralities);
  final hasFoodPath = (web.birdLinks[targetBirdId] ?? const []).isNotEmpty;

  final out = <PlantSuggestion>[];
  final seen = <String>{};

  bool plantable(String pid) {
    final p = plantsData[pid] as Map?;
    if (p == null) return false;
    final b = ((p['biome'] as List?) ?? const []).map((e) => '$e');
    if (!b.contains(biomeId)) return false;
    return temperatureFit(temp, p['temp_fit'] as List?) >= 0.05;
  }

  // ① 直接食べる植物
  for (final raw in ((bird['eats_plants'] as List?) ?? const [])) {
    final pid = '$raw';
    if (plantsData[pid] == null) continue;
    if (plantedPlants.contains(pid)) continue;
    if (!plantable(pid)) continue;
    if (seen.add(pid)) {
      out.add(PlantSuggestion(pid, 'direct', targetBirdId));
    }
  }

  // ② 虫を成り立たせる植物
  for (final raw in ((bird['eats_insects'] as List?) ?? const [])) {
    final iid = '$raw';
    final insect = insectsData[iid] as Map?;
    if (insect == null) continue;
    if (temperatureFit(temp, insect['temp_fit'] as List?) < 0.1) continue;
    final food = ((insect['eats_plants'] as List?) ?? const [])
        .map((e) => '$e')
        .toList();
    // その虫の食草がもう植わっているなら、足すものは無い
    if (food.any(plantedPlants.contains)) continue;
    for (final pid in food) {
      if (plantsData[pid] == null) continue;
      if (!plantable(pid)) continue;
      if (seen.add(pid)) {
        out.add(PlantSuggestion(pid, 'indirect', targetBirdId, insectId: iid));
        break; // 虫1匹につき1つだけ
      }
    }
  }

  return BirdSuggestion(info.probability, hasFoodPath, out);
}
