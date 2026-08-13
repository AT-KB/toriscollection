/// ステップ0: 音のスパイク — Flutter で「3羽が鳴くラジオ」だけを作る。
///
/// 目的は移行の可否を**耳で**決めること。提案書
/// `docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md` の §3 のとおり、
/// 他は一切触らず、いちばん危ない場所(音)だけを先に確かめる。
///
/// ## 提案書が「移行の成否はここで決まる」と書いた処理を、どう解いたか
/// 現行の Web 版は再生しながら毎フレーム RMS を測って、ノイズゲート(無音時の
/// 暗騒音を絞る)と AGC(録音ごとの音量差を吸収)をかけている。これが radio.py で
/// いちばん複雑な部分で、移植の最大の壁だった。
///
/// この2つは**鳴らす前に済ませられる**。しかも事前処理なら実時間の制約が無いぶん、
/// ゲートより良い方法(FFT による暗騒音の除去)が使える。
///   実時間でやること   → 事前にやること(tools/bird_audio_prep.py)
///   ノイズゲート       → afftdn で暗騒音そのものを消す
///   AGC               → loudnorm で音量を測って揃える
/// つまり**移植が難しい処理ではなく、そもそも持ち込む必要のない処理**だった。
/// このスパイクの assets/birds は、その処理を通した後の録音である。
///
/// 残るリバーブ(奥行き)は SoLoud の freeverb でそのまま作れる。ここでは
/// 観察回数に当たる「近さ」(b1/b2/b3)を、音量と残響の深さで表している。
library;

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_soloud/flutter_soloud.dart';

void main() => runApp(const SpikeApp());

/// 現行版 radio.py の定数をそのまま持ってきている(BGMモードでない方)。
const double kSingMinS = 2.5;
const double kSingMaxS = 5.5;
const double kTargetActive = 1.2; // 同時に鳴いていてほしい羽数
const double kRestMinS = 2.5;
const double kRestMaxS = 20.0;

/// 奥行きごとの音量と残響の深さ。現行の D(gain/wet) と同じ値。
const Map<String, double> kDepthGain = {'b1': 1.12, 'b2': 1.00, 'b3': 0.85};
const Map<String, double> kDepthWet = {'b1': 0.01, 'b2': 0.09, 'b3': 0.20};

class BirdSpec {
  final String id;
  final String name;
  final String asset;
  final String depth;
  const BirdSpec(this.id, this.name, this.asset, this.depth);
}

const List<BirdSpec> kBirds = [
  BirdSpec('northern_cardinal', 'Northern Cardinal',
      'assets/birds/northern_cardinal.mp3', 'b2'),
  BirdSpec('american_robin', 'American Robin',
      'assets/birds/american_robin.mp3', 'b3'),
  BirdSpec('song_sparrow', 'Song Sparrow',
      'assets/birds/song_sparrow.mp3', 'b1'),
];

const Map<String, String> kAmbience = {
  'wind': 'assets/ambience/wind.mp3',
  'rain': 'assets/ambience/rain.mp3',
};

