/// 目覚ましの画面。設計の根拠は
/// `toris_collection/docs/team/proposals/2026-08-11_目覚まし設計_研究に基づく仕様.md`。
///
/// 表示は**英語のみ**(製品版は 2026-08-09 に日本語表示を落としている)。
/// 文言は i18n.py の出荷済みの英語をそのまま使っている。
library;

import 'dart:async';

import 'package:flutter/foundation.dart' show listEquals;
import 'package:flutter/material.dart';

import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import 'alarm.dart';

class AlarmPage extends StatefulWidget {
  /// 近くで**出会った**鳥(儀式が成立した種)。
  /// 2羽目・3羽目はここから選ばれる。空でも構わない(既定の並びで埋まる)。
  final List<String> met;

  const AlarmPage({super.key, this.met = const []});

  @override
  State<AlarmPage> createState() => _AlarmPageState();
}

class _AlarmPageState extends State<AlarmPage> {
  TimeOfDay _time = const TimeOfDay(hour: 7, minute: 0);
  AlarmSetting? _current;
  bool _exactAllowed = true;
  bool _notifyAllowed = true;

  /// 鳴っている最中かどうか。鳴っていれば画面のいちばん上に「止める」を出す。
  bool _ringing = false;
  Timer? _ringWatch;

  /// いま鳴いている鳥。ネイティブが実際に音を足したものだけが入る。
  List<String> _singing = const [];

  /// 選んでいる1羽目。
  late String _first = _choices.first.key;

  /// 選べる鳥。**会えた鳥＋最初から居る3種**。
  List<({String key, String name})> get _choices {
    final list = selectableAlarmBirds(widget.met);
    return list.isEmpty ? [alarmBirds.first] : list;
  }

  @override
  void initState() {
    super.initState();
    _refresh();
    // 鳴り始めたら画面に「止める」を出す。通知を拒否していても止められるように。
    _ringWatch = Timer.periodic(const Duration(seconds: 2), (_) async {
      final r = await Alarm.isRinging();
      // 夜明けのコーラスは1羽から始まって増える。誰が鳴いたかを追う。
      final now = r ? await Alarm.ringingBirds() : const <String>[];
      if (!mounted) return;
      if (r != _ringing || !listEquals(now, _singing)) {
        setState(() {
          _ringing = r;
          _singing = now;
        });
      }
    });
  }

  @override
  void dispose() {
    _ringWatch?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final s = await Alarm.get();
    final exact = await Alarm.canScheduleExact();
    final notify = await Alarm.hasNotificationPermission();
    if (!mounted) return;
    setState(() {
      _current = s;
      _exactAllowed = exact;
      _notifyAllowed = notify;
      if (s.enabled) {
        _time = TimeOfDay(hour: s.hour, minute: s.minute);
      }
    });
  }

  Future<void> _pickTime() async {
    final t = await showTimePicker(context: context, initialTime: _time);
    if (t != null) setState(() => _time = t);
  }

