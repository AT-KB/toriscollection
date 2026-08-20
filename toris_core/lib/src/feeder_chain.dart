
/// 餌台 → リス → タカ →(警戒心の強い鳥を抑制)の連鎖。`feeder_chain.py` の移植。
///
/// アメリカ裏庭バードウォッチングの「餌台を置き、リスや猛禽との駆け引きで
/// 狙った鳥を呼ぶ」を、恣意的なルールではなく **GloBI の相互作用の向きだけ**で
/// 表す(交渉不能の原則4「生態に誠実」)。
///
///     開放型の餌台(種) --食べる--> リス --食べられる--> タカ --狙う--> 警戒心の強い鳥
///
/// **かご型の餌台にすればリスは届かない。** リスが来なければタカも来ず、
/// 臆病な鳥が来られる。これが唯一の駆け引き。餌台は罰ではなく、選択。
///
/// ⚠️ Python 側ではこのモジュールは**書かれたが一度も配線されていない**
/// (app.py も engine.py も import していない)。移植にあたり、
/// 計算そのものは Python と機械的に突き合わせてあるが、
/// **到来確率への接続は Flutter 側で新たに入れたもの**(2026-08-14 CEO 承認)。
library;
import 'dart:math';

/// 庭に置く餌台。`largeAccess` = 大型動物(リス)が中身に届くか。
/// 置ける餌台。
///
/// `draws` は**どちらの気質の鳥を強く引くか**。'bold' は警戒心の低い鳥、
/// 'shy' は警戒心の高い鳥。`bonus_max` はその効きの上限(pp)。
///
/// ## なぜ気質で分けるのか(2026-08-20 CEO承認)
/// この仕組みは「餌台を置き、**リスや猛禽との駆け引き**で狙った鳥を呼ぶ」
/// ためのものなのに、**代償(リス→鷹→抑制)だけが配線されていて、利点が
/// 一度も入っていなかった。** 実測すると:
///
///   開放型   空の庭 11% / 平均 1.74羽  ← 一方的に損
///   かご型   空の庭  5% / 平均 2.15羽  ← 「置かない」と1ビットも同じ
///
/// 選択肢が「無意味」か「自傷」の二択で、原則2「罰しない」に触れていた。
///
/// ## 量ではなく**顔ぶれ**で分ける
/// 最初は加点の大小で差をつけようとしたが(開放+3/かご+2 など)、鷹が来ない
/// ぶんかご型が常に勝ち、「安全な方が正解」で駆け引きにならなかった。
///
///   開放型 — 開けっぴろげで食べやすい。**大胆な鳥**が寄る。
///            ただしリスが来て鷹を呼ぶので、**臆病な鳥は二重に遠のく**。
///   かご型 — 囲われていて安全。**臆病な鳥**が安心して来る。鷹も来ない。
///
/// 実測(同じ庭。平均はほぼ並ぶ = どちらが得かではなく誰が来るかの差):
///   開放型 2.75羽  robin.30 / cardinal.35 / jay.35 / dove.35
///   かご型 2.78羽  finch.50 / thrasher.60 / wren.45 / waxwing.50
///   置かない 2.25羽
///
/// ⚠️ 体格では分けない。`data.py` に体長・体重が無く、体格表をでっち上げる
/// のは恣意的な指標になる(原則4。CEO 2026-08-20「今更体長のラベリングは
/// 違うな」)。**wariness は元からあるデータ。**
const Map<String, Map<String, Object>> kFeeders = {
  'feeder_open': {
    'english': 'Open feeder',
    'offers': 'seed',
    'large_access': true,
    'draws': 'bold',
    'bonus_max': 0.20,
  },
  'feeder_cage': {
    'english': 'Caged feeder',
    'offers': 'seed',
    'large_access': false,
    'draws': 'shy',
    'bonus_max': 0.20,
  },
};

/// 気質の効きが立ち上がる下限。ここを引いてから掛けるので、逆側の気質の鳥は
/// ほとんど加点されない(0.2 未満は 0)。
const double kLeanFloor = 0.2;

/// 餌台が、この鳥の到来確率に足す値(pp)。
///
/// 種・実を食べる鳥(`eats_plants` が空でない)にだけ効く。虫だけを食べる鳥に
/// 種を撒いても意味が無いので加点しない(原則4)。
/// 置いていなければ 0.0 — **今までと1ビットも変わらない。**
///
/// ⚠️ **到来にだけ効く。退去には効かない**(garden_items の加点と同じ扱い)。
double feederArrivalBonus(List<String> placedFeatures, Object? bird) {
  if (placedFeatures.isEmpty) return 0.0;
  final m = (bird as Map?) ?? const {};
  if (((m['eats_plants'] as List?) ?? const []).isEmpty) return 0.0;
  var w = (m['wariness'] as num?)?.toDouble() ?? 0.5;
  w = w.clamp(0.0, 1.0);
  var best = 0.0;
  for (final f in placedFeatures) {
    final meta = kFeeders[f];
    if (meta == null) continue;
    final lean = meta['draws'] == 'bold' ? 1.0 - w : w;
    final v = (meta['bonus_max'] as num).toDouble() * max(0.0, lean - kLeanFloor);
    if (v > best) best = v;
  }
  return best;
}

