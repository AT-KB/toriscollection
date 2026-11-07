/// 目覚ましの**時間の関係**を固定する。
///
/// ## なぜこのファイルがあるか(2026-09-22)
/// 目覚ましの数字は Java 側(`BirdAlarmService.java`)にあり、**Dart のテストが
/// 一度も届いていなかった**(監査台帳の「目覚ましは1羽で始まり、他が加わる」が
/// ずっと未整備だったのはこれが理由)。
///
/// 2026-09-22 に「鳥の前に夜明け前の庭を1分置く」を足したことで、
/// RAMP / JOIN / AUTO_STOP の関係が動いた。**動いたので、ここで固定する。**
///
/// いちばん守りたいのは **「最大音量に達してから自動停止まで10分」**。
/// 競合(Dawn Chorus)が「1分で勝手にスヌーズする」で評価を落としているので、
/// この10分は1秒も削らないと決めてある(企画 B-5)。人が定数を書き換えたとき、
/// ここが機械で止める。
///
/// ⚠️ **Java を読んで数字を取り出している。** 式を写していないので、
/// Java 側を直せばここも一緒に動く。写すと、実装だけ直って試験が古いまま通る。
library;

import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

const _javaPath =
    'android/app/src/main/java/com/toriscollection/toris_app/BirdAlarmService.java';

/// `private static final long NAME = <式>;` を拾って数にする。
///
/// 式に出てよいのは、整数リテラル(`60_000L` / `0.35f`)と、
/// **先に定義された定数の名前**と、`* / +` だけ。
Map<String, double> _constants(String src) {
  final out = <String, double>{};
  final re = RegExp(
      r'private static final (?:long|float|int) ([A-Z][A-Z0-9_]*) = ([^;]+);');
  for (final m in re.allMatches(src)) {
    final name = m.group(1)!;
    final expr = m.group(2)!.replaceAll(RegExp(r'\s+'), '');
    final v = _eval(expr, out);
    if (v != null) out[name] = v;
  }
  return out;
}

double? _eval(String expr, Map<String, double> known) {
  var acc = 0.0;
  for (final term in expr.split('+')) {
    var cur = 1.0;
    // 左から順に * と / を適用する。
    final parts = RegExp(r'[*/]|[^*/]+').allMatches(term).map((m) => m.group(0)!);
    var op = '*';
    for (final p in parts) {
      if (p == '*' || p == '/') {
        op = p;
        continue;
      }
      final v = _atom(p, known);
      if (v == null) return null;
      cur = op == '*' ? cur * v : cur / v;
    }
    acc += cur;
  }
  return acc;
}

double? _atom(String tok, Map<String, double> known) {
  if (known.containsKey(tok)) return known[tok];
  final lit = tok.replaceAll('_', '').replaceAll(RegExp(r'[LfF]$'), '');
  return double.tryParse(lit);
}