  Future<void> _set() async {
    // 鳴っている最中に「止める」を出すには通知が要る。セットのタイミングで求める。
    if (!_notifyAllowed) {
      await Alarm.requestNotificationPermission();
    }
    final ok = await Alarm.set(_time.hour, _time.minute,
        first: _first, met: widget.met);
    if (!mounted) return;
    if (!ok) {
      // Android 12+ で「正確なアラーム」が未許可。設定画面へ案内する。
      final go = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Permission needed for exact timing'),
          content: const Text(
            'Allow "Alarms & reminders" in Android settings. '
            'Without it, the time can drift while your phone sleeps.',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('Not now')),
            FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('Open settings')),
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
      SnackBar(content: Text('⏰ Set for ${_time.format(context)}')),
    );
  }

  Future<void> _cancel() async {
    await Alarm.cancel();
    await _refresh();
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Turned off')));
  }

  @override
  Widget build(BuildContext context) {
    final s = _current;
    return Scaffold(
      appBar: AppBar(title: const Text('Wake with the birds')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // 鳴っている間だけ出る、大きくて迷いようのない停止ボタン。
          if (_ringing) ...[
            SizedBox(
              height: 64,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFFB3261E)),
                onPressed: () async {
                  await Alarm.stopRinging();
                  if (mounted) setState(() => _ringing = false);
                },
                icon: const Icon(Icons.stop_circle, size: 28),
                label: const Text('Stop the birds',
                    style: TextStyle(fontSize: 18)),
              ),
            ),
            const SizedBox(height: 20),
          ],

          // ── おはようコールの鳥たち ──
          // CEO 2026-08-19「アラーム中に、鳴いてる鳥は名前とアイコンが出る
          // (加わったタイミング以降で)とかにしてほしいな、おはようコールの
          // 鳥たちとして」。
          //
          // ⚠️ **出すのは、ネイティブが実際に音を足した鳥だけ**。
          // 予定を先に書くと、まだ鳴いていない鳥の名前が出る(原則4)。
          // 1羽目から始まって、5分かけて2羽目・3羽目が増えていく。
          if (_ringing && _singing.isNotEmpty) ...[
            const Text('Your morning callers',
                style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.8,
                    color: kSub)),
            const SizedBox(height: 8),
            for (final k in _singing)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(children: [
                  _BirdIcon(k),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _SingingName(name: alarmBirdName(k), singing: true),
                  ),
                ]),
              ),
            const SizedBox(height: 20),
          ],
          const PageTitle('Starts almost too quiet to hear, then grows.'),

          // ── 時刻 ──
          Card(
            elevation: 0,
            color: Colors.white,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(18)),
            child: InkWell(
              borderRadius: BorderRadius.circular(18),
              onTap: _pickTime,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 22),
                child: Center(
                  child: Text(_time.format(context),
                      style: const TextStyle(
                          fontSize: 46,
                          fontWeight: FontWeight.w600,
                          color: kInk)),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // **設定は鳥の一覧より上に置く。** 選べる鳥が23種に増えたので、
          // 下に置くと23羽ぶんスクロールしないと押せなくなる(2026-08-19)。
          FilledButton.icon(
            onPressed: _set,
            icon: const Icon(Icons.alarm, size: 28),
            label: const Text('Set'),
          ),
          const SizedBox(height: 10),
          if (s?.enabled == true)
            TextButton(onPressed: _cancel, child: const Text('Turn off')),
          const SizedBox(height: 12),

          // ── 1羽目を選ぶ ──
          // プルダウンにした(CEO 2026-08-19)。23行の一覧だと、下の設定まで
          // 遠く、選ぶだけで画面が埋まっていた。
          const Text('First to sing',
              style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                  color: kSub)),
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _first,
                isExpanded: true,
                borderRadius: BorderRadius.circular(14),
                items: [
                  for (final b in _choices)
                    DropdownMenuItem(
                      value: b.key,
                      child: Row(children: [
                        _BirdIcon(b.key),
                        const SizedBox(width: 12),
                        Flexible(
                            child: Text(b.name,
                                overflow: TextOverflow.ellipsis)),
                      ]),
                    ),
                ],
                onChanged: (v) => setState(() => _first = v!),
              ),
            ),
          ),
          const SizedBox(height: 10),
          // 何が選べるのかを、事実として書く。
          Text(
            widget.met.isEmpty
                ? 'Meet birds up close in your garden, and they join this '
                    'list — and the chorus.'
                : 'Two more join as it grows, drawn from the '
                    '${widget.met.length} birds you have met up close.',
            style: const TextStyle(fontSize: 13, height: 1.5, color: kSub),
          ),
          const SizedBox(height: 16),

          if (!_notifyAllowed)
            Card(
              color: const Color(0xFFFFF3E0),
              child: ListTile(
                leading: const Icon(Icons.notifications_off,
                    color: Colors.orange),
                title: const Text('Notifications are turned off'),
                subtitle:
                    const Text('You will not see a way to stop the alarm'),
                trailing: TextButton(
                  onPressed: () async {
                    await Alarm.requestNotificationPermission();
                    await _refresh();
                  },
                  child: const Text('Allow'),
                ),
              ),
            ),

          if (!_exactAllowed)
            Card(
              color: const Color(0xFFFFF3E0),
              child: ListTile(
                leading: const Icon(Icons.warning_amber, color: Colors.orange),
                title: const Text('Exact timing is not allowed'),
                subtitle: const Text('The alarm may drift from the time you set'),
                trailing: TextButton(
                  onPressed: () async {
                    await Alarm.openExactAlarmSettings();
                    await _refresh();
                  },
                  child: const Text('Settings'),
                ),
              ),
            ),


          // ── いまの設定(ネイティブが持っているものをそのまま出す)──
          Center(
            child: Text(
              s == null
                  ? '…'
                  : (s.enabled
                      ? '⏰ Set for ${s.hhmm}'
                      : 'Not set right now'),
              style: const TextStyle(color: Color(0xFF3F5C37)),
            ),
          ),
        ],
      ),
    );
  }
}

