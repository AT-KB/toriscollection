/// 群れ(同種が複数)のサイズを決める純粋計算。`toris_collection/flock.py` の移植。
///
/// 群れは「ラジオを豊かにする」装置。新種を増やさずに、馴染んだ鳥の声を厚くする。
/// よく会った鳥ほど大きな群れで鳴く = 「会いに行く」がそのまま声の厚みになる。
///
/// 生態学的な根拠は Python 版の docstring を参照(群れやすさは種に依存し、
/// ここでは rarity を素朴な代理変数として使う)。
library;

import 'py_coerce.dart';

/// 1種あたりの群れ上限(音が濁らない範囲に抑える)。
const int maxCap = 3;

/// 観察何回ごとに群れが1羽増えるか。
const int growthEvery = 3;

/// その種が作りうる群れの最大サイズ(1..maxCap)。
///
/// データに flock_max があればそれを使う(種ごとの上書き)。無ければ rarity から
/// 導く: 普通種=群れやすい / レア種=単独。
int flockCap(String birdId, Map<String, dynamic> birdsData) {
  final bird = (birdsData[birdId] as Map?) ?? const {};
  final explicit = bird['flock_max'];
  if (explicit != null) {
    final n = pyInt(explicit);
    // Python 版は int() が失敗したときだけ rarity へ落ちる。数として読めたなら
    // その値を 1..maxCap に丸めて使う。
    if (n != null) return n.clamp(1, maxCap);
  }
  final r = pyFloat(bird['rarity']) ?? 0.5;
  if (r >= 0.7) return 1; // レア = 単独(特別な一声)
  if (r >= 0.4) return 2;
  return 3; // 普通種 = 群れやすい
}

/// ラジオで今この鳥が何羽で鳴くか(1..cap)。
///
/// cap を超えない範囲で、観察回数に応じて群れが育つ。単独種(cap=1)は常に1。
int flockSize(String birdId, Object? count, Map<String, dynamic> birdsData) {
  final cap = flockCap(birdId, birdsData);
  if (cap <= 1) return 1;
  final c = pyInt(count) ?? 0;
  // Python の `max(0, c) // GROWTH_EVERY`(切り捨て除算)
  final grown = 1 + (c < 0 ? 0 : c) ~/ growthEvery;
  return grown.clamp(1, cap);
}