void main() {
  final src = File(_javaPath).readAsStringSync();
  final k = _constants(src);

  test('Java の定数がちゃんと読めている(読めないと以下が全部素通りする)', () {
    // ⚠️ この試験が無いと、正規表現が空振りしたときに**全部 pass に見える**。
    for (final name in const [
      'RAMP_MS',
      'STEP_MS',
      'JOIN2_MS',
      'JOIN3_MS',
      'START_VOL',
      'AMB_PRE_MS',
      'AMB_FADE_MS',
      'AMB_PEAK',
      'AMB_BED',
      'AMB_DUCK_MS',
      'AUTO_STOP_MS',
    ]) {
      expect(k.containsKey(name), isTrue, reason: '$name を読み出せていない');
    }
    expect(k['RAMP_MS'], 5 * 60000.0);
    expect(k['AMB_PRE_MS'], 60000.0);
  });

  test('最大音量に達してから自動停止まで、きっかり10分ある', () {
    // **ここがこのファイルの本体。** 鳥は AMB_PRE_MS 後に入り、そこから
    // RAMP_MS かけて最大になる。自動停止は T から AUTO_STOP_MS。
    final maxAt = k['AMB_PRE_MS']! + k['RAMP_MS']!;
    final loud = k['AUTO_STOP_MS']! - maxAt;
    expect(loud, 10 * 60000.0,
        reason: '最大音量で鳴り続ける時間が10分から動いた。'
            '前置き(AMB_PRE_MS)を延ばしたなら AUTO_STOP_MS も同じだけ延ばすこと'
            '(企画 B-3 / B-5)。寝過ごし対策はここだけは緩めない');
  });

  test('前置きは、上がり切ってから保持する時間がある', () {
    // 「鳴り出したことが分かる」には、フェードインが終わってから
    // 一定の音量で保たれる時間が要る(企画 B-3: 40秒 + 20秒)。
    expect(k['AMB_FADE_MS']!, lessThan(k['AMB_PRE_MS']!),
        reason: 'フェードインが終わる前に鳥が入ると、前置きが前置きにならない');
    expect(k['AMB_PRE_MS']! - k['AMB_FADE_MS']!, 20000.0);
  });

  test('前置きの環境音は鳥の邪魔をしない: 入場後に必ず退き、最大時は鳥より下', () {
    expect(k['AMB_BED']!, lessThan(k['AMB_PEAK']!),
        reason: '鳥が入っても環境音が退かないと、さえずりがマスクされる'
            '(研究1: 起こす仕事をするのはメロディ)');
    expect(k['AMB_DUCK_MS']!, lessThanOrEqualTo(k['RAMP_MS']!),
        reason: '鳥が最大になるより後まで環境音が退き切らないのはおかしい');

    // ── 最大時の差を dB で見る ──
    // 素材は鳥 -19.0 LUFS / 環境音 -23.0 LUFS(`tools/bird_audio_prep.py`)。
    // 最大時は鳥の係数が 1.00、環境音が AMB_BED なので、実効の差は
    //   (-19.0) - (-23.0 + 20*log10(AMB_BED)) = 4.0 - 20*log10(AMB_BED)
    // **20dB 以上**空いていること。ここが埋まると研究1を裏切る。
    final gapDb = 4.0 - 20 * (log(k['AMB_BED']!) / ln10);
    expect(gapDb, greaterThan(20.0),
        reason: '起床の瞬間にさえずりが埋もれる(いまの差 '
            '${gapDb.toStringAsFixed(1)}dB)');
  });

  test('前置きの環境音は、実機で下げた値のまま(机上の計算に戻していない)', () {
    // 2026-09-22 19:00、実機(.dev)で鳴らして CEO が耳で確認。
    // 「雑音、つまり BGM が大きい気がするな音量」→ 0.35 → 0.20 / 0.18 → 0.09。
    // **机上の計算(-32.1 / -37.9 LUFS)より実機の耳を優先する。**
    // 戻したくなったら、まず実機で鳴らすこと。
    expect(k['AMB_PEAK'], closeTo(0.20, 1e-6),
        reason: '前置きは音楽ではなく気配。0.35 は実機で大きすぎた');
    expect(k['AMB_BED'], closeTo(0.09, 1e-6));
  });

  test('2羽目・3羽目はランプの 1/3・2/3 のまま(据え置き)', () {
    expect(k['JOIN2_MS'], closeTo(k['RAMP_MS']! / 3, 1.0));
    expect(k['JOIN3_MS'], closeTo(k['RAMP_MS']! * 2 / 3, 1.0));
    expect(k['JOIN3_MS']!, lessThan(k['RAMP_MS']!),
        reason: '最大音量に達したあとに加わる鳥がいるのは設計と違う');
  });

  test('前置きが読めなければ、鳥は遅れずに鳴く(目覚ましの信頼性)', () {
    // 企画 B-6-1。**前置きのせいで目覚ましが60秒遅れる、は絶対に作らない。**
    // `fromAsset` は例外を握って null を返すので、その null で分岐している。
    expect(src.contains('long birdDelay = 0L;'), isTrue,
        reason: '既定の遅延が0でないと、前置きが読めない朝に鳥が遅れる');
    expect(
        RegExp(r'if\s*\(ambience != null\)\s*\{[^}]*birdDelay = AMB_PRE_MS;')
            .hasMatch(src),
        isTrue,
        reason: '遅らせるのは、前置きが実際に読めたときだけであること');
  });

  test('前置きに使う音は、実際に同梱されている1層', () {
    // ⚠️ **アセット名を直書きしない。** Java の `AMB_ASSET` から取る。
    // 直書きすると、音を差し替えたときに試験が空振りする
    // (2026-09-22 に wind -> lake へ差し替えたときに実際そうなりかけた)。
    final m = RegExp(r'AMB_ASSET\s*=\s*\n?\s*"([^"]+)"').firstMatch(src);
    expect(m, isNotNull, reason: 'AMB_ASSET を読み出せていない');
    final path = m!.group(1)!;

    // Java は AssetManager 経由で読むので `flutter_assets/` の前置きが要る
    // (`BirdAlarmSounds.assetFor` と同じ)。
    expect(path.startsWith('flutter_assets/assets/ambience/'), isTrue,
        reason: '前置きは同梱の環境音から1層だけ選ぶ(企画 B-2)。'
            '前置きを間違えると、毎朝 fromAsset が null になって前置きが消える');
    final asset = path.substring('flutter_assets/'.length);
    expect(File(asset).existsSync(), isTrue,
        reason: '同梱していない音を指している($asset)。'
            '毎朝 fromAsset が null になり、前置きが丸ごと消える');

    // **1層だけ。** 重ねるとさえずり(2〜8kHz)をマスクする。
    expect(RegExp('AMB_ASSET').allMatches(src).length, 2,
        reason: 'AMB_ASSET の宣言と使用で2回のはず。'
            '増えていたら層を重ねていないか確かめること');
  });

  test('鳴っている鳥の名簿は、前置きのあいだ空のまま', () {
    // 企画 B-6-2。画面が「まだ鳴いていない鳥」を光らせないための歯止め(原則4)。
    // 前置きの環境音は鳥ではないので名簿に入れない。
    final from = src.indexOf('ambience = fromAsset(AMB_ASSET);');
    final to = src.indexOf('handler.postDelayed(() -> startBirds(chorus)');
    expect(from, greaterThan(0));
    expect(to, greaterThan(from),
        reason: '鳥の入場を遅らせる postDelayed が見つからない');
    expect(src.substring(from, to).contains('SINGING = java.util.Collections.emptyList();'),
        isTrue,
        reason: '前置きに入る前に名簿を空にしていない。'
            '前の朝の名簿が残ると、鳴っていない鳥が光る');

    // 名簿に足すのは、MediaPlayer を実際に作れたときだけ。
    expect(
        RegExp(r'players\.add\(first\);\s*\n\s*SINGING = java\.util\.Collections'
                r'\.singletonList\(chorus\[0\]\);')
            .hasMatch(src),
        isTrue,
        reason: '1羽目が読めなかったのに名簿に入れている');
  });
}
