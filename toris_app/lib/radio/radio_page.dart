/// 庭のラジオの画面。現行版(Streamlit)の `radio.py` が描いているものに当たる。
///
/// 表示は**英語のみ**。文字は少なく、押すものは大きく(`ui/theme.dart`)。
/// 説明を足したくなったら、まず作りを疑う。
library;

import 'dart:async';

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'radio_engine.dart';
import 'sleep_mode.dart';

class RadioPage extends StatefulWidget {
  /// 会った回数。よく会った鳥ほど主役に出やすく、近くで、厚く鳴く。
  final Map<String, int> observed;

  /// 庭の土地。ラジオの既定の土地になる(現行と同じ)。
  final String biomeId;

  const RadioPage(
      {super.key, this.observed = const {}, this.biomeId = 'charlotte'});

  @override
  State<RadioPage> createState() => _RadioPageState();
}

class _RadioPageState extends State<RadioPage>
    with AutomaticKeepAliveClientMixin {
  final RadioEngine _engine = RadioEngine();
  Timer? _watch;

  @override
  bool get wantKeepAlive => true; // タブを移っても鳴らし続ける

  @override
  void initState() {
    super.initState();
    // 覚えていた環境音の設定を戻してから読み込む(順番を逆にすると、
    // 既定の「Wind だけ」で鳴り始めてから切り替わる)。
    _engine.restorePrefs().then((_) => _engine
            .load(observed: widget.observed, biomeId: widget.biomeId))
        .then((_) {
      if (mounted) setState(() {});
    });
    _watch = Timer.periodic(const Duration(seconds: 2), (_) {
      // 通知の「Stop」でも止められるように見張る(画面を見ていなくても止まる)
      _engine.pollStopRequest(() {
        if (mounted) setState(() {});
      });
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _watch?.cancel();
    _engine.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final e = _engine;
    return Scaffold(
      appBar: AppBar(title: const Text('Garden radio')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          // ── どの土地のラジオを聴くか ──
          // 現行にもある(`radio.py` は選んだ土地の鳥だけを鳴らす)。
          // 既定は自分の庭の土地。別の土地の声も聴ける。
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'charlotte', label: Text('Charlotte')),
              ButtonSegment(value: 'kyoto', label: Text('Kyoto')),
            ],
            selected: {e.biomeId},
            onSelectionChanged: (v) async {
              await _engine.reload(v.first);
              if (mounted) setState(() {});
            },
          ),
          const SizedBox(height: 18),

          // ⚠️ ここに「今の庭(いま庭に居る鳥)」を置いてはいけない。
          // ラジオの顔ぶれは共起ネットワークからの抽選で、**庭に居る鳥とは無関係**。
          // 並べると「これから鳴く鳥」に読めてしまい、嘘になる
          // (CEO 2026-08-15「そこの Jay いたけど、ラジオにはいない」)。
          // 今の庭は庭のタブにある。

          // ── 主役: 鳴らす/止める ──
          //
          // **まだ誰にも会っていないうちは鳴らせない。** ラジオは会った鳥で
          // できているので(`radio.py` 冒頭「観察した鳥だけが鳴く」)、
          // 空のまま Listen を出すと、押しても何も起きないか、会っていない鳥が
          // 鳴いてしまう。文言は出荷済みの英語をそのまま使う。
          if (e.ready && e.birds.isEmpty)
            Text(
              'Once you meet birds in '
              '${widget.biomeId == 'kyoto' ? 'Kyoto' : 'Charlotte'}, '
              "you can hear their voices here.",
              style: const TextStyle(fontSize: 15, height: 1.4, color: kSub),
            )
          else
            FilledButton.icon(
              onPressed:
                  e.ready ? () => _engine.toggle(() => setState(() {})) : null,
              icon: Icon(
                  e.running ? Icons.stop_rounded : Icons.play_arrow_rounded,
                  size: 30),
              label: Text(e.running ? 'Stop' : 'Listen'),
            ),
          if (e.error != null) ...[
            const SizedBox(height: 8),
            Text(e.error!,
                style: const TextStyle(fontSize: 12, color: Colors.red)),
          ],
          const SizedBox(height: 22),

          // ── いま鳴いている鳥 ──
          // 近さ(b1/b2/b3)と群れの数は、よく会うほど育つ。
          ...e.birds.map((v) => _BirdRow(v)),

          // ── なぜこの顔ぶれか ──
          // **一行だけ。** ギルドごとの内訳は出さない — 鳥の名前は上に
          // 並んでいるので、繰り返すと文字が増えるだけだった
          // (CEO 2026-08-16「文字多くて読みにくい。もっと少なく、大きく」)。
          if (e.birds.isNotEmpty && e.lineupStory.isNotEmpty) ...[
            const SizedBox(height: 18),
            Text(e.lineupStory,
                style: const TextStyle(
                    fontSize: 16, height: 1.3, color: kInk)),
          ],
          const SizedBox(height: 26),

          _SectionLabel('Ambience'),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final k in kAmbienceKeys)
                FilterChip(
                  label: Text(kAmbienceLabel[k] ?? k),
                  selected: e.ambOn[k] == true,
                  onSelected: (on) {
                    setState(() => e.ambOn[k] = on);
                    e.applyAmbience();
                    e.savePrefs();  // 触ったら覚える
                  },
                ),
            ],
          ),
          Row(children: [
            const Icon(Icons.volume_up_rounded, color: kSub),
            Expanded(
              child: Slider(
                value: e.ambVol,
                onChanged: (v) {
                  setState(() => e.ambVol = v);
                  e.applyAmbience();
                },
                // つまみは動かしている間ずっと呼ばれる。**離した時だけ**書く。
                onChangeEnd: (_) => e.savePrefs(),
              ),
            ),
          ]),
          const SizedBox(height: 18),

          // ── 睡眠モード ──
          _SectionLabel('Sleep'),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final m in kSleepMinutes)
                ChoiceChip(
                  label: Text('$m min'),
                  selected: false,
                  onSelected: e.ready
                      ? (_) => e.startSleep(m, () => setState(() {}))
                      : null,
                ),
              if (e.sleepEndsAt != null)
                ActionChip(
                  avatar: const Icon(Icons.close_rounded, size: 18),
                  label: Text(
                      'Until ${TimeOfDay.fromDateTime(e.sleepEndsAt!).format(context)}'),
                  onPressed: () => setState(() => e.cancelSleep()),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(text,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
                color: kSub)),
      );
}

/// 1羽ぶんの行。鳴いている間だけ色がつく。
class _BirdRow extends StatelessWidget {
  final BirdVoice v;
  const _BirdRow(this.v);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 400),
          width: 14,
          height: 14,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: v.singing ? kGreen : const Color(0xFFDCE3D4),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Text(v.bird.english,
              style: const TextStyle(fontSize: 17, color: kInk)),
        ),
        // 群れが育っている鳥だけ羽数を出す(1羽のときは何も出さない)
        if (v.flock > 1)
          Text('×${v.flock}',
              style: const TextStyle(fontSize: 14, color: kSub)),
      ]),
    );
  }
}
