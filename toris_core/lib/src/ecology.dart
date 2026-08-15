/// 鳥どうしの「一緒に見られやすさ」。`toris_collection/ecology.py` の移植。
///
/// ラジオの顔ぶれは**純粋なランダムではなく**、すでに選ばれた鳥と一緒に
/// 見られやすい鳥を引きやすくする。こうして「関係の強い鳥たちが揃う」まとまった
/// 顔ぶれになる。交渉不能の原則4「生態に誠実」— 関係は恣意的に足さず、
/// 食べ物と気候の重なりから出す。
library;

import 'py_coerce.dart';

/// ギルド(食性のまとまり)。
String guild(String birdId, Map<String, dynamic> birdsData) {
  final bird = (birdsData[birdId] as Map?) ?? const {};
  final hasI = _truthy(bird['eats_insects']);
  final hasP = _truthy(bird['eats_plants']);
  if (hasI && hasP) return 'omnivore';
  if (hasI) return 'insectivore';
  if (hasP) return 'herbivore';
  return 'other';
}

/// Python の `bool(x)` と同じ判定(空リスト/空文字/0/null は偽)。
bool _truthy(Object? v) {
  if (v == null) return false;
  if (v is bool) return v;
  if (v is num) return v != 0;
  if (v is String) return v.isNotEmpty;
  if (v is Iterable) return v.isNotEmpty;
  if (v is Map) return v.isNotEmpty;
  return true;
}

/// 気候ニッチの重なり(0..1)。温度域がどれだけ重なっているか。
double climateOverlap(String a, String b, Map<String, dynamic> birdsData) {
  final fa = ((birdsData[a] as Map?) ?? const {})['temp_fit'];
  final fb = ((birdsData[b] as Map?) ?? const {})['temp_fit'];
  if (fa is! List || fb is! List || fa.length < 2 || fb.length < 2) return 0.0;
  final a0 = pyFloat(fa[0]), a1 = pyFloat(fa[1]);
  final b0 = pyFloat(fb[0]), b1 = pyFloat(fb[1]);
  if (a0 == null || a1 == null || b0 == null || b1 == null) return 0.0;
  final lo = a0 > b0 ? a0 : b0;
  final hi = a1 < b1 ? a1 : b1;
  final inter = hi - lo;
  final union = (a1 > b1 ? a1 : b1) - (a0 < b0 ? a0 : b0);
  if (inter <= 0 || union <= 0) return 0.0;
  return inter / union;
}

/// 食べ物の重なり(Jaccard 係数)。
double dietJaccard(String a, String b, Map<String, dynamic> birdsData) {
  Set<String> diet(String id) {
    final m = (birdsData[id] as Map?) ?? const {};
    return {
      ...((m['eats_plants'] as List?) ?? const []).map((e) => '$e'),
      ...((m['eats_insects'] as List?) ?? const []).map((e) => '$e'),
    };
  }

  final sa = diet(a), sb = diet(b);
  if (sa.isEmpty && sb.isEmpty) return 0.0;
  final union = sa.union(sb);
  if (union.isEmpty) return 0.0;
  return sa.intersection(sb).length / union.length;
}

/// 2羽の「よく一緒に見られる度」(0..1)。
///
/// = 気候ニッチ重なり × ギルド係数 × 競争抑制
/// 餌がほぼ同じ(J>0.7)だと**競争排除**で一緒にいにくくなる、という生態の筋を
/// そのまま式にしている。
double coOccurrence(String a, String b, Map<String, dynamic> birdsData) {
  if (a == b) return 0.0;
  final clim = climateOverlap(a, b, birdsData);
  final g = guild(a, birdsData) == guild(b, birdsData) ? 1.0 : 0.45;
  final j = dietJaccard(a, b, birdsData);
  final comp = 1.0 - 0.7 * (j - 0.7 > 0 ? j - 0.7 : 0.0) / 0.3;
  return clim * g * comp;
}

/// 共起しやすさの対称行列(自己 = 0)。呼応の相手選びに使う。
List<List<double>> coOccurrenceMatrix(
    List<String> birdIds, Map<String, dynamic> birdsData) {
  final n = birdIds.length;
  final mat = [for (var i = 0; i < n; i++) List<double>.filled(n, 0.0)];
  for (var i = 0; i < n; i++) {
    for (var j = i + 1; j < n; j++) {
      final c = coOccurrence(birdIds[i], birdIds[j], birdsData);
      mat[i][j] = c;
      mat[j][i] = c;
    }
  }
  return mat;
}

/// 「今日の顔ぶれ」を選ぶ。
///
/// 種(seed)は基礎重みで選び(= よく会う鳥ほど主役に出やすい)、以降は
/// **すでに選ばれた鳥と共起しやすい鳥**を引きやすくする。
/// 0.25 の下駄があるので、関係の薄い鳥もたまには混じる(単調さの回避)。
///
/// [nextDouble] は 0..1 の乱数。テストから固定できるように外から渡す。
List<String> pickLineup(
  List<String> candidateIds,
  Map<String, dynamic> birdsData,
  int k,
  double Function() nextDouble, {
  Map<String, double>? baseWeight,
}) {
  final cand = List<String>.from(candidateIds);
  if (cand.length <= k) return cand;
  final bw = baseWeight ?? const {};

  String weightedPick(List<String> items, List<double> weights) {
    final total = weights.fold<double>(0, (a, b) => a + b);
    if (total <= 0) return items[(nextDouble() * items.length).floor()];
    var r = nextDouble() * total;
    var acc = 0.0;
    for (var i = 0; i < items.length; i++) {
      acc += weights[i];
      if (r <= acc) return items[i];
    }
    return items.last;
  }

  final remaining = List<String>.from(cand);
  final seed =
      weightedPick(remaining, [for (final b in remaining) bw[b] ?? 1.0]);
  final chosen = <String>[seed];
  remaining.remove(seed);

  while (chosen.length < k && remaining.isNotEmpty) {
    final weights = <double>[];
    for (final b in remaining) {
      var co = 0.0;
      for (final c in chosen) {
        final v = coOccurrence(b, c, birdsData);
        if (v > co) co = v;
      }
      weights.add((bw[b] ?? 1.0) * (0.25 + co));
    }
    final pick = weightedPick(remaining, weights);
    chosen.add(pick);
    remaining.remove(pick);
  }
  return chosen;
}
