/// 庭の状態。植えたもの、来ている鳥、会った回数。
///
/// この輪がこの商品の背骨:
///   **植生をつくる → 虫が来る → その虫を目当てに鳥が来る →
///     会うほど馴染んで近くで鳴く → その声で朝を迎える**
///
/// 交渉不能の原則に従う:
///  1. **受動的**。時間を早送りする仕掛けは作らない。
///  2. **罰しない**。庭が痩せても、会った記録(図鑑・回数)は減らない。
library;

import 'dart:convert';
import 'dart:math';

import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:toris_core/toris_core.dart' as core;

class GardenData {
  final Map<String, dynamic> birds;
  final Map<String, dynamic> plants;
  final Map<String, dynamic> insects;
  final Map<String, dynamic> biomes;
  final Map<String, dynamic> seasonOffset;

  /// 図鑑の「こわいもの」。GloBI の実際の捕食記録。
  final Map<String, dynamic> predators;

  const GardenData(this.birds, this.plants, this.insects, this.biomes,
      this.seasonOffset, this.predators);

  static Future<GardenData> load() async {
    Future<Map<String, dynamic>> j(String n) async =>
        (jsonDecode(await rootBundle.loadString('assets/data/$n.json')) as Map)
            .cast<String, dynamic>();
    return GardenData(await j('birds'), await j('plants'), await j('insects'),
        await j('biomes'), await j('season_offset'), await j('predators'));
  }
}

/// 庭。植えたものと、会った記録を持つ。
class Garden {
  final GardenData data;

  String biomeId;
  final List<String> planted = [];

  /// **近くで出会った回数**(儀式で手前の枝まで来た回数)。
  /// これがラジオの近さ・群れの厚みに効く(現行の観察回数)。
  /// 来訪しただけでは増えない — 会いに行くから馴染む。
  final Map<String, int> observed = {};

  /// **来訪済みの鳥**。図鑑に名前が載る(絵はまだ出ない)。
  final Set<String> discovered = {};

  /// **会った日数**(1日1カウントの累計)。節目でバッジが付く。
  final Map<String, int> birdDays = {};

  /// 鳥ごとに「最後に数えた日」。**1日1カウントは鳥ごと**
  /// (現行の _mark_met_today は鳥ごとに last を持つ。アプリ全体で1回にすると、
  ///  同じ日に後から来た鳥が数えられない)。
  final Map<String, String> lastMetDay = {};

  /// いま庭に来ている鳥。
  final List<String> visiting = [];

  /// 前回ここを見た時刻。**時間は勝手に進む**ので、これが基準になる。
  DateTime? lastSeenAt;

  /// いまの儀式で既に出会えた鳥(二重に数えないため)。
  final Set<String> metThisRitual = {};

  /// 留守のあいだに来た鳥・去った鳥(画面に出すため)。
  List<String> lastArrivals = [];
  List<String> lastDepartures = [];

  /// 留守のあいだに撹乱で倒れた植物と、その出来事。
  /// 倒れたぶんは**純減**で、自動では植え直さない(現行と同じ)。
  List<String> lastLostPlants = [];
  List<String> lastDisturbances = [];

  Garden(this.data, {this.biomeId = 'kyoto'});

  int get maxPlants =>
      (data.biomes[biomeId]?['max_plants'] as num?)?.toInt() ?? 4;

  /// いまの月。時間は実時間で進む(急かさない)。
  int get month => DateTime.now().month;

  core.FoodWeb get web => core.buildFoodWeb(
        plantedPlants: planted,
        biomeId: biomeId,
        month: month,
        plantsData: data.plants,
        insectsData: data.insects,
        birdsData: data.birds,
        biomes: data.biomes,
        seasonOffset: data.seasonOffset,
      );

  /// この土地に植えられる植物。
  List<String> get availablePlants {
    final out = <String>[];
    data.plants.forEach((id, p) {
      final b = ((p['biome'] as List?) ?? const []).map((e) => '$e');
      if (b.contains(biomeId)) out.add(id);
    });
    out.sort();
    return out;
  }

  /// 土地を変える。植えたものはその土地に合わないので一度手放す
  /// (現行も土地ごとに植えられる植物が違う)。
  void setBiome(String id) {
    if (biomeId == id) return;
    biomeId = id;
    planted.removeWhere((p) {
      final b = ((data.plants[p]?['biome'] as List?) ?? const [])
          .map((e) => '$e');
      return !b.contains(id);
    });
  }

  /// 会った回数からの「近さ」。`radio.py` の _obs_to_depth と同じ区切り。
  String depthOf(String birdId) {
    final c = observed[birdId] ?? 0;
    if (c >= 6) return 'b1';
    if (c >= 3) return 'b2';
    return 'b3';
  }

  /// ドット絵。無い種は null(丸で代用する)。
  String? spriteFor(String birdId) =>
      spriteIds.contains(birdId) ? 'assets/sprites/$birdId.png' : null;

