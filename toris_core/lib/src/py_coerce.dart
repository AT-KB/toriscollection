/// Python の `int()` / `float()` と**同じ振る舞い**をする変換。
///
/// なぜ要るか: 移植元のロジックは、種データが Google Sheets 由来で型が揃わない
/// 前提で書かれており、`int(x)` / `float(x)` が失敗したときの分岐に意味がある
/// (例: flock.py は int() が失敗したときだけ rarity から導く)。素直に
/// `int.tryParse` に置き換えると、`int(2.7) == 2` のような Python 固有の
/// 振る舞いが落ちて、移植のズレになる。ここを1か所に閉じ込めておく。
///
/// 変換できないときは null を返す(Python 側の TypeError/ValueError に当たる)。
library;

/// Python の `int(x)` 相当。
///
/// - int はそのまま
/// - double は**0方向へ切り捨て**(Python の int(2.7)==2, int(-2.7)==-2)
/// - bool は 1/0(Python では bool は int の一種)
/// - 文字列は**整数の書き方のときだけ**通る(Python は int("2.5") で例外)
int? pyInt(Object? x) {
  if (x == null) return null;
  if (x is bool) return x ? 1 : 0;
  if (x is int) return x;
  if (x is double) {
    if (x.isNaN || x.isInfinite) return null;
    return x.truncate();
  }
  if (x is String) {
    final s = x.trim();
    if (s.isEmpty) return null;
    return int.tryParse(s);
  }
  return null;
}

/// Python の `float(x)` 相当。
///
/// 文字列は "0.8" も "2" も通る(Python の float() と同じ)。
double? pyFloat(Object? x) {
  if (x == null) return null;
  if (x is bool) return x ? 1.0 : 0.0;
  if (x is num) return x.toDouble();
  if (x is String) {
    final s = x.trim();
    if (s.isEmpty) return null;
    return double.tryParse(s);
  }
  return null;
}
