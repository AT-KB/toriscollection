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

/// 庭に置く餌台。`largeAccess` = 大型動物(リス)が中身に届くか。
const Map<String, Map<String, Object>> kFeeders = {
  'feeder_open': {
    'english': 'Open feeder',
    'offers': 'seed',
    'large_access': true,
  },
  'feeder_cage': {
    'english': 'Caged feeder',
    'offers': 'seed',
    'large_access': false,
  },
};

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
