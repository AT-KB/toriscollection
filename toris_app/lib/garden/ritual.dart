/// 出会いの儀式。現行(Streamlit)の `ritual.py` に当たる。
///
/// 「♪ 耳を澄ます」と、鳥が枝を移りながら少しずつ近づいてくる。
/// **手前の枝(b1)まで来て留まった瞬間が「出会い」**で、そこで会った回数が増える。
/// 会った回数は、ラジオでの近さ・群れの厚みに効く。
///
/// 交渉不能の原則に沿う:
///  - **急かさない。** 押し続けさせない。待っていれば近づいてくる。
///  - **罰しない。** 近づかなかった鳥がいても、何も失わない。
library;

import 'dart:async';
import 'dart:math';

import 'package:flutter_soloud/flutter_soloud.dart';
import 'package:toris_core/toris_core.dart' as core;

/// 儀式の1回ぶん。
class Ritual {
  final List<String> birdIds;
  final Random _rng;

  /// 庭の餌台から解けた連鎖(リス・鷹)。`core.resolveFeeders` の結果。
  /// 空なら驚きは**一切起きない**(かご型の餌台・餌台なしの庭)。
  final core.FeederChain chain;

  bool get _hasRaptor => chain.raptors.isNotEmpty;
  bool get _hasAnimal => chain.animals.isNotEmpty;

  /// 1歩(2.5秒)あたり、驚きが起きる確率。
  ///
  /// 90秒＝36歩を通しての「1回でも起きる」確率で決めた:
  ///   鷹が居る   0.020 → 約52%
  ///   リスだけ   0.012 → 約35%
  /// 毎回起きると煩わしく、起きなさすぎると何のための餌台か分からない。
  double get _scareChance =>
      _hasRaptor ? 0.020 : (_hasAnimal ? 0.012 : 0.0);

  /// 鳥ID → いまいる枝(0=奥 b3, 1=b2, 2=手前 b1)
  final Map<String, int> branch = {};

  /// 手前の枝に留まっている歩数。2 で出会いが成立する(現行の b1Dwell と同じ)。
  final Map<String, int> _dwell = {};

  /// 今回の儀式で出会えた鳥。
  final Set<String> met = {};

  Timer? _tick;
  final Map<String, SoundHandle> _voices = {};
  bool running = false;

  Ritual(this.birdIds, this._rng,
      {this.chain = core.FeederChain.empty}) {
    for (final b in birdIds) {
      branch[b] = 0; // みんな奥から始まる
      _dwell[b] = 0;
    }
  }

  static const Duration step = Duration(milliseconds: 2500);
  /// **90秒で切り上げる。**(CEO 2026-08-18)
  ///
  /// ここまで終わりが無く、近づきも飛び去りもしないまま延々と続いていた。
  /// 「おなか一杯になったら飛んでいく」のと同じで、一定の敷居を置く。
  ///
  /// 90秒にした根拠: いまの歩き方(2.5秒ごと、前へ0.55/手前では0.45、
  /// 手前に2歩で成立)を2万回まわすと、出会いまでの中央値は22.5秒、
  /// 90%が57.5秒以内。**90秒で切っても97.8%は成立する。**
  /// 60秒だと91.7%まで落ちるので、待てば必ず会える感じが壊れる。
  ///
  /// ⚠️ **罰ではない。** 会えなくても図鑑も会った日数も減らない
  /// (原則2)。もう一度「耳を澄ます」を押せばやり直せる。
  static const int maxSteps = 36; // 36 × 2.5秒 = 90秒

  /// 何歩進んだか。
  int steps = 0;

  /// 時間切れで、会えないまま飛んでいった鳥。
  final Set<String> flewOff = {};

  /// 時間切れで終わったか(画面が「終わり方」を出し分ける)。
  bool timedOut = false;

  /// 直近に驚かされた種類。'squirrel' か 'hawk'。無ければ null。
  String? scare;

  /// 驚きが起きた歩数(絵の側が「いま起きた」を見分ける)。
  int scareAtStep = -1;

