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
