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

/// 奥行きごとのローパス。遠い鳥ほど高域が減って「奥」に聞こえる。
/// 現行 radio.py の D[].freq と同じ値。
const Map<String, double> kDepthFreq = {
  'b1': 12000, 'b2': 8000, 'b3': 4600,
};

/// 群れの重ね方(現行 radio.py の群れ処理と同じ)。
/// 同じ声をわずかにずらして重ね、左右に広げる。音源は増やさない。
const double kFlockDelayMin = 0.09;
const double kFlockDelayRange = 0.33;

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

/// 種データ(食べ物・気候・レア度)。`tools/export_data.py` が書き出したもの。
/// 判断のロジックは Dart に写すが、**データは写さない**(写し間違いを避ける)。
Future<Map<String, dynamic>> loadBirdsData() async {
  final raw = await rootBundle.loadString('assets/data/birds.json');
  return (jsonDecode(raw) as Map).cast<String, dynamic>();
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
  /// 群れの2羽目以降。同じ音源を少しずらして重ねる。
  final List<SoundHandle> _flockHandles = [];
  final List<double> _flockDelays = [];
  Timer? _cycle;
  bool singing = false;

  /// 左右の位置(-1..1)。3羽を均等に散らす。

  BirdVoice(this.bird, this.depth, this._rng, {this.flock = 1});

  double get _peak => kDepthGain[depth] ?? 1.0;

  double pan = 0.0;

  Future<void> load({bool reverb = true}) async {
    final s = await SoLoud.instance.loadAsset(bird.asset);
    _source = s;
    if (reverb) {
      s.filters.freeverbFilter.activate();
      s.filters.freeverbFilter.roomSize().value = 0.62;
      s.filters.freeverbFilter.damp().value = 0.45;
      s.filters.freeverbFilter.wet().value = kDepthWet[depth] ?? 0.1;
    }
    // 奥行きのローパス。遠い鳥ほど高域を落として奥に置く(現行の filter と同じ)。
    // ハイパス(820Hz)と存在感EQ(3.5kHz +5dB)は全鳥共通なので素材に焼いてある
    // — SoLoud は音源につき biquad を1つしか持てないため。
    s.filters.biquadFilter.activate();
    s.filters.biquadFilter.type().value = 0; // 0 = LOWPASS
    s.filters.biquadFilter.frequency().value = kDepthFreq[depth] ?? 4600;
    s.filters.biquadFilter.resonance().value = 0.7;

    _handle = SoLoud.instance.play(s, volume: 0, looping: true, paused: true);
    SoLoud.instance.setPan(_handle!, pan);

    // 群れ: 2羽目以降を、わずかに遅らせて左右に広げて重ねる。
    // 後ろの個体ほど小さく(現行の 0.55 - f*0.10)、左右へ ±(10+f*7) ぶん。
    for (var f = 1; f < flock; f++) {
      final h = SoLoud.instance.play(s, volume: 0, looping: true, paused: true);
      _flockHandles.add(h);
      _flockDelays.add(kFlockDelayMin + _rng.nextDouble() * kFlockDelayRange);
      final goff = (f.isOdd ? 1 : -1) * (10 + f * 7) / 50.0;
      SoLoud.instance.setPan(h, (pan + goff).clamp(-1.0, 1.0));
    }
  }

  double _flockGain(int f) => (0.55 - f * 0.10).clamp(0.0, 1.0);

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

    // 群れは本体と同じ場所から、決めたぶんだけ遅れて鳴く
    final posMs = SoLoud.instance.getPosition(h).inMilliseconds;
    for (var i = 0; i < _flockHandles.length; i++) {
      final fh = _flockHandles[i];
      final back = (posMs - (_flockDelays[i] * 1000).round());
      SoLoud.instance.setPause(fh, false);
      if (back > 0) {
        SoLoud.instance.seek(fh, Duration(milliseconds: back));
      }
      SoLoud.instance.fadeVolume(fh, _peak * _scale * _flockGain(i + 1),
          const Duration(milliseconds: 400));
    }
  }

  void _stopSinging(void Function() onChange) {
    singing = false;
    onChange();
    final h = _handle;
    if (h == null) return;
    // 止めずに音量だけ下げる(止めて作り直すと音声が増えていく)。
    SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 900));
    for (final fh in _flockHandles) {
      SoLoud.instance.fadeVolume(fh, 0, const Duration(milliseconds: 900));
    }
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
    for (final fh in _flockHandles) {
      SoLoud.instance.setVolume(fh, 0);
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
    for (final fh in _flockHandles) {
      SoLoud.instance.setVolume(fh, 0);
      SoLoud.instance.setPause(fh, true);
    }
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
  /// 種データ(食べ物・気候)。共起ネットワークの計算に使う。
  Map<String, dynamic> _birdsData = const {};

  /// 今日の顔ぶれのギルドのまとまり(2羽以上のギルドだけ、多い順)。
  List<core.GuildGroup> guildGroups = const [];

  /// 「なぜこの顔ぶれか」の一文。語れることが無ければ、共起の一般論を出す。
  String lineupStory = '';

  /// 鳥ID → 英名(ギルドのまとまりを描くのに使う)。
  String englishOf(String id) =>
      (_birdsData[id]?['english'] as String?) ?? id;

  /// どの土地のラジオを聴くか。**現行にも土地の選択がある**
  /// (`radio.py` は `biome_pref` で顔ぶれを絞る)。移植で落ちていた。
  String biomeId = 'charlotte';

  /// 土地を替える。鳴っていたら、いったん止めてから組み直す。
  Future<void> reload(String biome) async {
    if (biome == biomeId) return;
    final wasRunning = running;
    if (running) toggle(() {});
    for (final v in birds) {
      v.stop();
    }
    birds.clear();
    ready = false;
    await load(observed: _lastObserved, biomeId: biome);
    if (wasRunning && ready) toggle(() {});
  }

  Map<String, int> _lastObserved = const {};

  Future<void> load(
      {Map<String, int> observed = const {}, String? biomeId}) async {
    if (biomeId != null) this.biomeId = biomeId;
    _lastObserved = observed;
    try {
      await SoLoud.instance.init();
      _birdsData = await loadBirdsData();
      final all = await loadBirdAssets();
      final lineup = _pickLineup(all, observed);
      for (var i = 0; i < lineup.length; i++) {
        final b = lineup[i];
        final count = observed[b.id] ?? 0;
        final v = BirdVoice(b, obsToDepth(count), _rng,
            flock: core.flockSize(b.id, count, _birdsData));
        // 左右に均等配置(現行の left = 20 + i/(n-1) * 60 を -1..1 に写す)
        final t = lineup.length > 1 ? i / (lineup.length - 1) : 0.5;
        v.pan = ((20 + t * 60) - 50) / 50.0;
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

  /// 顔ぶれを選ぶ。**共起ネットワーク**に沿って選ぶ(現行 ecology.pick_lineup)。
  ///
  /// 種(seed)は基礎重み 1.0 + 観察回数 * 0.5 で選ぶ(よく会う鳥ほど主役に
  /// 出やすい)。以降は**すでに選ばれた鳥と一緒に見られやすい鳥**を引きやすくする。
  /// 関係は恣意的に足さず、食べ物と気候の重なりから出す(原則4「生態に誠実」)。
  List<BirdAsset> _pickLineup(List<BirdAsset> all, Map<String, int> observed) {
    final byId = {for (final b in all) b.id: b};
    // **その土地に居る鳥だけ**から選ぶ(`radio.py` の biome_birds と同じ)。
    // 絞らないと、シャーロットの庭で日本の鳥が鳴く。
    final ids = [
      for (final id in byId.keys)
        if (((_birdsData[id]?['biome_pref'] as List?) ?? const [])
            .map((e) => '$e')
            .contains(biomeId))
          id
    ];
    if (ids.isEmpty) return [];
    final chosen = core.pickLineup(
      ids, _birdsData, kMaxBirds, _rng.nextDouble,
      baseWeight: {for (final id in ids) id: 1.0 + (observed[id] ?? 0) * 0.5},
    );
    // 「なぜこの顔ぶれか」。共起モデルが言える範囲だけを語る(原則4)。
    final story = core.lineupStory(chosen, _birdsData);
    guildGroups = core.guildGroups(chosen, _birdsData);
    // 画面に出すのは**短い方**。長い方は現行の文のまま `stories.dart` にある。
    lineupStory = core.lineupStoryShort(story);
    return [for (final id in chosen) byId[id]!];
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
