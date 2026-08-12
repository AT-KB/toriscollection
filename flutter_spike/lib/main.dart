/// ステップ0: 音のスパイク — Flutter で「3羽が鳴くラジオ」だけを作る。
///
/// 目的は移行の可否を**耳で**決めること。提案書
/// `docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md` の §3 のとおり、
/// 他は一切触らず、いちばん危ない場所(音)だけを先に確かめる。
///
/// ## 現行版(radio.py の WebAudio)から何を写したか
/// - 鳥ごとの**鳴く/休むの状態機械**(RA_SING_MIN_S ほかの定数をそのまま持ってきた)
/// - 休符の長さを鳥数から決めて**同時発声を ~1.2 羽に保つ**式(restDuration)
/// - 鳴き始めに録音の**別の場所へ跳ぶ**(同じフレーズの繰り返しに聞こえないように)
/// - 立ち上がり/収まりの**フェード**、奥行き(b1/b2/b3)による音量差
/// - 環境音を1層、ループで重ねる
///
/// ## まだ写せていないもの(ここが移行の可否を決める)
/// - **ノイズゲート**と **AGC**: 現行は AnalyserNode で RMS を毎フレーム測って
///   無音時の雑音を絞り、録音ごとの音量差を吸収している。just_audio は再生器で
///   あって信号処理はできないため、同じことはできない。
/// - **リバーブ(畳み込み)**と観察回数による近さの変化。
/// これらは `flutter_soloud` のような音を自前で混ぜるエンジンが要る。
/// **この段階での聴き比べは「間・重なり・自然さ」までを見るもの**で、
/// 「録音の粗さが処理で消えているか」はまだ答えられない。
library;

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

void main() => runApp(const SpikeApp());

/// 現行版 radio.py の定数をそのまま持ってきている(BGMモードでない方)。
const double kSingMinS = 2.5;
const double kSingMaxS = 5.5;
const double kTargetActive = 1.2; // 同時に鳴いていてほしい羽数
const double kRestMinS = 2.5;
const double kRestMaxS = 20.0;

/// 奥行きごとの音量。現行の D.gain と同じ値。
const Map<String, double> kDepthGain = {'b1': 1.12, 'b2': 1.00, 'b3': 0.85};

class BirdSpec {
  final String id;
  final String name;
  final String asset;
  final String depth;

  /// 録音ごとの音量差を手で埋める係数(現行の AGC の代わり)。
  final double trim;

  const BirdSpec(this.id, this.name, this.asset, this.depth, this.trim);
}

const List<BirdSpec> kBirds = [
  BirdSpec('northern_cardinal', 'Northern Cardinal',
      'assets/birds/northern_cardinal.mp3', 'b2', 1.0),
  BirdSpec('american_robin', 'American Robin',
      'assets/birds/american_robin.mp3', 'b3', 1.0),
  BirdSpec('song_sparrow', 'Song Sparrow',
      'assets/birds/song_sparrow.mp3', 'b1', 0.9),
];

const Map<String, String> kAmbience = {
  'wind': 'assets/ambience/wind.mp3',
  'rain': 'assets/ambience/rain.mp3',
};

/// 環境音の「全開時」の音量。現行 radio.py の AMB_MAX と同じ考え方
/// (素材は -23 LUFS に揃えてあるので、ここは鳥に対する前後関係だけを決める)。
const Map<String, double> kAmbMax = {'wind': 1.10, 'rain': 1.00};

class SpikeApp extends StatelessWidget {
  const SpikeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Toris Radio Spike',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7BA87B)),
        useMaterial3: true,
      ),
      home: const RadioPage(),
    );
  }
}

/// 1羽ぶんの発声サイクル。鳴く→休む→鳴く…を自分で回す。
class BirdVoice {
  final BirdSpec spec;
  final AudioPlayer player = AudioPlayer();
  final Random _rng;

  bool singing = false;
  bool _loaded = false;
  Timer? _cycle;
  Timer? _fade;

  BirdVoice(this.spec, this._rng);

  double get _peak => (kDepthGain[spec.depth] ?? 1.0) * spec.trim;

  Future<void> load() async {
    await player.setAsset(spec.asset);
    await player.setLoopMode(LoopMode.one);
    await player.setVolume(0);
    _loaded = true;
  }

  /// 鳴き始め。録音の途中から入ることで、毎回おなじフレーズにならないようにする
  /// (現行の pickVariant + 群れのずらしに当たる部分)。
  Future<void> _startSinging(void Function() onChange) async {
    if (!_loaded) return;
    final dur = player.duration;
    if (dur != null && dur.inMilliseconds > 4000) {
      // 終端ぎりぎりから始めると一瞬で折り返すので、後ろ4秒は避ける
      final maxMs = dur.inMilliseconds - 4000;
      await player.seek(Duration(milliseconds: _rng.nextInt(maxMs)));
    }
    await player.play();
    singing = true;
    onChange();
    _rampTo(_peak, const Duration(milliseconds: 420));
  }

  Future<void> _stopSinging(void Function() onChange) async {
    singing = false;
    onChange();
    _rampTo(0, const Duration(milliseconds: 900), thenPause: true);
  }

