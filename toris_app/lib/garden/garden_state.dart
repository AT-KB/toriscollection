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

import '../i18n.dart';

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

  /// 置いた餌台。開放型はリスが届き、リスがタカを呼ぶ(`feeder_chain`)。
  /// かご型ならリスは届かない — これが唯一の駆け引き。
  final List<String> feeders = [];

  /// **今日の道具**(広告リワード。6時間だけ効く)。`garden_items`。
  ///
  /// セーブコードには入れない — 6時間で消える端末ローカルの一時状態で、
  /// 機種変更で持ち歩くものではない。Python 側の SAVE_KEYS を変えずに済む。
  core.ItemPlacement? itemPlacement;

  /// 最後にリワードを受け取った日(ISO の yyyy-MM-dd)。1日1回のゲート。
  String? lastItemClaimDay;

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

  /// **アプリを開いた日数の合計**(庭のなじみ。`core.pacing`)。
  /// 連続ではなく合計 — 休んでも減らない(原則2「罰しない」)。
  int openDays = 0;

  /// 最後に数えた日(yyyy-MM-dd)。1日1カウントのため。
  String? lastOpenDay;

  /// **鳥につけた名前**。種ごとに最大3羽(`core.nicknameSlots`)。
  ///
  /// CEO 2026-11-08「1羽あたり3名まで。名前がある鳥と無い鳥で表示を変える。
  /// 『ルリツグミが来ました』と『ルリツグミのピョンタが来ました』」。
  ///
  /// セーブコードには入れない — Python 側の SAVE_KEYS を変えずに済ませるため。
  /// そのぶん、**引っ越しコードでは名前は移らない**(端末ローカル)。
  final Map<String, List<String>> nicknames = {};

  /// いま庭に来ているのが**どの子か**(種 → 名前)。名前のない子なら入らない。
  /// 来たときに決め、帰るまで変えない。
  final Map<String, String> visitingName = {};

  /// 直前の留守のあいだに帰った子の名前(「旅立っていきました」に出すため)。
  final Map<String, String> lastDepartedName = {};

  /// いま庭に来ている鳥。
  final List<String> visiting = [];

  /// 前回ここを見た時刻。**時間は勝手に進む**ので、これが基準になる。
  DateTime? lastSeenAt;

  /// いまの儀式で既に出会えた鳥(二重に数えないため)。
  final Set<String> metThisRitual = {};

  /// **この滞在メンバーには、もう耳を澄ませた。**
  ///
  /// 同じ顔ぶれのまま儀式を繰り返すと、観察回数と会った日数を水増しできる
  /// (それがラジオの近さと群れの厚みに効く)。現行も
  /// `ritual_done_for_residents` で同じ歯止めをかけている。
  /// **減らすものは何も無い**(原則2「罰しない」)。入り口を閉じるだけ。
  Set<String>? ritualDoneFor;

  /// **いまの儀式が「出会い」として記録されるか。**
  ///
  /// 耳を澄ませること自体はいつでもできる(鳥が枝を移るのを眺められる)。
  /// ただし同じ顔ぶれに二度目からは**記録されない**
  /// (CEO 2026-08-16「リッスンしてぴょこぴょこするのはいつでもできるでいいけど、
  ///  出会い、登録にならないようにだけして」)。
  ///
  /// 現行は儀式そのものを閉じていたが、**閉じる必要は無かった**。
  /// 止めたいのは水増しであって、眺めることではない。
  bool get ritualCounts =>
      !(ritualDoneFor != null &&
          ritualDoneFor!.length == visiting.length &&
          ritualDoneFor!.containsAll(visiting));

  /// はじめての案内が、いまどの段にいるか。`kTutorialSteps` 以上で終わり。
  ///
  /// **セーブコードには入れない。** 端末ごとの案内であって、庭の状態ではない。
  int tutorialStep = 0;

  bool get tutorialRunning => !core.tutorialIsDone(tutorialStep);

  /// 留守のあいだに来た鳥が、**図鑑に新しく載ったか**。
  /// 観察回数ではなく discovered で見る(現行と同じ判定軸)。
  final Set<String> lastFirstTimers = {};

  /// 留守のあいだに来た鳥・去った鳥(画面に出すため)。
  List<String> lastArrivals = [];

  /// 直近の `catchUp` で**何コマ進んだか**。0 なら何も起きていない。
  int lastTicks = 0;
  List<String> lastDepartures = [];

  /// 留守のあいだに撹乱で倒れた植物と、その出来事。
  /// 倒れたぶんは**純減**で、自動では植え直さない(現行と同じ)。
  List<String> lastLostPlants = [];
  /// 起きた撹乱そのもの(種類・アイコン・強さ)。**アイコンだけにしない** —
  /// 嵐/落雷/伐採で言い方が変わるので、種類が要る。
  List<core.Disturbance> lastDisturbances = [];

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

  /// いまの到来確率の内訳。「なぜ来たか」を出すのに使う。
  core.Arrival arrivalOf(String birdId) => core.arrivalProbability(
        birdId: birdId,
        web: web,
        biomeId: biomeId,
        birdsData: data.birds,
        raptors: chain.raptors,
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

  /// 餌台を置く / 片づける。餌台は1つだけ(開放型とかご型は同時に置けない —
  /// 同時に置けると開放型が常に勝ってしまい、選ぶ意味が消える)。
  void setFeeder(String? feederId) {
    feeders.clear();
    if (feederId != null) feeders.add(feederId);
  }

  /// いまの餌台から解けた連鎖(来ている動物と猛禽)。
  /// **リス返しが効いている間はリスが来ない**ので、
  /// 庭の絵も画面の文もそれに従う(見た目と中身をずらさない)。
  core.FeederChain get chain => core.resolveFeeders(feeders, planted,
      baffled: core.isBaffleActive(itemPlacement));

  /// **留守のあいだのぶんを進める。** 画面を開いた時に一度だけ呼ぶ。
  ///
  /// 現行の `absence_loop.evolve_state` に当たる。押して進める仕掛けは置かない
  /// (交渉不能の原則1「受動的である」)。5分未満の再訪では何も起きない。
  void catchUp(Random rng) {
    final now = DateTime.now();
    final last = lastSeenAt;
    // 庭のなじみ。**この回の到来にも効く**ように、進める前に数える。
    final todayKey = '${now.year}-${now.month.toString().padLeft(2, '0')}-'
        '${now.day.toString().padLeft(2, '0')}';
    if (lastOpenDay != todayKey) {
      lastOpenDay = todayKey;
      openDays += 1;
    }
    lastTicks = 0;
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
        placedFeatures: feeders,
        // 今日の道具。置いていなければ全部「効かない」値になるので、
        // 何も置いていない庭の確率は今までと1ビットも変わらない。
        arrivalBonusFn: core.makeArrivalBonusFn(
            itemPlacement, biomeId, data.birds),
        departureBonus: core.itemDepartureBonus(itemPlacement),
        baffled: core.isBaffleActive(itemPlacement),
        // ── ペース(CEO 2026-11-07。`core.pacing`)──
        // 3時間で1コマ・実時間に比例。全体と珍しさ・庭のなじみ・鳥の慣れ。
        tickCountFn: core.pacedTickCount,
        arrivalScaleFn: core.makeArrivalScaleFn(data.birds,
            openDays: openDays, meets: observed),
      );
      lastTicks = r.ticks;
      // 帰った子の名前を控えてから外す。来た鳥は、どの子が来たかを決める。
      lastDepartedName.clear();
      for (final b in r.departures) {
        final n = visitingName.remove(b);
        if (n != null) lastDepartedName[b] = n;
      }
      for (final b in r.arrivals) {
        visitingName.remove(b);
        final n = pickVisitor(b, rng);
        if (n != null) visitingName[b] = n;
      }
      visiting
        ..clear()
        ..addAll(r.residents);
      visitingName.removeWhere((b, _) => !visiting.contains(b));
      lastArrivals = r.arrivals;
      lastDepartures = r.departures;
      // 撹乱で倒れた植物を反映する。庭は痩せるが、記録は減らさない。
      lastLostPlants = r.lostPlants;
      lastDisturbances = r.disturbances;
      planted
        ..clear()
        ..addAll(r.plantedFinal);
      // 来た鳥は図鑑に載る(名前まで)。**近くで会うのは儀式を経てから。**
      // 「はじめまして」は**図鑑への新規登録かどうか**で見る(現行と同じ)。
      lastFirstTimers
        ..clear()
        ..addAll(r.arrivals.where((b) => !discovered.contains(b)));
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
    // **進んだときだけ時計を進める。**
    // 無条件に now を書くと、5分未満で開き直すたびに経過時間が消え、
    // 数分おきに開く人の庭には鳥が永遠に来なくなる(2026-08-18 に発覚)。
    // 初回(last == null)は基準が要るので必ず置く。
    // 3時間で1コマなので、**端数を持ち越す**(`core.pacedLastSeen`)。
    if (last == null) {
      lastSeenAt = now;
    } else if (lastTicks > 0) {
      lastSeenAt = core.pacedLastSeen(last, now, lastTicks);
    }
  }

  // ── 保存 ──
  // セーブコードと同じキー名を使う(`toris_core` の saveKeys)。
  // 将来 Streamlit 版と行き来できるようにしておく。
  Map<String, dynamic> toState() => {
        'biome': biomeId,
        'planted': planted,
        'feeders': feeders,
        'residents': visiting.toSet(),
        'discovered': discovered,
        // Python 側は {count: n} の形。読む側は素の数も受けるが、書く形は揃える。
        'observed': {
          for (final e in observed.entries) e.key: {'count': e.value}
        },
        // Python 側 `_mark_met_today` と同じ形 {days, last}。
        // last を持たないと、同じ日にアプリを開き直すたびに二重に数えてしまう。
        'bird_days': {
          for (final e in birdDays.entries)
            e.key: {'days': e.value, 'last': lastMetDay[e.key] ?? ''}
        },
        'saved_at': core.isoSeconds(lastSeenAt ?? DateTime.now()),
      };

  void applyState(Map<String, dynamic> s) {
    biomeId = (s['biome'] as String?) ?? biomeId;
    planted
      ..clear()
      ..addAll(((s['planted'] as List?) ?? const []).map((e) => '$e'));
    feeders
      ..clear()
      ..addAll(((s['feeders'] as List?) ?? const []).map((e) => '$e'));
    visiting
      ..clear()
      ..addAll(((s['residents'] as Iterable?) ?? const []).map((e) => '$e'));

    // **図鑑と会った日数は必ず戻す。** 保存はしていたのに読み戻していなかったため、
    // アプリを閉じるたびに図鑑が白紙に戻っていた(交渉不能の原則2「罰しない」に反する)。
    discovered
      ..clear()
      ..addAll(((s['discovered'] as Iterable?) ?? const []).map((e) => '$e'));
    // ⚠️ **`eco_log` は読まない**(2026-09-22 に「なぜ来たか」を製品から
    // 外した)。古いセーブコードには `eco_log` が入っているが、
    // `save_code.dart` の `saveKeys` には残してあるので**読めて落ちない**。
    // 単に使わないだけ。SAVE_KEYS を触ると Python 版との互換が崩れる。
    birdDays.clear();
    lastMetDay.clear();
    final days = s['bird_days'];
    if (days is Map) {
      days.forEach((k, v) {
        // Python は {days, last}。素の数で書かれた古い保存も読めるようにする。
        if (v is Map) {
          birdDays['$k'] = (v['days'] as num?)?.toInt() ?? 0;
          final l = v['last'];
          if (l is String && l.isNotEmpty) lastMetDay['$k'] = l;
        } else {
          birdDays['$k'] = (v as num?)?.toInt() ?? 0;
        }
      });
    }
    // 前回見た時刻。セーブコードの saved_at をそのまま使う
    // (現行も「離れていた時間」をこれで測っている)。
    // 読めなければ静かに null( と同じ)。
    lastSeenAt = core.parseIso(s['saved_at']) ?? lastSeenAt;
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
  static const _tutorialKey = 'toris_tutorial_step';
  static const _itemKey = 'toris_garden_item';
  static const _claimKey = 'toris_item_claim_day';
  static const _openDaysKey = 'toris_open_days';
  static const _openDayKey = 'toris_last_open_day';
  static const _nicknamesKey = 'toris_nicknames';
  static const _visitingNameKey = 'toris_visiting_name';

  /// その種に、あといくつ名前をつけられるか。
  int freeNameSlots(String birdId) =>
      core.nicknameSlots(observed[birdId] ?? 0) -
      (nicknames[birdId]?.length ?? 0);

  /// 名前をつけられるか(枠が1つ以上空いている)。
  bool canNickname(String birdId) => freeNameSlots(birdId) > 0;

  /// 来た子を決める。名前のある子それぞれと「名前のない子」を同じ重みで引く
  /// (名前が2つなら 1/3 ずつ)。名前のない子なら null。
  String? pickVisitor(String birdId, Random rng) {
    final names = nicknames[birdId] ?? const <String>[];
    if (names.isEmpty) return null;
    final i = rng.nextInt(names.length + 1);
    return i < names.length ? names[i] : null;
  }

  /// 画面に出す名前。名前のある子なら「ルリツグミのピョンタ」、なければ種名。
  String labelFor(String birdId) {
    final species = nameOf(data.birds[birdId], birdId);
    final n = visitingName[birdId] ?? lastDepartedName[birdId];
    return n == null ? species : individualLabel(species, n);
  }

  /// 名前を足す。枠が無ければ何もしない。12文字まで。
  void addNickname(String birdId, String name) {
    final n = name.trim();
    if (n.isEmpty || !canNickname(birdId)) return;
    (nicknames[birdId] ??= []).add(n.length > 12 ? n.substring(0, 12) : n);
  }

  /// 名前を変える / 外す(空なら外す)。
  void renameNickname(String birdId, String oldName, String name) {
    final list = nicknames[birdId];
    if (list == null) return;
    final i = list.indexOf(oldName);
    if (i < 0) return;
    final n = name.trim();
    if (n.isEmpty) {
      list.removeAt(i);
      if (list.isEmpty) nicknames.remove(birdId);
      if (visitingName[birdId] == oldName) visitingName.remove(birdId);
    } else {
      final v = n.length > 12 ? n.substring(0, 12) : n;
      list[i] = v;
      if (visitingName[birdId] == oldName) visitingName[birdId] = v;
    }
  }

  Future<void> save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_key, core.encodeCurrentState(toState()));
    await p.setInt(_tutorialKey, tutorialStep);
    final it = itemPlacement;
    if (it == null) {
      await p.remove(_itemKey);
    } else {
      await p.setString(_itemKey,
          '${it.itemId}|${core.isoSeconds(it.placedAt)}');
    }
    final d = lastItemClaimDay;
    if (d == null) {
      await p.remove(_claimKey);
    } else {
      await p.setString(_claimKey, d);
    }
    await p.setInt(_openDaysKey, openDays);
    final od = lastOpenDay;
    if (od != null) await p.setString(_openDayKey, od);
    await p.setString(_nicknamesKey, jsonEncode(nicknames));
    await p.setString(_visitingNameKey, jsonEncode(visitingName));
  }

  Future<void> restore() async {
    final p = await SharedPreferences.getInstance();
    tutorialStep = p.getInt(_tutorialKey) ?? 0;
    lastItemClaimDay = p.getString(_claimKey);
    openDays = p.getInt(_openDaysKey) ?? 0;
    lastOpenDay = p.getString(_openDayKey);
    try {
      final raw = p.getString(_nicknamesKey);
      if (raw != null) {
        nicknames.clear();
        (jsonDecode(raw) as Map).forEach((k, v) {
          // 2.0.7 の開発中は1種1つ(文字列)だった。どちらの形も読む。
          final list = v is List ? [for (final x in v) '$x'] : ['$v'];
          if (list.isNotEmpty) nicknames['$k'] = list.take(core.kMaxNicknames).toList();
        });
      }
      final vn = p.getString(_visitingNameKey);
      if (vn != null) {
        visitingName
          ..clear()
          ..addAll((jsonDecode(vn) as Map).map((k, v) => MapEntry('$k', '$v')));
      }
    } catch (_) {
      // 読めなければ名前なしで続ける(落ちない)。
    }
    final raw = p.getString(_itemKey);
    if (raw != null) {
      final i = raw.indexOf('|');
      final at = i < 0 ? null : DateTime.tryParse(raw.substring(i + 1));
      // 期限切れは読んだ時点で捨てる(切れたものを持ち歩かない)。
      if (at != null) {
        final placed = core.placeItem(raw.substring(0, i), now: at);
        if (core.itemIsActive(placed)) itemPlacement = placed;
      }
    }
    final code = p.getString(_key);
    if (code == null) return;
    final s = core.decodeSave(code);
    if (s != null) applyState(s);
    // **前の版から使っている人の通った日数を埋める。** 数え始めたのは 2.0.7 からなので、
    // そのままだと何週間も使ってきた人が「1日目」から始まる。会った日数(鳥ごと)の
    // 最大は、少なくともその日数は開いていた証拠になる。増やすだけで減らさない。
    if (birdDays.isNotEmpty) {
      final most = birdDays.values.reduce((a, b) => a > b ? a : b);
      if (most > openDays) openDays = most;
    }
    // **既に庭がある人には案内しない。** セーブコードで移してきた人や、
    // 前の版から使っている人に、いまさら「土地を選びましょう」は失礼。
    if (planted.isNotEmpty || discovered.isNotEmpty) {
      tutorialStep = core.kTutorialSteps;
    }
  }
}