  /// 残り時間(秒)。急かす表示には使わない — **画面には出さない**。
  double get secondsLeft => (maxSteps - steps) * step.inMilliseconds / 1000;


  /// 始める。声を鳴らしながら、鳥が枝を移る。
  Future<void> start(void Function() onChange,
      {required String Function(String) assetOf}) async {
    if (running) return;
    running = true;
    for (final b in birdIds) {
      try {
        final src = await SoLoud.instance.loadAsset(assetOf(b));
        _voices[b] = SoLoud.instance.play(src, volume: 0.0, looping: true);
      } catch (_) {}
    }
    _tick = Timer.periodic(step, (_) => _hop(onChange));
    onChange();
  }

  /// 1歩ぶん動く。近づくほど声が大きくなる(近さがそのまま音になる)。
  void _hop(void Function() onChange) {
    steps++;

    // ── リスと鷹 ────────────────────────────────────────────
    // **餌台の連鎖から解いたものだけ**を使う(`feeder_chain`)。
    // 開放型の餌台にはリスが来て、リスが居ると鷹が来る。かご型なら来ない。
    // 実際に居るときだけ驚きが起きるので、餌台の選択がそのまま効く。
    //
    // ⚠️ **罰ではない。** 驚いても記録は何も減らない(原則2)。
    // 枝を下がるだけで、また近づいてくる。
    scare = null;
    if (_rng.nextDouble() < _scareChance) {
      scare = _hasRaptor ? 'hawk' : 'squirrel';
      scareAtStep = steps;
      for (final b in birdIds) {
        // 鷹は全部いちばん奥まで。リスは1つ下がるだけ。
        branch[b] = _hasRaptor ? 0 : ((branch[b] ?? 0) - 1).clamp(0, 2);
        _dwell[b] = 0;
      }
      _applyVolumes();
      onChange();
      return; // この歩は逃げるだけ。近づかない。
    }

    for (final b in birdIds) {
      final cur = branch[b] ?? 0;
      // 手前ほど来にくい。警戒心があるので、行きつ戻りつする。
      final forward = _rng.nextDouble() < (cur == 2 ? 0.45 : 0.55);
      var next = cur + (forward ? 1 : -1);
      next = next.clamp(0, 2);
      branch[b] = next;

      if (next == 2) {
        _dwell[b] = (_dwell[b] ?? 0) + 1;
        // 手前に2歩とどまったら「出会い」。
        if ((_dwell[b] ?? 0) >= 2) met.add(b);
      } else {
        _dwell[b] = 0;
      }
    }
    _applyVolumes();

    // ── 敷居 ───────────────────────────────────────────────
    // 90秒。会えなかった鳥は飛んでいく。**終わりを作るためであって、
    // 罰ではない。** もう一度押せばやり直せる。
    if (steps >= maxSteps) {
      timedOut = true;
      flewOff
        ..clear()
        ..addAll(birdIds.where((b) => !met.contains(b)));
      onChange();
      stop();
      return;
    }
    onChange();
  }

  /// 近さを音に反映する。
  void _applyVolumes() {
    for (final b in birdIds) {
      final h = _voices[b];
      if (h == null) continue;
      // 奥 0.20 / 中 0.45 / 手前 0.85
      const vol = [0.20, 0.45, 0.85];
      SoLoud.instance
          .fadeVolume(h, vol[branch[b] ?? 0], const Duration(milliseconds: 800));
    }
  }

  /// 終わる。声は切らずに沈める。
  void stop() {
    _tick?.cancel();
    _tick = null;
    running = false;
    for (final h in _voices.values) {
      SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 700));
      SoLoud.instance.scheduleStop(h, const Duration(milliseconds: 800));
    }
    _voices.clear();
  }

  /// 枝の番号を、絵の側の呼び名に直す。
  static String depthName(int b) => b >= 2 ? 'b1' : (b == 1 ? 'b2' : 'b3');
}
