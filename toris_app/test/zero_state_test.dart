/// **ゼロ状態(まだ何もしていない人)に、何が見えてはいけないか。**
///
/// ## なぜこのファイルがあるか(2026-08-21)
/// ラジオが**会っていない鳥まで鳴らしていた**。移植で絞り込みが落ちたのが原因だが、
/// 監査も fixtures もそれを捕まえられなかった。理由は構造的:
///
///   ・台帳は Python の**公開関数**しか数えない。あの絞り込みは
///     `render_radio` の**中に直接書かれた式**だったので、載りようがなかった。
///   ・fixtures は「誰かが足したもの」しか比べない。
///
/// 個別に grep を足しても同じ形の穴はまた開く。そこで**別の角度**から張る:
/// この種の抜けは、**ほぼ必ずゼロ状態で表に出る**。
/// 何も持っていない人に「持っている人向けのもの」が見えていたら、それは抜けである。
///
/// **画面を足したら、ここに「ゼロ状態で何が無いか」を1つ足すこと。**
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_core/toris_core.dart' as core;

void main() {
  group('ゼロ状態: 何もしていない人に見えてはいけないもの', () {
    test('ラジオ: 会った鳥が0なら、鳴る鳥は0', () {
      // 掲載文 "A radio made only of birds you've met" を支えている規則。
      const pool = ['american_goldfinch', 'northern_cardinal', 'blue_jay'];
      expect(core.observedInBiome(pool, const {}), isEmpty);
      // 記録はあるが0回、も「会っていない」。
      expect(core.observedInBiome(pool, const {'blue_jay': 0}), isEmpty);
      // 1回でも会えば鳴く。
      expect(core.observedInBiome(pool, const {'blue_jay': 1}), ['blue_jay']);
    });

    test('今日の道具: 餌台が無ければ、餌台に依る道具は出ない', () {
      // 継ぎ足しは継ぎ足す先が、リス返しは守る対象(開放型)が要る。
      const birds = <String, dynamic>{};
      expect(
          core.itemIsAvailable('feeder', 'charlotte', birds,
              placedFeeders: const []),
          isFalse);
      expect(
          core.itemIsAvailable('squirrel_baffle', 'charlotte', birds,
              placedFeeders: const []),
          isFalse);
      // かご型だけでは、リス返しは意味を持たない(元からリスが来ない)。
      expect(
          core.itemIsAvailable('squirrel_baffle', 'charlotte', birds,
              placedFeeders: const ['feeder_cage']),
          isFalse);
    });

    test('今日の道具: 置いていなければ、到来にも退去にも一切効かない', () {
      // 「見なくても通常の到来確率は変わらない」(原則1)の機械的な保証。
      final fn = core.makeArrivalBonusFn(null, 'charlotte', const {});
      expect(fn('american_goldfinch'), 0.0);
      expect(core.itemDepartureBonus(null), 0.0);
      expect(core.isBaffleActive(null), isFalse);
    });

    test('餌台: 置いていなければ、リスも猛禽も来ない', () {
      final chain = core.resolveFeeders(const [], const []);
      expect(chain.animals, isEmpty);
      expect(chain.raptors, isEmpty);
    });
  });
}
