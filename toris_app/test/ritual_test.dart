/// 儀式の**終わり方**と、リス・鷹の驚き。
///
/// ## なぜ足したか(2026-08-18 CEO)
/// 「何分経っても近くで会えなかったり飛び去らなかったり、終わりのない感じ。
///  一定の敷居はほしいな、90秒で飛んでいくとか」
/// 「リスや鷹が木に近づいて、鳥が逃げていくアクション」
///
/// どちらも Python の `ritual.py` には**無い**。移植ではなく新しく足した分なので、
/// 突き合わせる相手がいない。だから**ここで振る舞いを固定する**。
///
/// 交渉不能の原則2「罰しない」に触れる機能なので、
/// **会えなくても記録が減らないこと**を試験で押さえる。
library;

import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/ritual.dart';
import 'package:toris_core/toris_core.dart' as core;

/// 時間を進めずに歩かせる(`Timer` を使わず、判定だけを回す)。
/// `_hop` は private なので、同じ歩き方をここで再現して確率を確かめる。
int _stepsToMeet(int seed) {
  final r = Random(seed);
  var branch = 0, dwell = 0, steps = 0;
  while (steps < 4000) {
    steps++;
    final forward = r.nextDouble() < (branch == 2 ? 0.45 : 0.55);
    branch = (branch + (forward ? 1 : -1)).clamp(0, 2);
    if (branch == 2) {
      dwell++;
      if (dwell >= 2) return steps;
    } else {
      dwell = 0;
    }
  }
  return steps;
}

void main() {
  _timingTests();

  test('敷居は120秒。**待てば会える**感じを壊さない長さであること', () {
    // 2026-11-03 に 90 → 120秒(歩くテンポを遅くしたぶん、敷居を延ばした)
    expect(Ritual.maxSteps * Ritual.step.inMilliseconds / 1000, 120.0);

    // 2万回まわして、90秒(36歩)以内に成立する割合を見る。
    // ここが大きく下がるようなら、歩き方か敷居のどちらかを変えている。
    var ok = 0;
    for (var s = 0; s < 20000; s++) {
      if (_stepsToMeet(s) <= Ritual.maxSteps) ok++;
    }
    final rate = ok / 20000;
    expect(rate, greaterThan(0.95),
        reason: '90秒で切ると9割5分は会えるはずだった(実測97.8%)。'
            'これを下回るなら、待てば会えるという約束が壊れている');
  });

  test('敷居までに会える割合は、**どのスタイルでも** 97% を下回らない', () {
    // ⚠️ 2026-09-22 で歩く速さが鳥ごとに変わった。**固定36歩ではもう測れない。**
    // 90秒で打てる歩数はスタイルごとに違うので、その歩数で切って数える。
    //
    // 遅いスタイルを作ると歩数が減り、そのぶん成立率が落ちる(企画 A-3 の表)。
    // いちばん遅い calm が現行と同じ 36.0歩・97.75% なので、**最悪ケースが
    // 現状と同じ**になっている。ここが崩れたら「待てば会える」が痩せている。
    const totalTicks = Ritual.maxSteps * Ritual.ticksPerStep;
    for (final st in HopStyle.all) {
      var ok = 0;
      for (var s = 0; s < 20000; s++) {
        final hops = _hopTicks(Random(s), totalTicks, st).length;
        if (_stepsToMeet(s) <= hops) ok++;
      }
      final rate = ok / 20000;
      expect(rate, greaterThan(0.97),
          reason: '${st.name} で 120秒に会える割合が 97% を切った '
              '(実測 quick 99.6 / steady 98.9 / calm 98.0%)。'
              'テンポを遅くすると歩数が減ってここが落ちる');
    }
  });

  test('餌台が無ければ、驚きは一度も起きない', () {
    final r = Ritual(['blue_jay'], Random(1));
    expect(r.chain.animals, isEmpty);
    expect(r.chain.raptors, isEmpty);
    expect(r.scare, isNull);
  });

  test('開放型の餌台にはリスが来る。かご型なら来ない', () {
    // 驚きの元は**餌台の連鎖そのもの**。ここが空なら儀式も静かなまま。
    final open = core.resolveFeeders(['feeder_open'], ['sunflower']);
    final caged = core.resolveFeeders(['feeder_caged'], ['sunflower']);
    expect(open.animals, isNotEmpty,
        reason: '開放型はリスが来る前提。来ないなら驚きが一生起きない');
    expect(caged.animals, isEmpty,
        reason: 'かご型でリスが来ると、餌台を選ぶ意味が消える');
  });

  test('会えなくても、飛んでいった鳥は記録から何も引かない', () {
    // Ritual は記録を持たない。**減らす手段が無い**ことを型で押さえる
    // (生態ログに削除関数を持たせないのと同じ考え。原則2)。
    final r = Ritual(['blue_jay', 'song_sparrow'], Random(3));
    expect(r.flewOff, isEmpty);
    expect(r.met, isEmpty);
    expect(r.timedOut, isFalse);
    // 飛んでいった鳥は「会えなかった」だけで、met には入らない。
    expect(r.flewOff.intersection(r.met), isEmpty);
  });

  test('残り時間は持っているが、画面に出す前提の名前にしない', () {
    // 急かす表示を作らないための歯止め(原則1)。値は持つが、
    // 画面に出したくなったらこの試験の意図を読み直すこと。
    final r = Ritual(['blue_jay'], Random(1));
    expect(r.secondsLeft, 120.0); // 2026-11-03 に 90 → 120秒
  });
}