/// 種子を供給する植物(GloBI: これらを様々な動物が食べる)。
const Set<String> kSeedPlants = {'sunflower'};

/// 堅果を供給する植物。
const Set<String> kAcornPlants = {'white_oak'};

/// 動物。`eats` = 何を食べる / `eatenBy` = 何に食べられる(GloBI)。
const Map<String, Map<String, Object>> kAnimals = {
  'gray_squirrel': {
    'english': 'Eastern Gray Squirrel',
    'scientific': 'Sciurus carolinensis',
    'role': 'mammal',
    'eats': ['seed', 'acorn'],
    'needs_large_access': true, // かご型の餌台からは食べられない
    'eaten_by': ['cooper_hawk'],
  },
};

/// 猛禽(GloBI: preysOn)。
const Map<String, Map<String, Object>> kRaptors = {
  'cooper_hawk': {
    'english': "Cooper's Hawk",
    'scientific': 'Accipiter cooperii',
    'role': 'raptor',
    'preys_on_animals': ['gray_squirrel'],
    // 猛禽が居るとき、警戒心に効く最大係数(wariness=1 で到来を 70% 抑制)
    'suppression': 0.7,
  },
};

/// 庭にある「動物向けの食べ物」の種別を返す。
///
/// `large_access` は、大型動物が届く供給(開放型の餌台・地面の堅果)が
/// 1つでもあるときに入る。
Set<String> availableFoods(
    List<String> placedFeatures, List<String> plantedPlants) {
  final foods = <String>{};
  var large = false;
  for (final f in placedFeatures) {
    final meta = kFeeders[f];
    if (meta == null) continue;
    foods.add(meta['offers'] as String);
    if (meta['large_access'] == true) large = true;
  }
  if (plantedPlants.any(kSeedPlants.contains)) foods.add('seed');
  if (plantedPlants.any(kAcornPlants.contains)) {
    foods.add('acorn');
    large = true; // 地面に落ちた堅果は大型動物も食べられる
  }
  if (large) foods.add('large_access');
  return foods;
}

/// 庭の供給から、来る動物(リス等)を返す。
List<String> animalsPresent(
    List<String> placedFeatures, List<String> plantedPlants) {
  final foods = availableFoods(placedFeatures, plantedPlants);
  final out = <String>[];
  for (final e in kAnimals.entries) {
    final eats = (e.value['eats'] as List).map((x) => '$x').toSet();
    if (eats.intersection(foods).isEmpty) continue;
    // かご型のみ等、大型が届かない供給しか無ければ来ない
    if (e.value['needs_large_access'] == true &&
        !foods.contains('large_access')) {
      continue;
    }
    out.add(e.key);
  }
  return out;
}

/// 居る動物(獲物)から、寄ってくる猛禽を返す(eatenBy の連鎖)。
List<String> raptorsPresent(List<String> animals) {
  final out = <String>[];
  for (final e in kRaptors.entries) {
    final prey = (e.value['preys_on_animals'] as List).map((x) => '$x').toSet();
    if (prey.intersection(animals.toSet()).isNotEmpty) out.add(e.key);
  }
  return out;
}

/// 猛禽が居るとき、警戒心 [wariness] の鳥の到来確率にかける係数(0〜1)。
///
/// 恐怖の景観(landscape of fear): 猛禽の圧の下では、臆病な種ほど来にくい。
/// 猛禽が居なければ 1.0(影響なし)。
double waryArrivalMultiplier(double wariness, List<String> raptors) {
  if (raptors.isEmpty) return 1.0;
  double? strength;
  for (final r in raptors) {
    final s = kRaptors[r]?['suppression'];
    if (s is num && (strength == null || s > strength)) {
      strength = s.toDouble();
    }
  }
  if (strength == null) return 1.0;
  final w = wariness.clamp(0.0, 1.0);
  final v = 1.0 - strength * w;
  return v < 0.0 ? 0.0 : v;
}

/// 連鎖の解決結果。
class FeederChain {
  final List<String> animals;
  final List<String> raptors;
  const FeederChain(this.animals, this.raptors);

  static const FeederChain empty = FeederChain([], []);
}

/// 庭の状態から連鎖を一括で解く。UI・エンジンからはこれを呼ぶ。
FeederChain resolveFeeders(
        List<String> placedFeatures, List<String> plantedPlants) {
  final animals = animalsPresent(placedFeatures, plantedPlants);
  return FeederChain(animals, raptorsPresent(animals));
}
