/// 庭のラジオの音を鳴らす部分。`toris_collection/radio.py` の WebAudio 実装の移植。
///
/// スパイク(`flutter_spike`)で確かめた作りをそのまま持ち込んでいる。移植で分かった
/// 大事なことが3つあり、どれも守らないと壊れる:
///
/// 1. **音声は1羽につき1本だけ作って使い回す。**
///    鳴くたびに play() すると止め損ねが積み上がり、同じ録音が何重にも重なって
///    金属的に膨らむ。鳴く/休むは**音量だけ**で表す。
/// 2. **残響(freeverb)は2チャンネルの音にしか使えない。**
///    モノラルの素材にかけると金属的な異音になる。同梱の録音はステレオで用意してある。
/// 3. **ノイズゲートと AGC は持ち込まない。**
///    録音を鳴らす前に済ませてある(`tools/bird_audio_prep.py`)。実時間で
///    やっていた処理が丸ごと不要になった。
library;

import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/services.dart';
import 'package:flutter_soloud/flutter_soloud.dart';

/// 現行版 radio.py の定数(BGMモードでない方)。数字は勝手に変えないこと。
const double kSingMinS = 2.5;
const double kSingMaxS = 5.5;
const double kTargetActive = 1.2; // 同時に鳴いていてほしい羽数
const double kRestMinS = 2.5;
const double kRestMaxS = 20.0;

/// ラジオで同時に鳴く種の上限。
/// 6種だと鳴きすぎて1羽ずつの声が聞き分けられず、庭の静けさとも合わなかった
/// (2026-08-11 に 6 -> 3 へ)。
const int kMaxBirds = 3;

/// 奥行きごとの音量と残響の深さ。現行の D(gain/wet) と同じ値。
const Map<String, double> kDepthGain = {'b1': 1.12, 'b2': 1.00, 'b3': 0.85};
const Map<String, double> kDepthWet = {'b1': 0.01, 'b2': 0.09, 'b3': 0.20};

/// 環境音。並び順がそのままタイルの並び。
const List<String> kAmbienceKeys = [
  'rain', 'wind', 'stream', 'waves', 'lake', 'fire', 'drips',
];

const Map<String, String> kAmbienceLabel = {
  'rain': '🌧 Rain',
  'wind': '🍃 Wind',
  'stream': '💧 Stream',
  'waves': '🌊 Waves',
  'lake': '🏞 Lake',
  'fire': '🔥 Fire',
  'drips': '🕳 Cave',
};

/// 全開時の音量。素材は -23 LUFS に揃えてあるので、ここは鳥に対する
/// 前後関係だけを決める(現行 radio.py の AMB_MAX と同じ値)。
const Map<String, double> kAmbMax = {
  'rain': 1.00, 'wind': 1.10, 'stream': 0.95, 'waves': 1.05,
  'lake': 1.00, 'fire': 0.90, 'drips': 0.70,
};

/// 同梱している鳥。`assets/birds/_credits.json` から読む
/// (音源を足したり差し替えたりしても、コードを触らずに反映される)。
class BirdAsset {
  final String id;
  final String english;
  final String scientific;
  const BirdAsset(this.id, this.english, this.scientific);

  String get asset => 'assets/birds/$id.mp3';
}

Future<List<BirdAsset>> loadBirdAssets() async {
  final raw = await rootBundle.loadString('assets/birds/_credits.json');
  final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
  return [
    for (final e in list)
      BirdAsset(e['id'] as String, (e['english'] ?? '') as String,
          (e['scientific'] ?? '') as String)
  ];
}

/// 1羽ぶんの発声サイクル。鳴く→休む→鳴く…を自分で回す。
class BirdVoice {
  final BirdAsset bird;
  final String depth;
  final Random _rng;

  AudioSource? _source;
  SoundHandle? _handle;
  Timer? _cycle;
  bool singing = false;

  BirdVoice(this.bird, this.depth, this._rng);

  double get _peak => kDepthGain[depth] ?? 1.0;

  Future<void> load({bool reverb = true}) async {
    final s = await SoLoud.instance.loadAsset(bird.asset);
    _source = s;
    if (reverb) {
      s.filters.freeverbFilter.activate();
      s.filters.freeverbFilter.roomSize().value = 0.62;
      s.filters.freeverbFilter.damp().value = 0.45;
      s.filters.freeverbFilter.wet().value = kDepthWet[depth] ?? 0.1;
    }
    _handle = SoLoud.instance.play(s, volume: 0, looping: true, paused: true);
  }

  void _startSinging(void Function() onChange) {
    final s = _source;
    final h = _handle;
    if (s == null || h == null) return;
    // 録音の途中から入る。毎回おなじフレーズにならないように。
    final len = SoLoud.instance.getLength(s);
    if (len.inMilliseconds > 6000) {
      SoLoud.instance.seek(
          h, Duration(milliseconds: _rng.nextInt(len.inMilliseconds - 5000)));
    }
    singing = true;
    onChange();
    SoLoud.instance.fadeVolume(h, _peak, const Duration(milliseconds: 400));
  }