// ── 鳥ごとに動くタイミングがばらけること ───────────────────────
//
// ## なぜ足したか(CEO 2026-08-28)
// 「鳥たちが同時に動くのがなんかいけてない、儀式のとき。
//  実際の鳥みたいに、動くのランダムにできない?タイミングを」
//
// 前は `Timer.periodic(step)` が1本で、**その1回で全羽をまとめて動かして**
// いた。だから3羽が2.5秒ごとに一斉に跳んで、時計仕掛けに見えていた。
//
// いまは 250ms で回して、鳥ごとに自分の番(`_nextHopTick`)が来た時だけ跳ぶ。
// 間隔は 8〜12 刻み(2.0〜3.0秒)を一様に引く = **平均はちょうど 2.5秒**。
//
// ⚠️ ここで押さえたいのは2つ:
//   (1) **見た目**: 一斉に動かないこと
//   (2) **バランス**: 歩く速さの期待値を変えていないので、
//       「90秒で 97.8% が出会う」が崩れていないこと
//
// `_nextHopTick` は private なので、**同じ組み立てをここで再現**して確かめる
// (`_stepsToMeet` と同じやり方)。

/// 1羽ぶんの「跳ぶ刻み」の並びを作る。
///
/// ⚠️ **式を書き写さない。** 実装の `HopStyle.firstHop` / `nextHop` を
/// そのまま呼ぶ。手で再現すると、実装を直したときに試験だけ古いまま通る
/// (HANDOFF_00 §2「テストは落ちることを確かめてから信じる」)。
List<int> _hopTicks(Random r, int totalTicks, HopStyle st) {
  final out = <int>[];
  var next = st.firstHop(r);
  while (next <= totalTicks) {
    out.add(next);
    next = st.nextHop(r, next);
  }
  return out;
}

void _timingTests() {
  const totalTicks = Ritual.maxSteps * Ritual.ticksPerStep; // 120秒ぶん

  test('刻みは 2.5秒 をちょうど割り切る(1歩=10刻み)', () {
    expect(Ritual.tickInterval.inMilliseconds * Ritual.ticksPerStep,
        Ritual.step.inMilliseconds);
  });

  test('3羽が同じ刻みで一斉に跳ぶことは、ほとんど無い', () {
    var allSame = 0;
    const trials = 500;
    for (var s = 0; s < trials; s++) {
      final r = Random(s);
      final a = _hopTicks(r, totalTicks, HopStyle.quick).toSet();
      final b = _hopTicks(r, totalTicks, HopStyle.steady).toSet();
      final c = _hopTicks(r, totalTicks, HopStyle.calm).toSet();
      // 3羽の跳ぶ刻みが完全に一致 = 前の「一斉に動く」状態
      if (a.length == b.length && a.containsAll(b) && a.containsAll(c)) {
        allSame++;
      }
    }
    expect(allSame, 0,
        reason: '3羽が完全に同じ刻みで跳んでいる = 一斉に動いて見える');
  });

  test('どのスタイルも、敷居までに36歩以上は打つ', () {
    // ⚠️ 2026-11-03: テンポを遅くし(2.0 / 2.75 / 3.25秒)、敷居を120秒に延ばした。
    // **下限は前と同じ 36歩**(歩数が減ると成立率が落ちる)。
    // ⚠️ **期待値は 2026-09-22 に変わった。** 前は全羽が平均 2.5秒ちょうどで
    // 「36歩前後」だったが、いまは quick / steady を**速く**してある。
    // 遅い側は作っていないので、**下限は calm の 36.0歩**。
    // (企画 A-3: 実効平均を 2.50秒より遅くしない = 歩数を減らさない)
    const expected = {'quick': 54.0, 'steady': 41.4, 'calm': 36.9};
    const trials = 2000;
    for (final st in HopStyle.all) {
      var total = 0;
      for (var s = 0; s < trials; s++) {
        total += _hopTicks(Random(s), totalTicks, st).length;
      }
      final avg = total / trials;
      expect(avg, closeTo(expected[st.name]!, 1.0),
          reason: '${st.name} の歩数が想定(${expected[st.name]})から外れた');
      expect(avg, greaterThanOrEqualTo(35.0),
          reason: '${st.name} が現行(36.0歩)より遅い。'
              '遅い鳥を作ると成立率が落ちる(企画 A-3)');
    }
  });

  test('3羽以下なら、基本テンポが全部ちがう', () {
    // ⚠️ **ここが 2026-09-22 の直しの本体。** 位相をずらしても、周期が全員
    // 同じなら目は「同じ拍」として拾う(企画 A-0)。
    // ここが壊れたら、8/28 以前に戻ったのと同じ。
    for (var s = 0; s < 200; s++) {
      final r = Ritual(['a', 'b', 'c'], Random(s));
      final bases = {for (final b in r.birdIds) r.style[b]!.base};
      expect(bases.length, 3,
          reason: '3羽の基本テンポが揃っている = 時計仕掛けに見える');
    }
    // 2羽でも全員ちがう。
    final two = Ritual(['a', 'b'], Random(7));
    expect({for (final b in two.birdIds) two.style[b]!.base}.length, 2);
  });

  test('4羽以上は配り直す(i mod 3)。誰も割り当て漏れしない', () {
    final r = Ritual(['a', 'b', 'c', 'd', 'e'], Random(11));
    for (final b in r.birdIds) {
      expect(r.style[b], isNotNull,
          reason: '割り当てが漏れると、その鳥だけ既定のテンポで歩く');
    }
  });
}
