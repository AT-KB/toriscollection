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
import 'package:toris_core/toris_core.dart' as core;

import 'sleep_mode.dart';

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

/// 観察回数から「近さ」を決める。`radio.py` の `_obs_to_depth` と同じ。
///
/// **よく会った鳥ほど手前で鳴く。** 警戒心が薄れて近くまで来る、という
/// 見立てで、会いに行くことがそのまま音の近さになる。
String obsToDepth(int count) {
  if (count >= 6) return 'b1'; // 手前・クリア
  if (count >= 3) return 'b2'; // 中間
  return 'b3'; // 遠景
}

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

  /// 何羽で鳴くか。観察回数で育つ(`toris_core` の flockSize)。
  /// いまは表示のみ。実際に重ねるのは現行 radio.py の群れ処理を移してから。
  final int flock;
  final Random _rng;

  AudioSource? _source;
  SoundHandle? _handle;
  Timer? _cycle;
  bool singing = false;

  BirdVoice(this.bird, this.depth, this._rng, {this.flock = 1});

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
    SoLoud.instance.fadeVolume(h, _peak * _scale, const Duration(milliseconds: 400));
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

  /// 眠りに落ちるときの減衰。1.0 で通常、0 で無音。
  double _scale = 1.0;

  void fadeScale(double k) {
    _scale = k;
    final h = _handle;
    if (h != null && singing) {
      SoLoud.instance.setVolume(h, _peak * _scale);
    }
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
  /// **顔ぶれはランダム**に選ぶ。ただし完全な平等ではなく、**よく会った鳥ほど
  /// 主役に出やすい**(現行 radio.py の base_w = 1.0 + count * 0.5 と同じ)。
  /// 近さ(奥行き)と群れの大きさも観察回数で決まる — よく会うほど警戒心が薄れ、
  /// 手前で、厚く鳴く。
  ///
  /// 共起ネットワークによる引き寄せ(ecology.pick_lineup)は、生態エンジンを
  /// 移してから足す。いまは基礎重みのぶんだけを写している。
  Future<void> load({Map<String, int> observed = const {}}) async {
    try {
      await SoLoud.instance.init();
      final all = await loadBirdAssets();
      final lineup = _pickLineup(all, observed);
      for (final b in lineup) {
        final count = observed[b.id] ?? 0;
        final v = BirdVoice(b, obsToDepth(count), _rng,
            flock: core.flockSize(b.id, count, const {}));
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

  /// 観察回数で重み付けした抽選。重み 1.0 + 回数 * 0.5(現行と同じ)。
  List<BirdAsset> _pickLineup(List<BirdAsset> all, Map<String, int> observed) {
    final pool = List<BirdAsset>.from(all);
    final out = <BirdAsset>[];
    while (out.length < kMaxBirds && pool.isNotEmpty) {
      final weights = [
        for (final b in pool) 1.0 + (observed[b.id] ?? 0) * 0.5
      ];
      final total = weights.fold<double>(0, (a, b) => a + b);
      var r = _rng.nextDouble() * total;
      var idx = pool.length - 1;
      for (var i = 0; i < pool.length; i++) {
        r -= weights[i];
        if (r <= 0) {
          idx = i;
          break;
        }
      }
      out.add(pool.removeAt(idx));
    }
    return out;
  }

  /// 眠りにつくまでの残り。null なら睡眠モードではない。
  Timer? _sleepTimer;
  Timer? _fadeTimer;
  DateTime? sleepEndsAt;

  void toggle(void Function() onChange) {
    if (!ready) return;
    running = !running;
    for (final v in birds) {
      running ? v.start(birds.length, onChange) : v.stop();
    }
    applyAmbience();
    // 画面が消えても鳴り続けるように、鳴っている間だけサービスを立てる。
    if (running) {
      RadioNative.startForeground();
    } else {
      cancelSleep();
      RadioNative.stopForeground();
      RadioNative.setBrightness(-1);
    }
    onChange();
  }

  /// 睡眠モードを始める。[minutes] 後に、最後の1分をかけて沈めて止める。
  void startSleep(int minutes, void Function() onChange) {
    cancelSleep();
    if (!running) toggle(onChange);
    sleepEndsAt = DateTime.now().add(Duration(minutes: minutes));
    final untilFade = Duration(minutes: minutes) - kFadeOut;
    _sleepTimer = Timer(untilFade.isNegative ? Duration.zero : untilFade, () {
      // 終わりは切らずに沈める。急に消えると、かえって目が覚める。
      _fadeOut(onChange);
    });
    // 画面は暗くするが、消すのは端末のスリープ時間に任せる。
    RadioNative.setBrightness(0.0);
    onChange();
  }

  void _fadeOut(void Function() onChange) {
    final steps = kFadeOut.inSeconds;
    final startVol = ambVol;
    var i = 0;
    _fadeTimer?.cancel();
    _fadeTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      i++;
      final k = (1 - i / steps).clamp(0.0, 1.0);
      ambVol = startVol * k;
      applyAmbience();
      for (final v in birds) {
        v.fadeScale(k);
      }
      if (i >= steps) {
        t.cancel();
        ambVol = startVol;
        if (running) toggle(onChange);
        sleepEndsAt = null;
        onChange();
      }
    });
  }

  void cancelSleep() {
    _sleepTimer?.cancel();
    _fadeTimer?.cancel();
    _sleepTimer = null;
    _fadeTimer = null;
    sleepEndsAt = null;
    for (final v in birds) {
      v.fadeScale(1.0);
    }
    RadioNative.setBrightness(-1);
  }

  /// 通知の「Stop」が押されていたら止める(画面を見ていなくても止められる)。
  Future<void> pollStopRequest(void Function() onChange) async {
    if (!running) return;
    if (await RadioNative.stopRequested()) {
      await RadioNative.clearStopRequest();
      toggle(onChange);
    }
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
    cancelSleep();
    RadioNative.stopForeground();
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