  void _stopSinging(void Function() onChange) {
    singing = false;
    onChange();
    final h = _handle;
    if (h == null) return;
    // 止めずに音量だけ下げる(止めて作り直すと音声が増えていく)。
    SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 900));
  }

  double _singDuration() =>
      kSingMinS + _rng.nextDouble() * (kSingMaxS - kSingMinS);

  /// 休符。羽数が増えるほど長くして、同時発声を kTargetActive 前後に保つ。
  /// 式は現行 radio.py の restDuration() と同じ。
  double _restDuration(int n) {
    const avgSing = (kSingMinS + kSingMaxS) / 2;
    var r = avgSing * (n / kTargetActive - 1);
    r = r.clamp(kRestMinS, kRestMaxS);
    return r * (0.7 + _rng.nextDouble() * 0.6); // ±30% ばらす
  }

  void start(int n, void Function() onChange) {
    _cycle?.cancel();
    final h = _handle;
    if (h != null) {
      SoLoud.instance.setVolume(h, 0);
      SoLoud.instance.setPause(h, false);
    }
    // 出だしをずらす。いっせいに鳴き始めると不自然になる。
    _cycle = Timer(Duration(milliseconds: _rng.nextInt(3000)),
        () => _loop(n, onChange));
  }

  void _loop(int n, void Function() onChange) {
    _startSinging(onChange);
    _cycle =
        Timer(Duration(milliseconds: (_singDuration() * 1000).round()), () {
      _stopSinging(onChange);
      _cycle = Timer(Duration(milliseconds: (_restDuration(n) * 1000).round()),
          () => _loop(n, onChange));
    });
  }

  void stop() {
    _cycle?.cancel();
    singing = false;
    final h = _handle;
    if (h == null) return;
    SoLoud.instance.setVolume(h, 0);
    SoLoud.instance.setPause(h, true);
  }
}

/// ラジオ全体。鳥3羽と環境音7層を持つ。
class RadioEngine {
  final Random _rng = Random();
  final List<BirdVoice> birds = [];
  final Map<String, SoundHandle> _amb = {};
  final Map<String, Timer> _ambPause = {};
  final Map<String, bool> ambOn = {for (final k in kAmbienceKeys) k: k == 'wind'};

  bool ready = false;
  bool running = false;
  double ambVol = 0.55;
  String? error;

  /// 鳴らす顔ぶれを選んで読み込む。
  ///
  /// 本来は「会ったことのある鳥」から選ぶ(現行の pick_lineup)。生態エンジンを
  /// 移すまでの間は、同梱している中から重複なく選ぶ。
  Future<void> load({List<String>? onlyIds}) async {
    try {
      await SoLoud.instance.init();
      var all = await loadBirdAssets();
      if (onlyIds != null && onlyIds.isNotEmpty) {
        all = all.where((b) => onlyIds.contains(b.id)).toList();
      }
      all.shuffle(_rng);
      final lineup = all.take(kMaxBirds).toList();
      const depths = ['b2', 'b3', 'b1']; // 近さをばらけさせる
      for (var i = 0; i < lineup.length; i++) {
        final v = BirdVoice(lineup[i], depths[i % depths.length], _rng);
        await v.load();
        birds.add(v);
      }
      for (final k in kAmbienceKeys) {
        final src = await SoLoud.instance.loadAsset('assets/ambience/$k.mp3');
        _amb[k] = SoLoud.instance.play(src, volume: 0, looping: true, paused: true);
      }
      ready = true;
    } catch (e) {
      error = '$e';
    }
  }

  void toggle(void Function() onChange) {
    if (!ready) return;
    running = !running;
    for (final v in birds) {
      running ? v.start(birds.length, onChange) : v.stop();
    }
    applyAmbience();
    onChange();
  }

  void applyAmbience() {
    for (final k in kAmbienceKeys) {
      final h = _amb[k];
      if (h == null) continue;
      final want = ambOn[k] == true && running;
      if (want) {
        SoLoud.instance.setPause(h, false);
        SoLoud.instance.fadeVolume(
            h, (kAmbMax[k] ?? 1.0) * ambVol, const Duration(milliseconds: 1200));
      } else {
        SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 1200));
        _ambPause[k]?.cancel();
        _ambPause[k] = Timer(const Duration(milliseconds: 1400), () {
          if (ambOn[k] != true || !running) SoLoud.instance.setPause(h, true);
        });
      }
    }
  }

  /// いま鳴っている音声の本数。増え続けていたら作りを間違えている
  /// (鳥3 + 環境音7 = 10 で張り付くのが正しい)。
  int get voiceCount => ready ? SoLoud.instance.getActiveVoiceCount() : 0;

  void dispose() {
    for (final t in _ambPause.values) {
      t.cancel();
    }
    for (final v in birds) {
      v.stop();
    }
    if (ready) {
      try {
        SoLoud.instance.deinit();
      } catch (_) {}
    }
  }
}
