/// 庭の画面。現行(Streamlit)の「🏞️ 庭の様子」+「🌱 植える」に当たる。
///
/// 現行と同じ順序で出す:
///   ① 木の情景(鳥が枝に止まっている絵)
///   ② 留守のあいだの出来事(誰が来て、誰が去ったか)
///   ③ 土地
///   ④ 植える
///
/// **時間は勝手に進む**(交渉不能の原則1「受動的である」)。開くたびに、
/// 前回からの経過ぶんだけ庭が動いている。押して進める仕掛けは置かない。
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/theme.dart';
import 'garden_state.dart';
import 'ritual.dart';
import 'tree_scene.dart';

class GardenPage extends StatefulWidget {
  final void Function(Garden garden)? onChanged;
  const GardenPage({super.key, this.onChanged});

  @override
  State<GardenPage> createState() => _GardenPageState();
}

class _GardenPageState extends State<GardenPage>
    with AutomaticKeepAliveClientMixin {
  Garden? _g;
  final Random _rng = Random();

  /// 出会いの儀式。耳を澄ますと、鳥が枝を移りながら近づいてくる。
  Ritual? _ritual;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    await Garden.loadSpriteIds();
    final d = await GardenData.load();
    final g = Garden(d);
    await g.restore();
    // 開いた時点で、留守のあいだのぶんを進める。押させない。
    g.catchUp(_rng);
    await g.save();
    if (!mounted) return;
    widget.onChanged?.call(g);
    setState(() => _g = g);
  }

  @override
  void dispose() {
    _ritual?.stop();
    super.dispose();
  }

  Future<void> _save() async {
    final g = _g;
    if (g == null) return;
    await g.save();
    widget.onChanged?.call(g);
  }

  String _name(Map<String, dynamic> m, String id) =>
      (m[id]?['english'] as String?) ?? id;

  Future<void> _listen() async {
    final g = _g;
    if (g == null || g.visiting.isEmpty) return;
    final r = Ritual(List<String>.from(g.visiting), _rng);
    setState(() => _ritual = r);
    await r.start(() {
      if (!mounted) return;
      // 手前まで来た鳥とは「出会えた」。会うほど馴染む。
      for (final b in r.met) {
        if (!g.metThisRitual.contains(b)) {
          g.metThisRitual.add(b);
          g.observed[b] = (g.observed[b] ?? 0) + 1;
        }
      }
      setState(() {});
    }, assetOf: (b) => 'assets/birds/$b.mp3');
  }

  Future<void> _stopListening() async {
    _ritual?.stop();
    final g = _g;
    if (g != null) {
      g.metThisRitual.clear();
      await _save();
    }
    if (mounted) setState(() => _ritual = null);
  }

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
          // ── ① 木の情景。ここが庭の顔。 ──
          TreeScene(
            birds: [
              for (final b in g.visiting)
                PerchedBird(
                  id: b,
                  english: _name(g.data.birds, b),
                  // 儀式のあいだは、いま止まっている枝をそのまま出す
                  depth: _ritual != null
                      ? Ritual.depthName(_ritual!.branch[b] ?? 0)
                      : g.depthOf(b),
                  sprite: g.spriteFor(b),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            g.visiting.isEmpty
                ? 'No one yet.'
                : g.visiting.map((b) => _name(g.data.birds, b)).join(' · '),
            style: const TextStyle(color: kInk, fontSize: 16),
          ),
          const SizedBox(height: 6),
          Text('${web.temperature.round()}°C',
              style: const TextStyle(color: kSub, fontSize: 13)),
          const SizedBox(height: 14),

          // ── 出会いの儀式 ──
          // 押し続けさせない。待っていれば、鳥のほうから近づいてくる。
          if (g.visiting.isNotEmpty)
            FilledButton.icon(
              onPressed: _ritual == null ? _listen : _stopListening,
              icon: Icon(_ritual == null
                  ? Icons.hearing
                  : Icons.stop_rounded, size: 26),
              label: Text(_ritual == null ? 'Listen closely' : 'Enough'),
            ),
          if (_ritual != null && _ritual!.met.isNotEmpty) ...[
            const SizedBox(height: 10),
            _Note('Came close: '
                '${_ritual!.met.map((b) => _name(g.data.birds, b)).join(', ')}'),
          ],
          const SizedBox(height: 20),

          // ── ② 留守のあいだの出来事 ──
          if (g.lastArrivals.isNotEmpty || g.lastDepartures.isNotEmpty) ...[
            _Note([
              if (g.lastArrivals.isNotEmpty)
                'Came while you were away: '
                    '${g.lastArrivals.map((b) => _name(g.data.birds, b)).join(', ')}',
              if (g.lastDepartures.isNotEmpty)
                'Moved on: '
                    '${g.lastDepartures.map((b) => _name(g.data.birds, b)).join(', ')}',
            ].join('\n')),
            const SizedBox(height: 20),
          ],

          // ── ③ 土地 ──
          const _Label('Your land'),
          Wrap(
            spacing: 10,
            children: [
              for (final id in g.data.biomes.keys)
                ChoiceChip(
                  label: Text(
                      (g.data.biomes[id]?['name_en'] as String?) ?? id),
                  selected: g.biomeId == id,
                  onSelected: (_) async {
                    setState(() => g.setBiome(id));
                    await _save();
                  },
                ),
            ],
          ),
          const SizedBox(height: 20),

          // ── ④ 植える ──
          _Label('Plant  ${g.planted.length}/${g.maxPlants}'),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (final p in g.availablePlants)
                FilterChip(
                  avatar: Text((g.data.plants[p]?['icon'] as String?) ?? '🌱'),
                  label: Text(_name(g.data.plants, p)),
                  selected: g.planted.contains(p),
                  onSelected: (_) async {
                    setState(() => g.planted.contains(p)
                        ? g.remove(p)
                        : g.plant(p));
                    await _save();
                  },
                ),
            ],
          ),

          // 湧いている虫。鳥が来る理由そのものなので、庭にも出す。
          if (web.insects.isNotEmpty) ...[
            const SizedBox(height: 20),
            const _Label('Insects'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final i in web.insects.keys)
                  Chip(
                      avatar: const Text('🐛'),
                      label: Text(_name(g.data.insects, i))),
              ],
            ),
          ],
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

/// 留守のあいだの知らせ。急かさず、静かに。
class _Note extends StatelessWidget {
  final String text;
  const _Note(this.text);
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFE8F1DE),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(text,
            style: const TextStyle(color: kInk, fontSize: 15, height: 1.5)),
      );
}
