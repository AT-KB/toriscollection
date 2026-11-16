/// ストアのレビューを、**一生に1回だけ**お願いする(2026-11-16 戦略 柱B)。
///
/// 評価が無いと Google Play のおすすめ枠に推薦できない(3.0 以上、インディーの棚は 3.8 以上)。
/// お願いするのは**価値がわかった瞬間**だけ:
///   1. 鳥に名前をつけた直後(愛着がいちばん大きいとき)
///   2. 7日以上ひらいてくれた人が、おかえりを見たあと
/// どちらも `Garden.takeHint('review_ask')` で1回きり。出すかどうかは Play が決める
/// (出なくても何も起きない)。文書: docs/team/proposals/2026-11-16_戦略_DLと収益化_半年.md
library;

import 'package:in_app_review/in_app_review.dart';

import 'garden/garden_state.dart';

/// おかえりのあとにお願いしてよい、ひらいた日数。
const kReviewOpenDays = 7;

/// 今お願いしてよいか。よければ印をつけて true(=2回目は無い)。
bool takeReviewChance(Garden g, {required bool justNamed}) {
  if (g.tutorialRunning) return false;
  if (!justNamed && g.openDays < kReviewOpenDays) return false;
  return g.takeHint('review_ask');
}

Future<void> maybeAskReview(Garden g, {required bool justNamed}) async {
  if (takeReviewChance(g, justNamed: justNamed)) await requestStoreReview();
}

Future<void> requestStoreReview() async {
  try {
    final r = InAppReview.instance;
    if (await r.isAvailable()) await r.requestReview();
  } catch (_) {
    // 端末に Play が無いなど。お願いできなくても困らない。
  }
}