  /// just_audio に音量の傾斜は無いので、自分で刻んで動かす。
  void _rampTo(double target, Duration over, {bool thenPause = false}) {
    _fade?.cancel();
    final from = player.volume;
    final steps = (over.inMilliseconds / 40).ceil();
    var i = 0;
    _fade = Timer.periodic(const Duration(milliseconds: 40), (t) {
      i++;
      final k = (i / steps).clamp(0.0, 1.0);
      player.setVolume(from + (target - from) * k);
      if (k >= 1.0) {
        t.cancel();
        if (thenPause) player.pause();
      }
    });
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

  /// テストから休符の式だけを確かめるための入口(音は鳴らさない)。
  @visibleForTesting
  double restDurationForTest(int n) => _restDuration(n);

  void run(int n, void Function() onChange) {
    _cycle?.cancel();
    // 出だしをずらして、3羽がいっせいに鳴き始めないようにする
    _cycle = Timer(Duration(milliseconds: _rng.nextInt(3000)), () {
      _loop(n, onChange);
    });
  }

  void _loop(int n, void Function() onChange) {
    _startSinging(onChange);
    final singMs = (_singDuration() * 1000).round();
    _cycle = Timer(Duration(milliseconds: singMs), () {
      _stopSinging(onChange);
      final restMs = (_restDuration(n) * 1000).round();
      _cycle = Timer(Duration(milliseconds: restMs), () => _loop(n, onChange));
    });
  }

  Future<void> stop() async {
    _cycle?.cancel();
    _fade?.cancel();
    singing = false;
    await player.pause();
    await player.setVolume(0);
  }

  Future<void> dispose() async {
    _cycle?.cancel();
    _fade?.cancel();
    await player.dispose();
  }
}

class RadioPage extends StatefulWidget {
  const RadioPage({super.key});

  @override
  State<RadioPage> createState() => _RadioPageState();
}

class _RadioPageState extends State<RadioPage> {
  final Random _rng = Random();
  final List<BirdVoice> _voices = [];
  final Map<String, AudioPlayer> _amb = {};
  final Map<String, bool> _ambOn = {for (final k in kAmbience.keys) k: false};

  bool _running = false;
  bool _ready = false;
  double _ambVol = 0.55;
  String _status = '読み込み中…';

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  Future<void> _prepare() async {
    try {
      for (final b in kBirds) {
        final v = BirdVoice(b, _rng);
        await v.load();
        _voices.add(v);
      }
      for (final e in kAmbience.entries) {
        final p = AudioPlayer();
        await p.setAsset(e.value);
        await p.setLoopMode(LoopMode.one);
        await p.setVolume(0);
        _amb[e.key] = p;
      }
      setState(() {
        _ready = true;
        _status = '3羽ぶんの録音と環境音2層を読み込んだ';
      });
    } catch (e) {
      setState(() => _status = '読み込みに失敗: $e');
    }
  }

  void _toggleRadio() {
    if (!_ready) return;
    setState(() => _running = !_running);
    if (_running) {
      for (final v in _voices) {
        v.run(_voices.length, () => setState(() {}));
      }
      _applyAmbience();
    } else {
      for (final v in _voices) {
        v.stop();
      }
      for (final p in _amb.values) {
        p.pause();
      }
    }
  }

  void _applyAmbience() {
    for (final e in _amb.entries) {
      final on = _ambOn[e.key] == true && _running;
      e.value.setVolume(on ? (kAmbMax[e.key] ?? 1.0) * _ambVol : 0);
      if (on) {
        e.value.play();
      } else {
        e.value.pause();
      }
    }
  }

  @override
  void dispose() {
    for (final v in _voices) {
      v.dispose();
    }
    for (final p in _amb.values) {
      p.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7FAF2),
      appBar: AppBar(
        title: const Text('音のスパイク — 3羽が鳴くラジオ'),
        backgroundColor: const Color(0xFFCFD9B8),
      ),
      body: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            FilledButton(
              onPressed: _ready ? _toggleRadio : null,
              child: Text(_running ? '■ 止める' : '🎙 ラジオを始める'),
            ),
            const SizedBox(height: 6),
            Text(_status, style: const TextStyle(fontSize: 12)),
            const SizedBox(height: 18),
            // いま鳴いている鳥が見えるようにする(重なり方を目でも確かめるため)
            ..._voices.map((v) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [
                    Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: v.singing
                            ? const Color(0xFF7AB040)
                            : const Color(0xFFD5DCC8),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(v.spec.name),
                    const SizedBox(width: 8),
                    Text('(${v.spec.depth})',
                        style: const TextStyle(
                            fontSize: 11, color: Color(0xFF5A7A5A))),
                  ]),
                )),
            const SizedBox(height: 22),
            const Text('環境音', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Row(
              children: kAmbience.keys.map((k) {
                final on = _ambOn[k] == true;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(k == 'wind' ? '🍃 Wind' : '🌧 Rain'),
                    selected: on,
                    onSelected: (_) {
                      setState(() => _ambOn[k] = !on);
                      _applyAmbience();
                    },
                  ),
                );
              }).toList(),
            ),
            Row(children: [
              const Text('🔈'),
              Expanded(
                child: Slider(
                  value: _ambVol,
                  onChanged: (v) {
                    setState(() => _ambVol = v);
                    _applyAmbience();
                  },
                ),
              ),
            ]),
            const Spacer(),
            const Text(
              'このスパイクに入っていないもの: ノイズゲート / AGC / リバーブ。\n'
              '録音の粗さを処理で消せるかは、次の段階(自前で音を混ぜるエンジン)で見る。',
              style: TextStyle(fontSize: 11, color: Color(0xFF5A7A5A)),
            ),
          ],
        ),
      ),
    );
  }
}
