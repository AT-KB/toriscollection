/// 「会った日数」の節目バッジ。`toris_collection/badges.py` の移植。
///
/// 交渉不能の原則1「受動的」・原則2「罰しない」に従う。連続ログイン条件も、
/// 進捗バーも、「あと◯日で称号」のような煽りも**持たない**。節目に届いたときだけ、
/// 図鑑のカードに小さな一言を添える。
///
/// Python 版は `t()` で表示言語に変換していたが、ここは UI を持たない層なので
/// **日本語の原文をそのまま返す**。訳を当てるのは表示側の仕事にする
/// (原文をキーに辞書を引く仕組みは Python 版と同じ)。
library;

/// 節目。大きいものから順に見て、最初に届いたもの1件だけを使う。
class BadgeTier {
  final int threshold;
  final String icon;

  /// 図鑑カードの見出しに使う短い呼び名(日本語原文)。
  final String label;

  /// カードに添える一言(日本語原文)。
  final String message;

  /// 一言の全文テンプレート。`{bird}` に鳥の名前が入る。
  final String template;

  const BadgeTier(
      this.threshold, this.icon, this.label, this.message, this.template);
}

const List<BadgeTier> badgeTiers = [
  BadgeTier(100, '🏅', '皆勤の友', 'すっかり顔なじみです。', '{bird}とはすっかり顔なじみです。'),
  BadgeTier(30, '🌿', '常連', 'よく会う仲になりました。', '{bird}とはよく会う仲になりました。'),
  BadgeTier(10, '🌱', 'おなじみ', 'おなじみになってきました。', '{bird}とはおなじみになってきました。'),
];

/// 会った日数から、該当する節目(最高位1件)を返す。未到達なら null。
BadgeTier? badgeForDays(int? days) {
  // Python 版は `if not days` なので、0 も null も同じ扱い(未到達)。
  if (days == null || days == 0) return null;
  for (final tier in badgeTiers) {
    if (days >= tier.threshold) return tier;
  }
  return null;
}

/// 図鑑カードに添える一言。バッジ未到達なら null。
///
/// 数値や進捗(あと何回等)は含めない。かわいさ優先で短く1文に留める。
/// 戻り値は日本語の原文。表示側で訳す。
String? badgeMessage(String birdName, int? days) {
  final tier = badgeForDays(days);
  if (tier == null) return null;
  return '${tier.icon} ${tier.template.replaceAll('{bird}', birdName)}';
}
