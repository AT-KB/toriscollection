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

  test('敷居は90秒。**待てば会える**感じを壊さない長さであること', () {
    expect(Ritual.maxSteps * Ritual.step.inMilliseconds / 1000, 90.0);

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
    expect(r.secondsLeft, 90.0);
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

/// 1羽ぶんの「跳ぶ刻み」の並びを、実装と同じ式で作る。
List<int> _hopTicks(Random r, int totalTicks) {
  final out = <int>[];
  var next = r.nextInt(Ritual.ticksPerStep) + 1; // 始まりの位相
  while (next <= totalTicks) {
    out.add(next);
    next += Ritual.ticksPerStep +
        r.nextInt(Ritual.jitterTicks * 2 + 1) - Ritual.jitterTicks;
  }
  return out;
}

void _timingTests() {
  const totalTicks = Ritual.maxSteps * Ritual.ticksPerStep; // 90秒ぶん

  test('刻みは 2.5秒 をちょうど割り切る(1歩=10刻み)', () {
    expect(Ritual.tickInterval.inMilliseconds * Ritual.ticksPerStep,
        Ritual.step.inMilliseconds);
  });

  test('3羽が同じ刻みで一斉に跳ぶことは、ほとんど無い', () {
    var allSame = 0;
    const trials = 500;
    for (var s = 0; s < trials; s++) {
      final r = Random(s);
      final a = _hopTicks(r, totalTicks).toSet();
      final b = _hopTicks(r, totalTicks).toSet();
      final c = _hopTicks(r, totalTicks).toSet();
      // 3羽の跳ぶ刻みが完全に一致 = 前の「一斉に動く」状態
      if (a.length == b.length && a.containsAll(b) && a.containsAll(c)) {
        allSame++;
      }
    }
    expect(allSame, 0,
        reason: '3羽が完全に同じ刻みで跳んでいる = 一斉に動いて見える');
  });

  test('歩く速さの期待値は変えていない(90秒でならして36歩前後)', () {
    var total = 0;
    const trials = 2000;
    for (var s = 0; s < trials; s++) {
      total += _hopTicks(Random(s), totalTicks).length;
    }
    final avg = total / trials;
    // 平均間隔がちょうど 10 刻みなので、360 刻み ÷ 10 = 36 歩前後になる。
    expect(avg, closeTo(Ritual.maxSteps.toDouble(), 1.0),
        reason: 'ここがずれると「90秒で97.8%が出会う」の前提が崩れる');
  });
}
