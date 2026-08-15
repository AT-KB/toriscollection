/// 庭の画面。**植える → 虫が来る → 鳥が来る** を1画面で見せる。
///
/// 文字は少なく、押すものは大きく。説明せずに、いま何が起きているかを見せる。
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'garden_state.dart';

class GardenPage extends StatefulWidget {
  /// 会った回数はラジオと目覚ましが読む。庭で貯まったものをそのまま渡す。
  final void Function(Garden garden)? onChanged;
  const GardenPage({super.key, this.onChanged});

  @override
  State<GardenPage> createState() => _GardenPageState();
}

class _GardenPageState extends State<GardenPage>
    with AutomaticKeepAliveClientMixin {
  Garden? _g;
  final Random _rng = Random();
  List<String> _newcomers = [];

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    GardenData.load().then((d) async {
      final g = Garden(d);
      await g.restore();
      if (mounted) setState(() => _g = g);
    });
  }

  Future<void> _look() async {
    final g = _g;
    if (g == null) return;
    final came = g.lookAtGarden(_rng);
    await g.save();
    widget.onChanged?.call(g);
    if (mounted) setState(() => _newcomers = came);
  }

  Future<void> _togglePlant(String id) async {
    final g = _g;
    if (g == null) return;
    setState(() {
      g.planted.contains(id) ? g.remove(id) : g.plant(id);
    });
    await g.save();
  }

  String _name(Map<String, dynamic> m, String id) =>
      (m[id]?['english'] as String?) ?? id;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final g = _g;
    if (g == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Garden')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    final web = g.web;

    return Scaffold(
      appBar: AppBar(title: const Text('Garden')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          // ── 主役: 見に行く ──
          FilledButton.icon(
            onPressed: _look,
            icon: const Icon(Icons.visibility_outlined, size: 28),
            label: const Text('Look outside'),
          ),
          const SizedBox(height: 8),
          Text('${web.temperature.round()}°C  ·  '
              '${g.planted.length}/${g.maxPlants} planted',
              style: const TextStyle(color: kSub)),
          const SizedBox(height: 22),

          if (_newcomers.isNotEmpty) ...[
            _Banner(
                'New: ${_newcomers.map((b) => _name(g.data.birds, b)).join(', ')}'),
            const SizedBox(height: 18),
          ],

          // ── いま来ている鳥 ──
          if (g.visiting.isNotEmpty) ...[
            const _Label('Here now'),
            ...g.visiting.map((b) => _Row(
                  icon: Icons.flutter_dash,
                  text: _name(g.data.birds, b),
                  trailing: (g.observed[b] ?? 0) > 0 ? '×${g.observed[b]}' : null,
                )),
            const SizedBox(height: 22),
          ],

          // ── 湧いている虫(鳥を呼ぶもの) ──
          if (web.insects.isNotEmpty) ...[
            const _Label('Insects'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final i in web.insects.keys)
                  Chip(label: Text(_name(g.data.insects, i))),
              ],
            ),
            const SizedBox(height: 22),
          ],

          // ── 植える ──
          const _Label('Plant'),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final p in g.availablePlants)
                FilterChip(
                  avatar: Text((g.data.plants[p]?['icon'] as String?) ?? '🌱'),
                  label: Text(_name(g.data.plants, p)),
                  selected: g.planted.contains(p),
                  onSelected: (_) => _togglePlant(p),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);
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

class _Row extends StatelessWidget {
  final IconData icon;
  final String text;
  final String? trailing;
  const _Row({required this.icon, required this.text, this.trailing});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(children: [
          Icon(icon, size: 20, color: kGreen),
          const SizedBox(width: 12),
          Expanded(
              child: Text(text,
                  style: const TextStyle(fontSize: 17, color: kInk))),
          if (trailing != null)
            Text(trailing!, style: const TextStyle(color: kSub)),
        ]),
      );
}

/// 新しく来た鳥の知らせ。急かさず、静かに1行だけ。
class _Banner extends StatelessWidget {
  final String text;
  const _Banner(this.text);
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFE8F1DE),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(text, style: const TextStyle(color: kInk, fontSize: 15)),
      );
}
