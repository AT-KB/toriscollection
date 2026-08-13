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

  /// 読み込み時に**音声を1本だけ**作り、以後ずっと使い回す。
  ///
  /// 2026-08-13: 最初は「鳴くたびに play() して、休符で止める」形にしていた。
  /// これは止め損ねが起きると同じ録音が何重にも重なり、少しずつずれた複製が
  /// 干渉して**金属的な「キーン」**になり、しかも重なるほど大きくなる
  /// (CEO 試聴「フェード風にキーンってしてめちゃうるさかった」)。
  /// 数を増やさなければ、そもそも起こらない。鳴く/休むは**音量だけ**で表す。
  Future<void> load() async {
    final s = await SoLoud.instance.loadAsset(spec.asset);
    source = s;
    handle = SoLoud.instance
        .play(s, volume: 0, looping: true, paused: true);
  }

  /// 奥行き = 残響の深さ。近い鳥ほど乾いて、遠い鳥ほど森に溶ける。
  ///
  /// **freeverb は2チャンネルの音にしか使えない**(flutter_soloud の注記)。
  /// 素材をモノラルにしていたときは、ここで金属的な異音になった
  /// (2026-08-13 実機・CEO「キーン」「金属音」)。残響が深い鳥ほどひどく、
  /// 「なにか1つ音がおかしい」という聞こえ方になる。素材はステレオで用意すること。
  void setReverb(bool on) {
    final s = source;
    if (s == null) return;
    try {
      if (on) {
        s.filters.freeverbFilter.activate();
        s.filters.freeverbFilter.roomSize().value = 0.62;
        s.filters.freeverbFilter.damp().value = 0.45;
        s.filters.freeverbFilter.wet().value = kDepthWet[spec.depth] ?? 0.1;
      } else {
        s.filters.freeverbFilter.deactivate();
      }
    } catch (_) {
      // 既に同じ状態のときは例外になることがある。音を止める理由にはしない。
    }
  }

  /// 鳴き始め。録音の途中から入ることで、毎回おなじフレーズにならないようにする
  /// (現行の pickVariant + 群れのずらしに当たる部分)。
  void _startSinging(void Function() onChange) {
    final s = source;
    final h = handle;
    if (s == null || h == null) return;
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
    // 音声は止めない。音量を下げるだけ(止めて作り直すと数が増えていく)。
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

  /// テストから休符の式だけを確かめるための入口(音は鳴らさない)。
  @visibleForTesting
  double restDurationForTest(int n) => _restDuration(n);

  void run(int n, void Function() onChange) {
    _cycle?.cancel();
    final h = handle;
    if (h != null) {
      SoLoud.instance.setVolume(h, 0);
      SoLoud.instance.setPause(h, false);
    }
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

  /// ラジオを止める。音声は捨てず、黙らせて止めておく(次に始めるとき作り直さない)。
  void stop() {
    _cycle?.cancel();
    singing = false;
    final h = handle;
    if (h == null) return;
    SoLoud.instance.setVolume(h, 0);
    SoLoud.instance.setPause(h, true);
  }
}

class RadioPage extends StatefulWidget {
  const RadioPage({super.key});

  @override
  State<RadioPage> createState() => _RadioPageState();
}

class _RadioPageState extends State<RadioPage> {
  final Random _rng = Random();
  final List<BirdVoice> _birds = [];
  final Map<String, AudioSource> _ambSrc = {};
  final Map<String, SoundHandle> _ambHandle = {};
  final Map<String, Timer> _ambPause = {};
  final Map<String, bool> _ambOn = {'wind': true, 'rain': false};

  /// いま鳴っている音声の本数。増え続けていないかを目で見るために出す
  /// (重なりが「キーン」の正体だったので、再発したらここで分かる)。
  Timer? _voiceWatch;
  int _voices = 0;

  bool _running = false;
  bool _ready = false;
  double _ambVol = 0.55;
  String _status = '読み込み中…';

  /// 残響のオン/オフ。耳で切り分けられるように画面から切り替えられる。
  bool _reverb = true;

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
        v.setReverb(_reverb);
        _birds.add(v);
      }
      for (final e in kAmbience.entries) {
        final src = await SoLoud.instance.loadAsset(e.value);
        _ambSrc[e.key] = src;
        // 鳥と同じ理由で、環境音も音声は1層につき1本だけ作って使い回す。
        _ambHandle[e.key] =
            SoLoud.instance.play(src, volume: 0, looping: true, paused: true);
      }
      _voiceWatch = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        setState(() => _voices = SoLoud.instance.getActiveVoiceCount());
      });
      setState(() {
        _ready = true;
        _status = '掃除済みの録音3羽 + 環境音2層(SoLoud)';
      });
    } catch (e) {
      setState(() => _status = '読み込みに失敗: $e');
    }
  }

  void _toggleRadio() {
    if (!_ready) return;
    setState(() => _running = !_running);
    for (final v in _birds) {
      if (_running) {
        v.run(_birds.length, () => setState(() {}));
      } else {
        v.stop();
      }
    }
    _applyAmbience();
  }

  void _applyAmbience() {
    for (final key in kAmbience.keys) {
      final h = _ambHandle[key];
      if (h == null) continue;
      final want = _ambOn[key] == true && _running;
      final vol = (kAmbMax[key] ?? 1.0) * _ambVol;
      if (want) {
        SoLoud.instance.setPause(h, false);
        SoLoud.instance.fadeVolume(h, vol, const Duration(milliseconds: 1200));
      } else {
        SoLoud.instance.fadeVolume(h, 0, const Duration(milliseconds: 1200));
        // 止めるのはフェードが終わってから。音声そのものは捨てない。
        _ambPause[key]?.cancel();
        _ambPause[key] = Timer(const Duration(milliseconds: 1400), () {
          if (_ambOn[key] != true || !_running) {
            SoLoud.instance.setPause(h, true);
          }
        });
      }
    }
  }

  @override
  void dispose() {
    _voiceWatch?.cancel();
    for (final t in _ambPause.values) {
      t.cancel();
    }
    for (final v in _birds) {
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
            Text('$_status ・ 鳴っている音声 $_voices 本'
                '${_voices > 5 ? ' ← 増えすぎ' : ''}',
                style: TextStyle(
                    fontSize: 12,
                    color: _voices > 5 ? Colors.red : null)),
            const SizedBox(height: 18),
            // いま鳴いている鳥が見えるようにする(重なり方を目でも確かめるため)
            ..._birds.map((v) => Padding(
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
            const SizedBox(height: 10),
            // 残響を切って聴き比べられるようにしておく。異音が出たとき、
            // 残響のせいかどうかをその場で切り分けられる。
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('残響(奥行き)', style: TextStyle(fontSize: 14)),
              subtitle: const Text('切ると、加工した録音そのものの音になる',
                  style: TextStyle(fontSize: 11)),
              value: _reverb,
              onChanged: !_ready
                  ? null
                  : (v) {
                      setState(() => _reverb = v);
                      for (final b in _birds) {
                        b.setReverb(v);
                      }
                    },
            ),
            const SizedBox(height: 12),
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
