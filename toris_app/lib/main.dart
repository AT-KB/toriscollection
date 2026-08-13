/// Toris Collection — Flutter 版(移行中)。
///
/// ## なぜ Flutter に移るのか
/// 現行版は Streamlit を WebView で包んだ構成で、**通知・目覚まし・端末連携が
/// 原理的に作れない**。目覚ましは仕方なくネイティブ Java で書き、WebView から
/// JavaScript 経由で叩いていた。今後「通知」「睡眠データ」「ウィジェット」に
/// 触れるたび同じ壁が来る。判断の根拠は
/// `toris_collection/docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md`。
///
/// ## いまの段階(A案: 目的直行)
/// 移行の目的そのもの — **目覚ましと通知** — を最初に成立させる。
/// 図鑑・庭・ラジオは現行版が動いているので後回し。
/// 鳴らすネイティブ側(`BirdAlarmService` ほか)は Capacitor 版からそのまま移した
/// (Capacitor にも WebView にも依存していなかった)。置き換えたのは、Web から
/// 呼ぶための `@JavascriptInterface` を MethodChannel にした部分だけ。
///
/// ## パッケージ名について
/// いまは `com.toriscollection.toris_app`。製品版は `com.toriscollection.app`。
/// **わざと別にしてある** — 同じにすると開発中のビルドが Play 版を潰すため。
/// 切り替え(提案書 §3 ステップ3)のときに製品版の名前へ変える。
library;

import 'package:flutter/material.dart';

import 'alarm.dart';

void main() => runApp(const TorisApp());

class TorisApp extends StatelessWidget {
  const TorisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Toris Collection',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7BA87B)),
        useMaterial3: true,
      ),
      home: const AlarmPage(),
    );
  }
}

class AlarmPage extends StatefulWidget {
  const AlarmPage({super.key});

  @override
  State<AlarmPage> createState() => _AlarmPageState();
}

class _AlarmPageState extends State<AlarmPage> {
  TimeOfDay _time = const TimeOfDay(hour: 7, minute: 0);
  String _bird = alarmBirds.first.key;
  AlarmSetting? _current;
  bool _exactAllowed = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final s = await Alarm.get();
    final exact = await Alarm.canScheduleExact();
    if (!mounted) return;
    setState(() {
      _current = s;
      _exactAllowed = exact;
      if (s.enabled) {
        _time = TimeOfDay(hour: s.hour, minute: s.minute);
        _bird = s.sound;
      }
    });
  }

  Future<void> _pickTime() async {
    final t = await showTimePicker(context: context, initialTime: _time);
    if (t != null) setState(() => _time = t);
  }

  Future<void> _set() async {
    final ok = await Alarm.set(_time.hour, _time.minute, _bird);
    if (!mounted) return;
    if (!ok) {
      // Android 12+ で「正確なアラーム」が未許可。設定画面へ案内する。
      final go = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('正確な時刻に鳴らす許可が要ります'),
          content: const Text(
            'Android の設定で「アラームとリマインダー」を許可してください。'
            '許可がないと、端末が眠っている間に時刻がずれます。',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('あとで')),
            FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('設定を開く')),
          ],
        ),
      );
      if (go == true) await Alarm.openExactAlarmSettings();
      await _refresh();
      return;
    }
    await _refresh();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('⏰ ${_time.format(context)} にセットしました')),
    );
  }

  Future<void> _cancel() async {
    await Alarm.cancel();
    await _refresh();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('解除しました')));
  }

  @override
  Widget build(BuildContext context) {
    final s = _current;
    return Scaffold(
      backgroundColor: const Color(0xFFF7FAF2),
      appBar: AppBar(
        title: const Text('鳥の声と起きたい'),
        backgroundColor: const Color(0xFFCFD9B8),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            '選んだ鳥のさえずりが、5分かけて少しずつ大きくなり、'
            '途中でほかの鳥も加わります。いきなり大きな音では起こしません。',
            style: TextStyle(color: Colors.grey.shade700, height: 1.5),
          ),
          const SizedBox(height: 24),

          // ── 時刻 ──
          Card(
            child: ListTile(
              leading: const Icon(Icons.schedule),
              title: const Text('起きる時刻'),
              subtitle: Text(_time.format(context),
                  style: const TextStyle(
                      fontSize: 30, fontWeight: FontWeight.w600)),
              trailing: const Icon(Icons.edit),
              onTap: _pickTime,
            ),
          ),
          const SizedBox(height: 16),

          // ── 最初に鳴く鳥 ──
          const Text('最初に鳴く鳥', style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text(
            'さえずりだけを選べるようにしています。耳障りな地鳴きで起こさないためです。',
            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
          ),
          const SizedBox(height: 8),
          RadioGroup<String>(
            groupValue: _bird,
            onChanged: (v) => setState(() => _bird = v!),
            child: Column(
              children: alarmBirds
                  .map((b) => RadioListTile<String>(
                        value: b.key,
                        title: Text(b.name),
                        dense: true,
                      ))
                  .toList(),
            ),
          ),
          const SizedBox(height: 16),

          if (!_exactAllowed)
            Card(
              color: const Color(0xFFFFF3E0),
              child: ListTile(
                leading: const Icon(Icons.warning_amber, color: Colors.orange),
                title: const Text('正確な時刻に鳴らす許可がありません'),
                subtitle: const Text('このままだと時刻がずれることがあります'),
                trailing: TextButton(
                  onPressed: () async {
                    await Alarm.openExactAlarmSettings();
                    await _refresh();
                  },
                  child: const Text('設定'),
                ),
              ),
            ),

          Row(children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _set,
                icon: const Icon(Icons.alarm),
                label: const Text('この時刻にセット'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton(
                onPressed: s?.enabled == true ? _cancel : null,
                child: const Text('解除する'),
              ),
            ),
          ]),
          const SizedBox(height: 20),

          // ── いまの設定(ネイティブが持っているものをそのまま出す)──
          Center(
            child: Text(
              s == null
                  ? '…'
                  : (s.enabled
                      ? '⏰ ${s.hhmm} にセットされています'
                      : 'いまは設定されていません'),
              style: const TextStyle(color: Color(0xFF3F5C37)),
            ),
          ),
        ],
      ),
    );
  }
}
