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
  const GardenData(
      this.birds, this.plants, this.insects, this.biomes, this.seasonOffset);

  static Future<GardenData> load() async {
    Future<Map<String, dynamic>> j(String n) async =>
        (jsonDecode(await rootBundle.loadString('assets/data/$n.json')) as Map)
            .cast<String, dynamic>();
    return GardenData(await j('birds'), await j('plants'), await j('insects'),
        await j('biomes'), await j('season_offset'));
  }
}

/// 庭。植えたものと、会った記録を持つ。
class Garden {
  final GardenData data;

  String biomeId;
  final List<String> planted = [];

  /// 鳥ID → 会った回数。よく会うほど近くで鳴くようになる(ラジオが読む)。
  final Map<String, int> observed = {};

  /// いま庭に来ている鳥。
  final List<String> visiting = [];

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

  bool plant(String plantId) {
    if (planted.length >= maxPlants || planted.contains(plantId)) return false;
    planted.add(plantId);
    return true;
  }

  void remove(String plantId) => planted.remove(plantId);

  /// 見に行く。来ている鳥を数え直し、会った回数を増やす。
  ///
  /// 現行の run_turn に当たる。滞在は最大4種(落ち着いた庭に保つため)。
  /// **来なかったことは罰ではない**ので、記録は減らさない。
  List<String> lookAtGarden(Random rng) {
    final w = web;
    final newcomers = <String>[];
    for (final bid in data.birds.keys) {
      if (visiting.contains(bid)) continue;
      if (visiting.length >= 4) break;
      final a = core.arrivalProbability(
          birdId: bid, web: w, biomeId: biomeId, birdsData: data.birds);
      if (a.probability > 0 && rng.nextDouble() < a.probability) {
        visiting.add(bid);
        newcomers.add(bid);
      }
    }
    // 会った回数は、いま来ている鳥ぶんだけ増える(会いに行くほど馴染む)
    for (final bid in visiting) {
      observed[bid] = (observed[bid] ?? 0) + 1;
    }
    return newcomers;
  }

  // ── 保存 ──
  // セーブコードと同じキー名を使う(`toris_core` の saveKeys)。
  // 将来 Streamlit 版と行き来できるようにしておく。
  Map<String, dynamic> toState() => {
        'biome': biomeId,
        'planted': planted,
        'residents': visiting.toSet(),
        'discovered': observed.keys.toSet(),
        'observed': {for (final e in observed.entries) e.key: e.value},
      };

  void applyState(Map<String, dynamic> s) {
    biomeId = (s['biome'] as String?) ?? biomeId;
    planted
      ..clear()
      ..addAll(((s['planted'] as List?) ?? const []).map((e) => '$e'));
    visiting
      ..clear()
      ..addAll(((s['residents'] as Iterable?) ?? const []).map((e) => '$e'));
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
