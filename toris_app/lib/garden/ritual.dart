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

/// 儀式の1回ぶん。
class Ritual {
  final List<String> birdIds;
  final Random _rng;

  /// 鳥ID → いまいる枝(0=奥 b3, 1=b2, 2=手前 b1)
  final Map<String, int> branch = {};

  /// 手前の枝に留まっている歩数。2 で出会いが成立する(現行の b1Dwell と同じ)。
  final Map<String, int> _dwell = {};

  /// 今回の儀式で出会えた鳥。
  final Set<String> met = {};

  Timer? _tick;
  final Map<String, SoundHandle> _voices = {};
  bool running = false;

  Ritual(this.birdIds, this._rng) {
    for (final b in birdIds) {
      branch[b] = 0; // みんな奥から始まる
      _dwell[b] = 0;
    }
  }

  static const Duration step = Duration(milliseconds: 2500);

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

      final h = _voices[b];
      if (h != null) {
        // 奥 0.20 / 中 0.45 / 手前 0.85
        const vol = [0.20, 0.45, 0.85];
        SoLoud.instance.fadeVolume(
            h, vol[next], const Duration(milliseconds: 800));
      }
    }
    onChange();
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
