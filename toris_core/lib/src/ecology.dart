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

// ─────────────────────────────────────────────────────────────
// 顔ぶれの見せ方。`ecology.guild_label / guild_groups / lineup_story`。
//
// ⚠️ `ecology.py` は **i18n に依存しない**設計で、`lineup_story` は
// 「どの文か」の種類だけを返す。文にするのは表示側(radio.py)の仕事。
// ここでも同じ切り分けを守る — `lineupStory` は種類を返し、
// 文にするのは `stories.dart` の `lineupStoryText`。
// ─────────────────────────────────────────────────────────────

/// 採餌ギルドの見た目。`GUILD_LABELS`(絵文字, 日本語, 英語)。
class GuildLook {
  final String icon;
  final String english;
  const GuildLook(this.icon, this.english);
}

const Map<String, GuildLook> kGuildLabels = {
  'insectivore': GuildLook('🐛', 'insects'),
  'herbivore': GuildLook('🍇', 'berries and nectar'),
  'omnivore': GuildLook('🍃', 'a bit of everything'),
  'other': GuildLook('🐦', 'its own ways'),
};

/// 採餌ギルドの表示ラベル(英語)。知らないキーは "other" に落ちる。
String guildLabel(String guildKey) =>
    (kGuildLabels[guildKey] ?? kGuildLabels['other']!).english;

String guildIcon(String guildKey) =>
    (kGuildLabels[guildKey] ?? kGuildLabels['other']!).icon;

/// ギルドごとのまとまり。**2羽以上いるギルドだけ**、人数の多い順。
class GuildGroup {
  final String guild;
  final String icon;
  final String label;
  final List<String> birds;
  const GuildGroup(this.guild, this.icon, this.label, this.birds);
}

/// 顔ぶれをギルドごとにまとめる。`guild_groups` と同じ。
///
/// **同数のときの並びは、そのギルドが最初に現れた順**(Python の sort は
/// 安定なので、`by_guild` に入った順が残る)。ここも同じにする。
List<GuildGroup> guildGroups(
    List<String> birdIds, Map<String, dynamic> birdsData) {
  final byGuild = <String, List<String>>{}; // Dart の Map も挿入順を保つ
  for (final b in birdIds) {
    byGuild.putIfAbsent(guild(b, birdsData), () => []).add(b);
  }
  final groups = <GuildGroup>[];
  byGuild.forEach((g, members) {
    if (members.length < 2) return;
    groups.add(GuildGroup(g, guildIcon(g), guildLabel(g), members));
  });
  // 安定ソート(Dart の List.sort は安定ではないので、順位を付けて崩さない)
  final indexed = [
    for (var i = 0; i < groups.length; i++) MapEntry(i, groups[i])
  ];
  indexed.sort((a, b) {
    final c = b.value.birds.length.compareTo(a.value.birds.length);
    return c != 0 ? c : a.key.compareTo(b.key);
  });
  return [for (final e in indexed) e.value];
}

/// 今日の顔ぶれが「なぜ一緒にいるか」の**種類**。
///
/// 共起モデルの駆動要因(同じ採餌ギルド / 気候ニッチの重なり)から導く。
/// **種固有の逸話は作らない**(「冬に混群を作る」等は検証できない)。
/// モデルが言える範囲だけを返す(原則4「生態に誠実」)。
///
/// 戻り値: kind = 'guild' / 'climate' / 'mixed'、語れることが無ければ null。
class LineupStory {
  final String kind;

  /// kind == 'guild' のときの、中心になったギルド。
  final String? guild;
  const LineupStory(this.kind, {this.guild});
}

LineupStory? lineupStory(
    List<String> birdIds, Map<String, dynamic> birdsData) {
  final ids = [for (final b in birdIds) if (birdsData.containsKey(b)) b];
  if (ids.length < 2) return null;

  final counts = <String, int>{};
  for (final b in ids) {
    final g = guild(b, birdsData);
    counts[g] = (counts[g] ?? 0) + 1;
  }
  // most_common(1): 同数なら**最初に数えた方**(Counter は挿入順を保つ)
  var topGuild = counts.keys.first;
  var topN = counts[topGuild]!;
  counts.forEach((g, n) {
    if (n > topN) {
      topGuild = g;
      topN = n;
    }
  });

  var sum = 0.0;
  var pairs = 0;
  for (var i = 0; i < ids.length; i++) {
    for (var j = i + 1; j < ids.length; j++) {
      sum += climateOverlap(ids[i], ids[j], birdsData);
      pairs++;
    }
  }
  final clim = sum / pairs;

  if (topN >= 2 && topN >= ids.length * 0.6) {
    return LineupStory('guild', guild: topGuild);
  }
  if (clim >= 0.45) return const LineupStory('climate');
  return const LineupStory('mixed');
}
