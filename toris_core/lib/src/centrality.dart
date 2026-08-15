/// Sony CSL 補正済み中心性から、レア度係数を出す。`centrality.py` +
/// `engine.calculate_arrival_probability` の中心性部分の移植。
///
/// ## なぜ要るか
/// GloBI の生の中心性は「有名な種ほど大きく出る」サンプリングバイアスを持つ。
/// Funabashi et al. (2024) がべき分布フィッティングで補正した値を出しており、
/// それを使うと**データが少ないだけのマイナー種を不当に不利にしない**
/// (交渉不能の原則4「生態に誠実」)。
///
/// ## ⚠️ いまは誰も呼んでいない、が式は持つ
/// 元データ(約200-300MB)は**リポジトリに置かれていない**ため、Python 側でも
/// `is_available()` が False を返し、この補正は**一度も発動していない**。
/// 私は当初「動作が同じだから」と式ごと移さなかったが、それは推測で決めたこと。
/// CEO 2026-08-16「呼ぶ確率とかのロジックは基本すべて移すこと、推測ではなく
/// 忠実に」を受けて、**式を持ち、データが来たら同じ答えを出せる**ようにした。
///
/// データを入れるときは `centrality.py` のキャッシュ
/// (`.centrality_cache.json`、37種ぶんの小さな JSON)を書き出して
/// アセットに置き、`loadCentralities` に渡す。
library;

import 'dart:math';

/// 1種ぶんの中心性。キーは `centrality.py` のキャッシュと同じ。
class Centrality {
  final double? pr;
  final double? prCorrected;
  const Centrality({this.pr, this.prCorrected});

  /// 補正後を優先し、無ければ生の値。`get_centrality(use_corrected: true)` と同じ。
  ///
  /// Python は `data.get("pr_corrected") or data.get("pr")` — **0 は偽**なので
  /// pr_corrected が 0 のときは pr に落ちる。そこまで同じにする。
  double? get value =>
      (prCorrected != null && prCorrected != 0.0) ? prCorrected : pr;

  static Centrality? fromJson(Object? o) {
    if (o is! Map) return null;
    double? d(String k) {
      final v = o[k];
      return v is num ? v.toDouble() : null;
    }

    return Centrality(pr: d('pr'), prCorrected: d('pr_corrected'));
  }
}

/// 学名 → 中心性。**キーは大文字**(Python 側が `.upper()` で持つ)。
Map<String, Centrality> loadCentralities(Map<String, dynamic> raw) {
  final out = <String, Centrality>{};
  raw.forEach((k, v) {
    final c = Centrality.fromJson(v);
    if (c != null) out[k.toUpperCase()] = c;
  });
  return out;
}

/// 中心性から出したレア度係数。データが無ければ null(呼び出し側が
/// シードの rarity から出した値をそのまま使う)。
///
/// `engine.calculate_arrival_probability` と同じ式:
/// ```
/// pr が正なら normalized = clamp((log10(pr) + 8) / 5, 0.05, 0.7)
///   -8 → 0.05(超レア) / -4 → 0.7(普通)
/// ```
double? centralityRarityFactor(
    String? scientific, Map<String, Centrality>? centralities) {
  if (centralities == null || centralities.isEmpty) return null;
  if (scientific == null || scientific.isEmpty) return null;
  final c = centralities[scientific.toUpperCase()];
  if (c == null) return null;
  final pr = c.value;
  // Python は `if pr and pr > 0` — null も 0 も通さない。
  if (pr == null || pr <= 0) return null;
  final logPr = log(pr) / ln10;
  final normalized = (logPr + 8) / 5;
  return max(0.05, min(0.7, normalized));
}

/// 中心性のデータが手元にあるか。`centrality.is_available` に当たる。
///
/// Python はデータ**ファイル**の有無を見るが、Dart 側はファイルを持たない層
/// なので「表が渡されて、中身があるか」で判定する。
bool centralityIsAvailable(Map<String, Centrality>? centralities) =>
    centralities != null && centralities.isNotEmpty;

/// その分類群の PageRank。`centrality.get_centrality` と同じ。
///
/// [useCorrected] が true なら補正後を優先し、無ければ生の値。
/// false なら生の値だけ。見つからなければ null。
double? getCentrality(String taxonName, Map<String, Centrality> centralities,
    {bool useCorrected = true}) {
  final c = centralities[taxonName.toUpperCase()];
  if (c == null) return null;
  return useCorrected ? c.value : c.pr;
}
