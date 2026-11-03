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
    // 3つのスタイルを毎回シャッフルして先頭から配る。
    // **3羽以下なら必ず全員ちがうスタイル**になる(4羽以上は i mod 3)。
    final deck = [...HopStyle.all]..shuffle(_rng);
    for (var i = 0; i < birdIds.length; i++) {
      final b = birdIds[i];
      branch[b] = 0; // みんな奥から始まる
      _dwell[b] = 0;
      style[b] = deck[i % deck.length];
    }
  }

  static const Duration step = Duration(milliseconds: 2500);

  /// 時計の刻み。**1歩の長さ(`step`)より細かく回す。**
  ///
  /// ⚠️ **なぜ細かくするか**(CEO 2026-08-28「鳥たちが同時に動くのがなんか
  /// いけてない。実際の鳥みたいに、動くのランダムにできない?」)。
  ///
  /// 前は `Timer.periodic(step)` が1本だけで、**その1回で全羽をまとめて
  /// 動かしていた**。だから3羽が2.5秒ごとに一斉に跳ぶ。時計仕掛けに見える。
  ///
  /// いまは 250ms で回し、**鳥ごとに自分の番が来た時だけ**跳ぶ。
  static const Duration tickInterval = Duration(milliseconds: 250);

  /// 1歩ぶんが何刻みか(2500 / 250 = 10)。
  static const int ticksPerStep = 10;

  /// 鳥ごとの**歩き方(スタイル)**。`_styleOf` で1羽ずつ割り当てる。
  ///
  /// ⚠️ **ここが 2026-09-22 の直しの本体。** 位相をずらすだけでは足りない
  /// (企画『2026-09-22_実機4件_仕様』A-0 の実測: 現行は既に「一斉」ではないが、
  /// 3羽とも周期が同じ 2.5秒なので、目は「同じ拍」として拾う)。
  /// **周期そのものを鳥ごとに変える。**
  final Map<String, HopStyle> style = {};

  /// 時計が何刻み進んだか。`steps`(1歩=10刻み)とは別。
  int _ticks = 0;

  /// 鳥ごとの「次に跳ぶ刻み」。**始まりの位相を鳥ごとにずらす**ので、
  /// 最初から一斉には動かない。
  final Map<String, int> _nextHopTick = {};
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
  ///
  /// ⚠️ **2026-11-03 に 120秒へ延ばした**(CEO「テンポが速すぎる、もうちょっと
  /// ゆっくり」)。歩くのを遅くすると 90秒で打てる歩数が減り、いちばん遅い鳥で
  /// 成立率が 94.3% まで落ちる。120秒なら 98.0% で、**最悪ケースが前と同じ**。
  static const int maxSteps = 48; // 48 × 2.5秒 = 120秒

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
    // 最初に跳ぶ刻みは、スタイルの基本間隔ぶんの幅から引く。
    for (final b in birdIds) {
      _nextHopTick[b] = _styleOf(b).firstHop(_rng);
    }
    _tick = Timer.periodic(tickInterval, (_) => _onTick(onChange));
    onChange();
  }

  /// 時計の1刻み。**鳥ごとに、自分の番が来た時だけ動かす。**
  void _onTick(void Function() onChange) {
    _ticks++;
    var changed = false;

    // ── 1歩ぶんの節目 ──────────────────────────────────────
    // 驚き(リス・鷹)と、90秒の敷居は**全体の時計**で数える。
    // 鳥ごとに数えると、羽数のぶんだけ驚きの回数が増えてしまう。
    if (_ticks % ticksPerStep == 0) {
      steps++;
      if (_scare(onChange)) return;   // 逃げる歩。近づかない
      changed = true;
    }

    // ── 鳥ごとの1歩 ────────────────────────────────────────
    for (final b in birdIds) {
      if (_ticks < (_nextHopTick[b] ?? 0)) continue;
      _hopOne(b);
      // 次に跳ぶのは、その鳥のスタイルが決める。
      _nextHopTick[b] = _styleOf(b).nextHop(_rng, _ticks);
      changed = true;
    }

    if (changed) {
      _applyVolumes();
    }

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
    if (changed) onChange();
  }

  /// 驚き。起きたら true(その歩は誰も近づかない)。
  bool _scare(void Function() onChange) {
    // ── リスと鷹 ────────────────────────────────────────────
    // **餌台の連鎖から解いたものだけ**を使う(`feeder_chain`)。
    // 開放型の餌台にはリスが来て、リスが居ると鷹が来る。かご型なら来ない。
    // 実際に居るときだけ驚きが起きるので、餌台の選択がそのまま効く。
    //
    // ⚠️ **罰ではない。** 驚いても記録は何も減らない(原則2)。
    // 枝を下がるだけで、また近づいてくる。
    //
    // ⚠️ **驚きだけは全羽まとめて動く。** 鷹が出たら1羽ずつ気づくのは
    // おかしいので、ここは同時でよい(CEO の指摘は「近づき方が揃っている」
    // ことだった)。
    scare = null;
    if (_rng.nextDouble() >= _scareChance) return false;

    scare = _hasRaptor ? 'hawk' : 'squirrel';
    scareAtStep = steps;
    for (final b in birdIds) {
      // 鷹は全部いちばん奥まで。リスは1つ下がるだけ。
      branch[b] = _hasRaptor ? 0 : ((branch[b] ?? 0) - 1).clamp(0, 2);
      _dwell[b] = 0;
      // 驚いた直後も**同じ式**で掛け直す。全羽が同じ式だと、驚いたあとに
      // 周期が揃ってしまう(企画の仕様 A-2)。
      _nextHopTick[b] = _styleOf(b).nextHop(_rng, _ticks);
    }
    _applyVolumes();
    onChange();
    return true;
  }

  /// その鳥の歩き方。割り当てが無ければ steady(ふつう)。
  HopStyle _styleOf(String b) => style[b] ?? HopStyle.steady;

  /// 1羽ぶんの1歩。近づくほど声が大きくなる(近さがそのまま音になる)。
  ///
  /// **確率は前と1つも変えていない** — 手前へ 0.45 / それ以外 0.55、
  /// 手前に2歩とどまったら出会い。変えたのは**いつ動くか**だけ。
  void _hopOne(String b) {
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

/// 鳥1羽ぶんの**歩き方**。「いつ跳ぶか」だけを決める。
///
/// ## なぜスタイルを分けたか(CEO 2026-08-28 / 企画 2026-09-22)
/// 8/28 に「鳥ごとに自分の番が来た時だけ跳ぶ」に直したが、CEO はまだ
/// 「同時」と感じていた。企画部が2万回まわして数えたところ、**同じ刻みで
/// 2羽以上が跳ぶのは90秒に 10.1回**しかなく、既に一斉ではない。
/// それでも時計仕掛けに見えるのは、**3羽の周期が全員おなじ 2.5秒**だから。
/// 同じテンポの振り子が3つ並んでいると、目は「同じ拍」として拾う。
///
/// → 直すのは位相ではなく**周期**。quick と calm は1歩ごとに必ず 0.5秒ずつ
/// 開き、5歩で1周期(2.5秒)ぶんずれて、そのまま回り続ける。
///
/// ## 数字の根拠(企画『2026-09-22_実機4件_仕様』A-1 / A-3、2万回の実測)
/// 制約は「90秒で出会いが成立する割合を 97.8% から実質下げないこと」。
/// 効くのは**90秒のあいだに何歩打てるか**だけなので、
/// **どのスタイルも実効平均を 2.50秒より遅くしない**。
/// 遅い鳥を作るのではなく、**速い鳥を作る**ことで差をつける。
///
/// ## 2026-11-03 に作り直した(CEO「テンポが速すぎる」「1こは2秒に1回、
/// 1こは2.5秒に1回みたいにバラバラに」)
///
/// 前の3種は 2.24 / 2.40 / 2.50秒で、**差が小さすぎて同じ拍に見えた**。
/// ゆらぎ(±0.5〜1秒)も大きく、拍の違いが埋もれていた。
/// いまは**拍そのものをはっきり離し、ゆらぎは ±0.25秒に絞る**。
///
/// | | base | jitter | 立ち止まり | 拍 | 120秒の歩数 | 成立率 |
/// |---|---|---|---|---|---|---|
/// | quick  | 8  | ±1 | 0.15 / +6 | 2.0秒  | 54.0歩 | 99.6% |
/// | steady | 11 | ±1 | 0.10 / +6 | 2.75秒 | 41.4歩 | 98.9% |
/// | calm   | 13 | ±1 | —         | 3.25秒 | 36.9歩 | 98.0% |
///
/// 遅くした代わりに敷居を 120秒に延ばした(`maxSteps`)。いちばん遅い calm が
/// 前の最悪(97.75%)と同じなので、**待てば会える感じは痩せていない**(原則2)。
///
/// ⚠️ **スタイルは種(species)に固定しない。** 種ごとに歩き方を決めると
/// 「この種はこう歩く」という**データの裏づけが無い主張**をアプリが出すことに
/// なる(原則4「生態に誠実」)。**その回のその1羽の気分**として毎回配り直す。
class HopStyle {
  /// 見分けるための名前(試験と記録用。画面には出さない)。
  final String name;

  /// 基本間隔(刻み)。1刻み = 250ms。
  final int base;

  /// ゆらぎ(±刻み)。
  final int jitter;

  /// ときどき立ち止まる確率。
  ///
  /// 小鳥の実際の動きは「素早く数歩 → ぴたりと止まって周りを見る」。
  /// **速い鳥にだけ付ける** — 歩数に余裕があるので、止まりの代金を
  /// 成立率で払わずに済む。calm に足すと 96.92% まで落ちるので足さない。
  final double pauseChance;

  /// 立ち止まる長さ(刻み)。
  final int pauseTicks;

  const HopStyle(
      this.name, this.base, this.jitter, this.pauseChance, this.pauseTicks);

  /// せっかち。2秒に1回(1.75〜2.25秒。ときどき 1.5秒ほど立ち止まる)。
  static const HopStyle quick = HopStyle('quick', 8, 1, 0.15, 6);

  /// ふつう。2.75秒に1回(2.5〜3.0秒。ときどき立ち止まる)。
  static const HopStyle steady = HopStyle('steady', 11, 1, 0.10, 6);

  /// のんびり。3.25秒に1回(3.0〜3.5秒)。
  static const HopStyle calm = HopStyle('calm', 13, 1, 0.0, 0);

  static const List<HopStyle> all = [quick, steady, calm];

  /// 最初に跳ぶ刻み。1〜base。
  int firstHop(Random r) => 1 + r.nextInt(base);

  /// 次に跳ぶ刻み。**下限は1刻み**(必ず前に進む)。
  int nextHop(Random r, int now) {
    var d = base + r.nextInt(jitter * 2 + 1) - jitter;
    if (r.nextDouble() < pauseChance) d += pauseTicks;
    if (d < 1) d = 1;
    return now + d;
  }

  @override
  String toString() => 'HopStyle($name)';
}
