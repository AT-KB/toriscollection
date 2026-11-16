/// ストアのレビューのお願い(`lib/review.dart`)。2026-11-16 戦略 柱B。
///
/// 守ること: **案内の途中では頼まない / 価値がわかってから / 一生に1回だけ**。
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:toris_app/garden/garden_state.dart';
import 'package:toris_app/review.dart';
import 'package:toris_core/toris_core.dart' as core;

Garden _g({int step = core.kTutorialSteps, int days = 0}) =>
    Garden(const GardenData({}, {}, {}, {'kyoto': {'max_plants': 4}}, {}, {}),
        biomeId: 'kyoto')
      ..tutorialStep = step
      ..openDays = days;

void main() {
  test('案内の途中では、名前をつけた直後でも頼まない', () {
    expect(takeReviewChance(_g(step: 1), justNamed: true), isFalse);
  });

  test('名前をつけた直後は頼む。2回目は無い', () {
    final g = _g();
    expect(takeReviewChance(g, justNamed: true), isTrue);
    expect(takeReviewChance(g, justNamed: true), isFalse);
    expect(takeReviewChance(g..openDays = 30, justNamed: false), isFalse);
  });

  test('おかえりでは、7日ひらいてくれてから', () {
    expect(takeReviewChance(_g(days: kReviewOpenDays - 1), justNamed: false),
        isFalse);
    expect(takeReviewChance(_g(days: kReviewOpenDays), justNamed: false),
        isTrue);
  });

  test('頼んだ印は端末に保存されて、開き直しても2回目は無い', () async {
    TestWidgetsFlutterBinding.ensureInitialized();
    SharedPreferences.setMockInitialValues({});
    final g = _g();
    takeReviewChance(g, justNamed: true);
    await g.save();
    final again = _g();
    await again.restore();
    expect(takeReviewChance(again..tutorialStep = core.kTutorialSteps,
            justNamed: true),
        isFalse);
  });
}