/// 鳥の姿。ドット絵があればそれ、無ければ `BirdMark`。
///
/// 目覚ましの4種は4種とも絵がある。将来ここを増やしたときに、絵の無い種で
/// **Flutter のマスコットが出ないように**代役を通す(2026-08-15 の指摘)。
class _BirdIcon extends StatelessWidget {
  final String birdId;
  const _BirdIcon(this.birdId);

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 36,
        height: 36,
        child: Image.asset(
          'assets/sprites/$birdId.png',
          filterQuality: FilterQuality.none,
          errorBuilder: (_, _, _) =>
              const BirdMark(size: 30, color: Color(0xFF8A9A7B)),
        ),
      );
}

/// 鳴いている間だけ、名前が**ゆっくり息をする**。
///
/// CEO 2026-08-18「ラジオのような表現にしてほしい、鳴いてるトリの名前が
/// ピヨピヨする感じ」。ラジオの `_BirdRow` と同じ考えで、
/// **鳴っている鳥だけ**に色と動きを与える。
///
/// 動きはゆっくりにする(1.4秒で1往復)。速い点滅は急かす表示になり、
/// 交渉不能の原則1「受動的である」に反する。眠りから覚める画面でもある。
class _SingingName extends StatefulWidget {
  final String name;
  final bool singing;
  const _SingingName({required this.name, required this.singing});

  @override
  State<_SingingName> createState() => _SingingNameState();
}

class _SingingNameState extends State<_SingingName>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  );

  @override
  void initState() {
    super.initState();
    if (widget.singing) _c.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(_SingingName old) {
    super.didUpdateWidget(old);
    // 鳴き止んだら**必ず止める**。回りっぱなしにすると、鳴いていない鳥の
    // 名前が動き続けて表示が嘘になる。
    if (widget.singing && !_c.isAnimating) {
      _c.repeat(reverse: true);
    } else if (!widget.singing && _c.isAnimating) {
      _c.stop();
      _c.value = 0;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (context, _) {
          final t = Curves.easeInOut.transform(_c.value);
          return Row(children: [
            // ラジオと同じ点。鳴っている間だけ色がつく。
            AnimatedContainer(
              duration: const Duration(milliseconds: 400),
              width: 9,
              height: 9,
              margin: const EdgeInsets.only(right: 10),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: widget.singing
                    ? Color.lerp(const Color(0xFFBFD3B0), kGreen, t)
                    : const Color(0xFFDCE3D4),
              ),
            ),
            Flexible(
              child: Text(
                widget.name,
                style: TextStyle(
                  color: widget.singing
                      ? Color.lerp(kSub, kGreen, t)
                      : kInk,
                  fontWeight:
                      widget.singing ? FontWeight.w700 : FontWeight.w400,
                ),
              ),
            ),
          ]);
        },
      );
}
