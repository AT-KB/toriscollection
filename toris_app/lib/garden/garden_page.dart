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
import 'package:toris_core/toris_core.dart' as core;

import '../ui/plant_form.dart';
import '../ui/theme.dart';
import 'garden_state.dart';
import 'ritual.dart';
import 'transfer_sheet.dart';
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

  /// 到来1件を、短く。**鳥 ← 目当て** だけ。
  /// 目当てが分からなければ鳥の名前だけ(何かに惹かれたことにしない・原則4)。
  String _shortReason(Garden g, core.ArrivalEvent r) {
    final bird = _name(g.data.birds, r.birdId);
    if (r.relatedPlant.isNotEmpty) {
      final icon = (g.data.plants[r.relatedPlant]?['icon'] as String?) ?? '🌱';
      return '$bird  ←  $icon ${_name(g.data.plants, r.relatedPlant)}';
    }
    if (r.relatedInsect.isNotEmpty) {
      return '$bird  ←  🐛 ${_name(g.data.insects, r.relatedInsect)}';
    }
    return bird;
  }

  /// 植えるものを選ぶ。**開いたときだけ**一覧を見せる。
  Future<void> _openPlantPicker(Garden g) async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        builder: (ctx, controller) => StatefulBuilder(
          builder: (ctx, setSheet) => ListView(
            controller: controller,
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            children: [
              Text('Plant  ${g.planted.length}/${g.maxPlants}',
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w600, color: kInk)),
              const SizedBox(height: 14),
              for (final p in g.availablePlants)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Text(
                      (g.data.plants[p]?['icon'] as String?) ?? '🌱',
                      style: const TextStyle(fontSize: 24)),
                  title: Text(_name(g.data.plants, p),
                      style: const TextStyle(fontSize: 16, color: kInk)),
                  trailing: g.planted.contains(p)
                      ? const Icon(Icons.check_circle, color: kGreen)
                      : (g.planted.length >= g.maxPlants
                          ? null
                          : const Icon(Icons.add_circle_outline, color: kSub)),
                  onTap: () async {
                    setSheet(() {
                      g.planted.contains(p) ? g.remove(p) : g.plant(p);
                    });
                    setState(() {});
                    await _save();
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }

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
      appBar: AppBar(
        title: const Text('Garden'),
        actions: [
          // 端末を替えるときの控え。ふだんは押さないので、隅に小さく。
          IconButton(
            tooltip: 'Move your garden',
            icon: const Icon(Icons.ios_share_rounded),
            onPressed: () => showTransferSheet(context, g, onRestored: () async {
              widget.onChanged?.call(g);
              setState(() {});
            }),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          // ── ① 裏庭の情景。ここが庭の顔。 ──
          // 餌台・リス・タカ・植生は、**選択とそのまま連動する**。
          TreeScene(
            plants: [
              for (final p in g.planted)
                plantLook(g.data.plants[p]?['icon'] as String?)
            ],
            feeder: g.feeders.isEmpty ? null : g.feeders.first,
            hasSquirrel: g.chain.animals.isNotEmpty,
            hasRaptor: g.chain.raptors.isNotEmpty,
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
                  data: g.data.birds[b] as Map<String, dynamic>?,
                ),
            ],
          ),
          const SizedBox(height: 10),
          // **今の庭は、上の木そのもの。** 別のカードを足さない。
          // 一度「In your garden now」という帯を作って外した(CEO 2026-08-15
          // 「使い道が分からん」)。木に居る鳥をもう一度並べるだけで、
          // 情報は1つも増えていなかった。
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
          // **文章にしない。** 「◯◯が来ました。△△に惹かれて立ち寄ったようです。」
          // では長すぎる(CEO 2026-08-16「文章だと文字数が多すぎます」)。
          // 関係だけを矢印で見せる: `Carolina Wren ← 🐛 Firefly`
          //
          // 記録そのもの(図鑑の "Why it came")は Python と一致させた**原文のまま**
          // 残してある。ここは表示の組み立て直しで、`ArrivalEvent` が持っている
          // 構造(どの植物・どの虫)から短く作る。
          if (g.lastReasons.isNotEmpty ||
              g.lastArrivals.isNotEmpty ||
              g.lastDepartures.isNotEmpty ||
              g.lastLostPlants.isNotEmpty) ...[
            _Note([
              if (g.lastLostPlants.isNotEmpty)
                '${g.lastDisturbances.join(' ')} Lost  '
                    '${g.lastLostPlants.map((p) => _name(g.data.plants, p)).join(' · ')}',
              for (final r in g.lastReasons) _shortReason(g, r),
              if (g.lastReasons.isEmpty)
                for (final b in g.lastArrivals) _name(g.data.birds, b),
              if (g.lastDepartures.isNotEmpty)
                'Left  '
                    '${g.lastDepartures.map((b) => _name(g.data.birds, b)).join(' · ')}',
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
          // 一覧を出しっぱなしにしない。**植えたものだけ**を見せ、
          // 足すときにだけ選ぶ画面を開く(CEO 2026-08-15「ダラダラしている」)。
          Row(children: [
            Expanded(
              child: _Label('Plant  ${g.planted.length}/${g.maxPlants}'),
            ),
            if (g.planted.length < g.maxPlants)
              TextButton.icon(
                onPressed: () => _openPlantPicker(g),
                icon: const Icon(Icons.add, size: 20),
                label: const Text('Add'),
              ),
          ]),
          if (g.planted.isEmpty)
            Text('Nothing planted yet.',
                style: TextStyle(color: kSub, fontSize: 14))
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final p in g.planted)
                  InputChip(
                    avatar:
                        Text((g.data.plants[p]?['icon'] as String?) ?? '🌱'),
                    label: Text(_name(g.data.plants, p)),
                    onDeleted: () async {
                      setState(() => g.remove(p));
                      await _save();
                    },
                  ),
              ],
            ),

          // ── 餌台 ──
          // 開放型を置くとリスが届き、リスがタカを呼び、臆病な鳥が来にくくなる。
          // かご型ならリスは届かない。**これが唯一の駆け引き**で、罰ではなく選択。
          const SizedBox(height: 20),
          const _Label('Feeder'),
          Wrap(
            spacing: 10,
            children: [
              for (final f in ['feeder_open', 'feeder_cage'])
                ChoiceChip(
                  label: Text(core.kFeeders[f]!['english'] as String),
                  selected: g.feeders.contains(f),
                  onSelected: (on) async {
                    setState(() => g.setFeeder(on ? f : null));
                    await _save();
                  },
                ),
            ],
          ),
          if (g.chain.animals.isNotEmpty || g.chain.raptors.isNotEmpty) ...[
            const SizedBox(height: 10),
            _Note([
              for (final a in g.chain.animals)
                '🐿️ ${core.kAnimals[a]?['english']} is taking the seed.',
              for (final r in g.chain.raptors)
                "🦅 ${core.kRaptors[r]?['english']} is watching. "
                    'Shy birds keep their distance.',
            ].join('\n')),
          ],

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
