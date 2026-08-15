/// 庭のラジオの画面。現行版(Streamlit)の `radio.py` が描いているものに当たる。
///
/// 表示は**英語のみ**。製品版は 2026-08-09 に日本語表示を落としている。
/// 文言は `i18n.py` の TRANSLATIONS にある出荷済みの英語をそのまま使う。
library;

import 'dart:async';

import 'package:flutter/material.dart';

import 'radio_engine.dart';
import 'sleep_mode.dart';

class RadioPage extends StatefulWidget {
  const RadioPage({super.key});

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
    _engine.load().then((_) {
      if (mounted) setState(() {});
    });
    _watch = Timer.periodic(const Duration(seconds: 2), (_) {
      // 通知の「Stop」で止められるようにする(画面を見ていなくても止まる)
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
      backgroundColor: const Color(0xFFF7FAF2),
      appBar: AppBar(
        title: const Text('🎙 Garden radio'),
        backgroundColor: const Color(0xFFCFD9B8),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            'Every bird you have ever met sings here — even the ones that '
            'left the garden.',
            style: TextStyle(color: Colors.grey.shade700, height: 1.5),
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: e.ready ? () => _engine.toggle(() => setState(() {})) : null,
            icon: Icon(e.running ? Icons.stop : Icons.mic),
            label: Text(e.running ? 'Stop' : 'Start the radio'),
          ),
          const SizedBox(height: 8),
          Text(
            e.error != null
                ? 'Could not start audio: ${e.error}'
                : (e.ready
                    ? '${e.birds.length} birds · ${e.voiceCount} voices'
                    : 'Loading…'),
            style: TextStyle(
                fontSize: 12,
                color: e.error != null ? Colors.red : Colors.grey.shade600),
          ),
          const SizedBox(height: 18),

          // いま鳴いている鳥。重なり方が目でも分かるようにする。
          ...e.birds.map((v) => Padding(
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
                  Expanded(child: Text(v.bird.english)),
                  Text(v.depth,
                      style: const TextStyle(
                          fontSize: 11, color: Color(0xFF5A7A5A))),
                ]),
              )),

          const SizedBox(height: 24),
          const Text('Ambience',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: kAmbienceKeys.map((k) {
              final on = e.ambOn[k] == true;
              return ChoiceChip(
                label: Text(kAmbienceLabel[k] ?? k),
                selected: on,
                onSelected: (_) {
                  setState(() => e.ambOn[k] = !on);
                  e.applyAmbience();
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 20),

          // ── 睡眠モード ──
          // Streamlit では作れなかった機能。画面を消しても鳴り続け、
          // 決めた時間で静かに沈んで止まる。
          const Text('Fall asleep to the garden',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(
            e.sleepEndsAt == null
                ? 'The screen dims and the birds keep singing. '
                  'They fade away on their own.'
                : 'Fading away at '
                  '${TimeOfDay.fromDateTime(e.sleepEndsAt!).format(context)}',
            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: [
              for (final m in kSleepMinutes)
                ChoiceChip(
                  label: Text('$m min'),
                  selected: false,
                  onSelected:
                      e.ready ? (_) => e.startSleep(m, () => setState(() {})) : null,
                ),
              if (e.sleepEndsAt != null)
                ActionChip(
                  label: const Text('Cancel'),
                  onPressed: () => setState(() => e.cancelSleep()),
                ),
            ],
          ),
          const SizedBox(height: 16),

          Row(children: [
            const Text('🔈'),
            Expanded(
              child: Slider(
                value: e.ambVol,
                onChanged: (v) {
                  setState(() => e.ambVol = v);
                  e.applyAmbience();
                },
              ),
            ),
          ]),
        ],
      ),
    );
  }
}