  /// 図鑑用の大きい絵。無ければ null。
  String? detailSpriteFor(String birdId) => detailIds.contains(birdId)
      ? 'assets/sprites/${birdId}_detail.png'
      : null;

  /// 詳細絵がある種ID。
  static Set<String> detailIds = {};

  /// 同梱しているドット絵の種ID。起動時に一度だけ読む。
  static Set<String> spriteIds = {};

  /// アプリに入っているドット絵を数える(AssetManifest から)。
  static Future<void> loadSpriteIds() async {
    try {
      final m = await AssetManifest.loadFromAssetBundle(rootBundle);
      final all = m.listAssets().where(
          (k) => k.startsWith('assets/sprites/') && k.endsWith('.png'));
      spriteIds = {
        for (final k in all)
          if (!k.endsWith('_detail.png'))
            k.substring('assets/sprites/'.length, k.length - 4)
      };
      detailIds = {
        for (final k in all)
          if (k.endsWith('_detail.png'))
            k.substring('assets/sprites/'.length, k.length - '_detail.png'.length)
      };
    } catch (_) {}
  }

  bool plant(String plantId) {
    if (planted.length >= maxPlants || planted.contains(plantId)) return false;
    planted.add(plantId);
    return true;
  }

  void remove(String plantId) => planted.remove(plantId);

  /// **留守のあいだのぶんを進める。** 画面を開いた時に一度だけ呼ぶ。
  ///
  /// 現行の `absence_loop.evolve_state` に当たる。押して進める仕掛けは置かない
  /// (交渉不能の原則1「受動的である」)。5分未満の再訪では何も起きない。
  void catchUp(Random rng) {
    final now = DateTime.now();
    final last = lastSeenAt;
    lastArrivals = [];
    lastDepartures = [];
    if (last != null && planted.isNotEmpty) {
      final r = core.evolveWhileAway(
        plantedPlants: planted,
        biomeId: biomeId,
        month: month,
        residents: visiting.toSet(),
        lastSeenAt: last,
        now: now,
        rng: rng,
        plantsData: data.plants,
        insectsData: data.insects,
        birdsData: data.birds,
        biomes: data.biomes,
        seasonOffset: data.seasonOffset,
      );
      visiting
        ..clear()
        ..addAll(r.residents);
      lastArrivals = r.arrivals;
      lastDepartures = r.departures;
      // 撹乱で倒れた植物を反映する。庭は痩せるが、記録は減らさない。
      lastLostPlants = r.lostPlants;
      lastDisturbances = [for (final d in r.disturbances) d.icon];
      planted
        ..clear()
        ..addAll(r.plantedFinal);
      // 来た鳥は図鑑に載る(名前まで)。**近くで会うのは儀式を経てから。**
      discovered.addAll(r.arrivals);
    }
    // 会った日数は**鳥ごとに**1日1カウント。いま庭にいる鳥ぶんだけ増える。
    final today = '${now.year}-${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}';
    for (final b in visiting) {
      if (lastMetDay[b] != today) {
        lastMetDay[b] = today;
        birdDays[b] = (birdDays[b] ?? 0) + 1;
      }
    }
    lastSeenAt = now;
  }

  // ── 保存 ──
  // セーブコードと同じキー名を使う(`toris_core` の saveKeys)。
  // 将来 Streamlit 版と行き来できるようにしておく。
  Map<String, dynamic> toState() => {
        'biome': biomeId,
        'planted': planted,
        'residents': visiting.toSet(),
        'discovered': discovered,
        'observed': {for (final e in observed.entries) e.key: e.value},
        'bird_days': {for (final e in birdDays.entries) e.key: e.value},
        'saved_at': core.isoSeconds(lastSeenAt ?? DateTime.now()),
      };

  void applyState(Map<String, dynamic> s) {
    biomeId = (s['biome'] as String?) ?? biomeId;
    planted
      ..clear()
      ..addAll(((s['planted'] as List?) ?? const []).map((e) => '$e'));
    visiting
      ..clear()
      ..addAll(((s['residents'] as Iterable?) ?? const []).map((e) => '$e'));
    // 前回見た時刻。セーブコードの saved_at をそのまま使う
    // (現行も「離れていた時間」をこれで測っている)。
    final at = s['saved_at'];
    if (at is String) lastSeenAt = DateTime.tryParse(at);
    observed.clear();
    final obs = s['observed'];
    if (obs is Map) {
      obs.forEach((k, v) {
        final n = v is Map ? v['count'] : v;
        observed['$k'] = (n as num?)?.toInt() ?? 0;
      });
    }
  }

  static const _key = 'toris_save';

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_key, core.encodeCurrentState(toState()));
  }

  Future<void> restore() async {
    final p = await SharedPreferences.getInstance();
    final code = p.getString(_key);
    if (code == null) return;
    final s = core.decodeSave(code);
    if (s != null) applyState(s);
  }
}