/// 環境音の「全開時」の音量。素材は -23 LUFS に揃えてあるので、ここは
/// 鳥に対する前後関係だけを決める(現行 radio.py の AMB_MAX と同じ考え方)。
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
  final Random _rng;
  AudioSource? source;
  SoundHandle? handle;

  bool singing = false;
  Timer? _cycle;

  BirdVoice(this.spec, this._rng);

  double get _peak => kDepthGain[spec.depth] ?? 1.0;

  Future<void> load() async {
    final s = await SoLoud.instance.loadAsset(spec.asset);
    source = s;
    // 奥行き = 残響の深さ。近い鳥ほど乾いて、遠い鳥ほど森に溶ける。
    s.filters.freeverbFilter.activate();
    s.filters.freeverbFilter.roomSize().value = 0.62;
    s.filters.freeverbFilter.damp().value = 0.45;
    s.filters.freeverbFilter.wet().value = kDepthWet[spec.depth] ?? 0.1;
  }

  /// 鳴き始め。録音の途中から入ることで、毎回おなじフレーズにならないようにする
  /// (現行の pickVariant + 群れのずらしに当たる部分)。
  void _startSinging(void Function() onChange) {
    final s = source;
    if (s == null) return;
    final h = SoLoud.instance.play(s, volume: 0, looping: true);
    handle = h;
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
    final h = handle;
    if (h == null) return;
    SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 900));
    // フェードが終わってから止める(途中で切ると「ブツッ」と鳴る)
    SoLoud.instance.scheduleStop(h, const Duration(milliseconds: 1000));
    handle = null;
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
    _cycle = Timer(Duration(milliseconds: _rng.nextInt(3000)),
        () => _loop(n, onChange));
  }

  void _loop(int n, void Function() onChange) {
    _startSinging(onChange);
    _cycle = Timer(Duration(milliseconds: (_singDuration() * 1000).round()), () {
      _stopSinging(onChange);
      _cycle = Timer(Duration(milliseconds: (_restDuration(n) * 1000).round()),
          () => _loop(n, onChange));
    });
  }

  void stop() {
    _cycle?.cancel();
    singing = false;
    final h = handle;
    if (h != null) SoLoud.instance.stop(h);
    handle = null;
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
  final Map<String, AudioSource> _ambSrc = {};
  final Map<String, SoundHandle> _ambHandle = {};
  final Map<String, bool> _ambOn = {'wind': true, 'rain': false};

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
      await SoLoud.instance.init();
      for (final b in kBirds) {
        final v = BirdVoice(b, _rng);
        await v.load();
        _voices.add(v);
      }
      for (final e in kAmbience.entries) {
        _ambSrc[e.key] = await SoLoud.instance.loadAsset(e.value);
      }
      setState(() {
        _ready = true;
        _status = '掃除済みの録音3羽 + 環境音2層(SoLoud)';
      });
    } catch (e) {
      setState(() => _status = '読み込みに失敗: $e');
    }
  }

  Future<void> _toggleRadio() async {
    if (!_ready) return;
    setState(() => _running = !_running);
    if (_running) {
      for (final v in _voices) {
        v.run(_voices.length, () => setState(() {}));
      }
      await _applyAmbience();
    } else {
      for (final v in _voices) {
        v.stop();
      }
      for (final h in _ambHandle.values) {
        SoLoud.instance.stop(h);
      }
      _ambHandle.clear();
    }
  }

  Future<void> _applyAmbience() async {
    for (final key in kAmbience.keys) {
      final want = _ambOn[key] == true && _running;
      final has = _ambHandle[key];
      final vol = (kAmbMax[key] ?? 1.0) * _ambVol;
      if (want && has == null) {
        final h =
            SoLoud.instance.play(_ambSrc[key]!, volume: 0, looping: true);
        _ambHandle[key] = h;
        SoLoud.instance.fadeVolume(h, vol, const Duration(milliseconds: 1200));
      } else if (want && has != null) {
        SoLoud.instance.setVolume(has, vol);
      } else if (!want && has != null) {
        SoLoud.instance.fadeVolume(has, 0, const Duration(milliseconds: 1200));
        SoLoud.instance.scheduleStop(has, const Duration(milliseconds: 1300));
        _ambHandle.remove(key);
      }
    }
  }

  @override
  void dispose() {
    for (final v in _voices) {
      v.stop();
    }
    // 初期化できていない環境(ネイティブ音声ライブラリの無いテスト実行など)で
    // deinit を呼ぶと、画面を畳む途中で落ちる。立ち上がっていた時だけ止める。
    if (_ready) {
      try {
        SoLoud.instance.deinit();
      } catch (_) {}
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
                    Text('${v.spec.depth} · 残響 '
                        '${((kDepthWet[v.spec.depth] ?? 0) * 100).round()}%',
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
              'ゲートとAGCは実時間でやらず、録音を鳴らす前に済ませてある。\n'
              '残響は SoLoud の freeverb。奥行き(b1/b2/b3)で深さを変えている。',
              style: TextStyle(fontSize: 11, color: Color(0xFF5A7A5A)),
            ),
          ],
        ),
      ),
    );
  }
}
