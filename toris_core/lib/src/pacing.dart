/// 鳥が来るペース。**Python には無い、Flutter 版だけの調整**(CEO 2026-11-07)。
///
/// CEO「鳥の来る頻度をちょっと落としてほしい、時間軸の進み方とかかな?
/// もうちょっとコレクション難易度を上げて、鳥が来る喜びを知ってほしい」
/// 「ログインし続けることで、鳥が来やすくなるインセンティブ」
/// 「警戒心とかに係数つけれるといいな。一定以上警戒心下がると、鳥ごとに名前つけれる」
///
/// ## 前の進み方の穴
/// `estimateTickCount` は経過時間に**比例しない**(5分〜30分で1コマ、1日で5コマ)。
/// 5分おきに開くと1時間で12コマ進み、1日放っておくと5コマ。
/// **こまめに開くほど何倍も早く図鑑が埋まった。**
///
/// ## 3つの係数(到来確率に**掛ける**。`runTurn` の arrivalScaleFn)
///  1. **全体と珍しさ** — 全体を半分にし、珍しい鳥ほどさらに来にくく。
///  2. **庭のなじみ** — アプリを開いた**日数の合計**で段が上がり、珍しい鳥が来やすくなる。
///     ⚠️ **連続ログインにはしない。** 途切れたら戻る仕組みは原則2「罰しない」に反し、
///     「毎日開かないと損」は原則1「受動的」に反する。合計なので休んでも減らない。
///  3. **鳥の慣れ** — 近くで会った回数(observed)で、その鳥の警戒心が下がる。
///     警戒心の強い鳥ほど、慣れの効き目が大きい。
///
/// ## 数字の根拠(Python の本体エンジンで 40回 × 90日、京都、1日3回開く、7日ごとに植え替え)
/// | | 最初の1羽 | 10種 | 15種 | 18種 | 20種(全部) |
/// |---|---|---|---|---|---|
/// | 前 | 1日目 | 3日 | 6日 | 11.5日 | 26日 |
/// | いま | 1日目 | 6日 | 11日 | 17.5日 | 34.5日 |
/// 「最初の1羽は初日」は変えない — 来る喜びを最初に知ってもらうため。
library;

import 'py_coerce.dart';

/// 1コマが何時間ぶんか。
const double kHoursPerTick = 3.0;

/// 1回で進める上限のコマ数(= 18時間ぶん)。
const int kMaxTicksPerVisit = 6;

/// 経過時間 → コマ数。**実時間に比例する**(3時間で1コマ、上限6コマ)。
int pacedTickCount(double hours) {
  if (hours <= 0) return 0;
  final n = (hours / kHoursPerTick).floor();
  return n > kMaxTicksPerVisit ? kMaxTicksPerVisit : n;
}

/// 進めたあとの「前回見た時刻」。**端数を持ち越す**。
///
/// 1時間おきに開く人は、毎回0コマでも3回目で1コマ進む。
/// now に揃えると端数が消え、こまめに開く人の庭が止まってしまう。
/// 上限を超えて離れていたぶんは持ち越さない(18時間以上は now に揃える)。
DateTime pacedLastSeen(DateTime last, DateTime now, int ticks) {
  final hours = now.difference(last).inSeconds / 3600.0;
  if (hours >= kHoursPerTick * kMaxTicksPerVisit) return now;
  return last.add(Duration(seconds: (ticks * kHoursPerTick * 3600).round()));
}

/// 全体の係数。
const double kBaseScale = 0.5;

/// 珍しさの効き(rarity 1.0 で 1 − 0.7 = 0.3 倍)。
const double kRarityWeight = 0.7;

/// 庭のなじみの段。開いた日数の合計がこの日数に届くたびに1段。
const List<int> kFamiliarityDays = [3, 7, 14, 30];

/// 1段あたり、珍しい鳥にだけ足す割合(rarity × 0.25 × 段)。
const double kFamiliarityWeight = 0.25;

/// 鳥が慣れきるまでの「近くで会った回数」。
const int kTameMeets = 6;

/// 慣れの効き(警戒心 1.0 の鳥が慣れきると 1.5 倍)。
const double kTameWeight = 0.5;

/// **名前をつけられる**ようになる「近くで会った回数」。慣れきったとき。
/// 2羽目・3羽目はその倍・3倍(CEO 2026-11-08「1羽あたり3名まで」)。
const int kNicknameMeets = kTameMeets;

/// 1種につけられる名前の上限。
const int kMaxNicknames = 3;

/// 庭のなじみの段(0〜4)。
int gardenFamiliarityLevel(int openDays) =>
    kFamiliarityDays.where((d) => openDays >= d).length;

/// 次の段まであと何日か。最上段なら null。
int? daysToNextFamiliarity(int openDays) {
  for (final d in kFamiliarityDays) {
    if (openDays < d) return d - openDays;
  }
  return null;
}

/// 鳥の慣れ(0〜1)。近くで会った回数 / [kTameMeets]。
double tameness(int meets) =>
    meets <= 0 ? 0.0 : (meets >= kTameMeets ? 1.0 : meets / kTameMeets);

/// 名前をつけられるか(1羽目)。
bool canNickname(int meets) => meets >= kNicknameMeets;

/// 名前の枠がいくつ開いているか(0〜3)。6回で1つ、12回で2つ、18回で3つ。
int nicknameSlots(int meets) {
  final n = meets ~/ kNicknameMeets;
  return n > kMaxNicknames ? kMaxNicknames : n;
}

/// 次の枠まであと何回会えばいいか。枠が全部開いていれば null。
int? meetsToNextSlot(int meets) {
  final open = nicknameSlots(meets);
  if (open >= kMaxNicknames) return null;
  return (open + 1) * kNicknameMeets - meets;
}

/// 到来確率に掛ける係数。
double arrivalScale(Map? bird, {required int openDays, required int meets}) {
  final b = bird ?? const {};
  final r = (pyFloat(b['rarity']) ?? 0.5).clamp(0.0, 1.0);
  final w = (pyFloat(b['wariness']) ?? 0.5).clamp(0.0, 1.0);
  final lvl = gardenFamiliarityLevel(openDays);
  return kBaseScale *
      (1 - kRarityWeight * r) *
      (1 + kFamiliarityWeight * lvl * r) *
      (1 + kTameWeight * w * tameness(meets));
}

/// `runTurn` / `evolveWhileAway` に渡す形。
double Function(String) makeArrivalScaleFn(
  Map<String, dynamic> birdsData, {
  required int openDays,
  required Map<String, int> meets,
}) =>
    (bid) => arrivalScale(birdsData[bid] as Map?,
        openDays: openDays, meets: meets[bid] ?? 0);
