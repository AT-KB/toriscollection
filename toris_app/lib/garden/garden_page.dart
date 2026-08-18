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

import '../ui/bird_mark.dart';
import '../ui/theme.dart';
import 'garden_state.dart';
import 'popups.dart';
import 'ritual.dart';
import 'transfer_sheet.dart';
import 'tree_scene.dart';
import 'tutorial_overlay.dart';

class GardenPage extends StatefulWidget {
  final void Function(Garden garden)? onChanged;
  const GardenPage({super.key, this.onChanged});

  @override
  State<GardenPage> createState() => _GardenPageState();
}

class _GardenPageState extends State<GardenPage>
    with AutomaticKeepAliveClientMixin, WidgetsBindingObserver {
  Garden? _g;
  final Random _rng = Random();

  /// 出会いの儀式。耳を澄ますと、鳥が枝を移りながら近づいてくる。
  Ritual? _ritual;

  /// この儀式で出会えた鳥(終わったらポップアップで見せる)。
  final List<MetBird> _metThisRitual = [];

  /// この回の儀式が「出会い」として記録されるか。始めた時点で決める。
  bool _ritualCounts = true;

  // チュートリアルで**明るく残すもの**の目印。
  final GlobalKey _landKey = GlobalKey();
  final GlobalKey _plantKey = GlobalKey();
  final GlobalKey _insectKey = GlobalKey();

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _boot();
  }

  /// 前面に戻ってきたら、留守のぶんを進める。
  ///
  /// 儀式の最中は触らない(鳥が近づいている途中で庭を作り直さない)。
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final g = _g;
    if (state != AppLifecycleState.resumed || g == null) return;
    if (_ritual != null) return;
    _advance(g);
  }

  Future<void> _boot() async {
    await Garden.loadSpriteIds();
    final d = await GardenData.load();
    final g = Garden(d);
    await g.restore();
    await _advance(g);
  }

  /// 留守のあいだのぶんを進めて、「おかえり」を出す。
  ///
  /// ⚠️ **起動時だけでは足りない。**
  /// `initState` は画面を作り直したときしか通らない。ホームに戻して数時間後に
  /// 戻ってきても Flutter の処理は生きたままなので、ここを通らず庭が
  /// 止まっていた。**「なんで到来全然しないの」の正体**(2026-08-18)。
  /// OS がアプリを殺すまで、何時間放っておいても鳥は来なかった。
  Future<void> _advance(Garden g) async {
    final before = g.lastSeenAt;
    // 開いた時点で、留守のあいだのぶんを進める。押させない。
    g.catchUp(_rng);
    final hoursAway = before == null
        ? 0.0
        : DateTime.now().difference(before).inSeconds / 3600.0;
    await g.save();
    if (!mounted) return;
    widget.onChanged?.call(g);
    setState(() => _g = g);

    // **一度に開くのは1つだけ。** 起動時は「おかえり」だけ(出会いは儀式のあと)。
    final report = AwayReport(
      hoursAway: hoursAway,
      arrivals: [
        for (final b in g.lastArrivals)
          MetBird(b, g.lastFirstTimers.contains(b)),
      ],
      departures: <String>{
        for (final b in g.lastDepartures) _name(g.data.birds, b),
      }.toList(),
      lostPlants: [for (final p in g.lastLostPlants) _name(g.data.plants, p)],
      // 撹乱は種類ごとに一文で語る。倒れた植物はその文の中に入る。
      disturbanceStories: [
        for (final d in g.lastDisturbances)
          core.disturbanceStory(d.type, d.icon, [
            for (final p in g.lastLostPlants) _name(g.data.plants, p),
          ]),
      ],
      summary: core.summarizeEvents(
        g.lastArrivals,
        (b) => _name(g.data.birds, b),
      ),
    );
    if (report.worthShowing && mounted) {
      await showWelcomeBackPopup(context, g, report);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
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

  /// チップに載せる鳥の絵。ドット絵が無い種は、その鳥の色の小鳥で代える
  /// (虫の 🐛 と同じ役回り。ここでも枠組みの既定は使わない)。
  Widget _birdAvatar(Garden g, String birdId) {
    final sprite = g.spriteFor(birdId);
    if (sprite != null) {
      return Image.asset(sprite, filterQuality: FilterQuality.none);
    }
    return BirdMark.forBird(
      (g.data.birds[birdId] as Map?)?.cast<String, dynamic>(),
      size: 20,
    );
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
              Text(
                'Plant  ${g.planted.length}/${g.maxPlants}',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: kInk,
                ),
              ),
              const SizedBox(height: 14),
              for (final p in g.availablePlants)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Text(
                    (g.data.plants[p]?['icon'] as String?) ?? '🌱',
                    style: const TextStyle(fontSize: 24),
                  ),
                  title: Text(
                    _name(g.data.plants, p),
                    style: const TextStyle(fontSize: 16, color: kInk),
                  ),
                  trailing: g.planted.contains(p)
                      ? const Icon(Icons.check_circle, color: kGreen)
                      : (g.planted.length >= g.maxPlants
                            ? null
                            : const Icon(
                                Icons.add_circle_outline,
                                color: kSub,
                              )),
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
    // この回が記録される儀式かどうかを、始めた時点で決める。
    _ritualCounts = g.ritualCounts;
    setState(() => _ritual = r);
    await r.start(() {
      if (!mounted) return;
      // 手前まで来た鳥とは「出会えた」。会うほど馴染む。
      // **記録するのは、数える儀式のときだけ。** 眺めるだけの回は何も増えない。
      if (!_ritualCounts) {
        setState(() {});
        return;
      }
      for (final b in r.met) {
        if (!g.metThisRitual.contains(b)) {
          // 「はじめまして」= **図鑑への新規登録かどうか**。観察回数では見ない
          // (回数で見ると、既に図鑑に載っている鳥にも「はじめて」が出る)。
          final isFirst = !g.discovered.contains(b);
          g.metThisRitual.add(b);
          g.observed[b] = (g.observed[b] ?? 0) + 1;
          // 近くで観察できた鳥は、当然「来た鳥」でもある。
          g.discovered.add(b);
          _metThisRitual.add(MetBird(b, isFirst));
        }
      }
      setState(() {});
    }, assetOf: (b) => 'assets/birds/$b.mp3');
  }

  Future<void> _stopListening() async {
    final met = List<MetBird>.from(_metThisRitual);
    _metThisRitual.clear();
    _ritual?.stop();
    final g = _g;
    if (g != null) {
      g.metThisRitual.clear();
      if (_ritualCounts) {
        // **この顔ぶれには、もう耳を澄ませた。** 同じ相手に繰り返して
        // 観察回数を水増しできないようにする(現行 ritual_done_for_residents)。
        g.ritualDoneFor = g.visiting.toSet();
      }
      await _save();
    }
    if (mounted) setState(() => _ritual = null);
    if (g != null && met.isNotEmpty && mounted) {
      await showMetBirdPopup(context, g, met);
    }
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

    // ── チュートリアルの覆い ──
    // 進み具合を見て段を繰り上げる(「次へ」では進めない段がある)。
    if (g.tutorialRunning) {
      final resolved = core.resolveTutorialStep(
        g.tutorialStep,
        hasPlanted: g.planted.isNotEmpty,
      );
      if (resolved != g.tutorialStep) {
        g.tutorialStep = resolved;
        WidgetsBinding.instance.addPostFrameCallback((_) => _save());
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Garden'),
        actions: [
          // 端末を替えるときの控え。ふだんは押さないので、隅に小さく。
          IconButton(
            tooltip: 'Move your garden',
            icon: const Icon(Icons.ios_share_rounded),
            onPressed: () => showTransferSheet(
              context,
              g,
              onRestored: () async {
                widget.onChanged?.call(g);
                setState(() {});
              },
            ),
          ),
        ],
      ),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
            children: [
              // ── ① 裏庭の情景。ここが庭の顔。 ──
              // 餌台・リス・タカ・植生は、**選択とそのまま連動する**。
              TreeScene(
                plants: [
                  for (final p in g.planted)
                    (g.data.plants[p]?['icon'] as String?) ?? '🌱',
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
              const SizedBox(height: 12),
              // いま来ている鳥。**虫と同じ形**(絵 + 名前のチップ)で下に出す
              // (CEO 2026-08-16「land の鳥も insects みたいに名前とアイコンを
              // 下に出して」)。木の上の鳥は小さいので、ここで誰か分かる。
              if (g.visiting.isEmpty)
                const Text(
                  'No one yet.',
                  style: TextStyle(color: kSub, fontSize: 15),
                )
              else
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final b in g.visiting)
                      Chip(
                        avatar: _birdAvatar(g, b),
                        label: Text(_name(g.data.birds, b)),
                      ),
                  ],
                ),
              const SizedBox(height: 8),
              Text(
                '${web.temperature.round()}°C',
                style: const TextStyle(color: kSub, fontSize: 13),
              ),
              const SizedBox(height: 14),

              // ── 出会いの儀式 ──
              // 押し続けさせない。待っていれば、鳥のほうから近づいてくる。
              if (g.visiting.isNotEmpty) ...[
                FilledButton.icon(
                  onPressed: _ritual == null ? _listen : _stopListening,
                  icon: Icon(
                    _ritual == null ? Icons.hearing : Icons.stop_rounded,
                    size: 26,
                  ),
                  label: Text(_ritual == null ? 'Listen closely' : 'Enough'),
                ),
                // 眺めるのはいつでもできる。**記録にならない**時だけ、静かに断る。
                if (!g.ritualCounts)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      "🌙 You've listened closely enough for today. "
                      'When a new bird comes, you can go and meet it again.',
                      style: TextStyle(fontSize: 12, height: 1.4, color: kSub),
                    ),
                  ),
              ],
              const SizedBox(height: 20),

              // ── ② 留守のあいだの出来事 ──
              // **ここには出さない。ポップアップにだけ出す**(CEO 2026-08-16
              // 「ガーデンの lost left とかはポップにだけあればいい」)。
              // 庭に常設すると、痩せたことをずっと突きつけることになる。

              // ── ③ 土地 ──
              const _Label('Your land'),
              Wrap(
                key: _landKey,
                spacing: 10,
                children: [
                  for (final id in g.data.biomes.keys)
                    ChoiceChip(
                      label: Text(
                        (g.data.biomes[id]?['name_en'] as String?) ?? id,
                      ),
                      selected: g.biomeId == id,
                      onSelected: (_) async {
                        setState(() {
                          g.setBiome(id);
                          // 案内中は、土地を選んだ時点で次へ(「次へ」は出さない)。
                          if (g.tutorialStep == 0) {
                            g.tutorialStep = core.advanceTutorialStep(0);
                          }
                        });
                        await _save();
                      },
                    ),
                ],
              ),
              const SizedBox(height: 20),

              // ── ④ 植える ──
              // 一覧を出しっぱなしにしない。**植えたものだけ**を見せ、
              // 足すときにだけ選ぶ画面を開く(CEO 2026-08-15「ダラダラしている」)。
              Row(
                children: [
                  Expanded(
                    child: _Label('Plant  ${g.planted.length}/${g.maxPlants}'),
                  ),
                  if (g.planted.length < g.maxPlants)
                    TextButton.icon(
                      key: _plantKey,
                      onPressed: () => _openPlantPicker(g),
                      icon: const Icon(Icons.add, size: 20),
                      label: const Text('Add'),
                    ),
                ],
              ),
              if (g.planted.isEmpty)
                Text(
                  'Nothing planted yet.',
                  style: TextStyle(color: kSub, fontSize: 14),
                )
              else
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final p in g.planted)
                      InputChip(
                        avatar: Text(
                          (g.data.plants[p]?['icon'] as String?) ?? '🌱',
                        ),
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
              // **短く。種名は絵文字で代用**(CEO 2026-08-16)。
              // 何が起きているかは庭の絵に出ているので、文はひとことでいい。
              if (g.chain.raptors.isNotEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text(
                    'The squirrel drew a hawk. '
                    'Shy birds keep their distance.',
                    style: TextStyle(fontSize: 13, height: 1.4, color: kSub),
                  ),
                )
              else if (g.chain.animals.isNotEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text(
                    'A squirrel is taking the seed.',
                    style: TextStyle(fontSize: 13, color: kSub),
                  ),
                ),

              // 湧いている虫。鳥が来る理由そのものなので、庭にも出す。
              if (web.insects.isNotEmpty) ...[
                const SizedBox(height: 20),
                const _Label('Insects'),
                Wrap(
                  key: _insectKey,
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final i in web.insects.keys)
                      Chip(
                        avatar: const Text('🐛'),
                        label: Text(_name(g.data.insects, i)),
                      ),
                  ],
                ),
              ],
            ],
          ),

          // ── チュートリアルの覆い。次に触るものだけ明るい ──
          if (g.tutorialRunning) _tutorial(g, web),
        ],
      ),
    );
  }

  /// いまの段の覆い。段によって、明るく残すものが変わる。
  Widget _tutorial(Garden g, core.FoodWeb web) {
    final step = g.tutorialStep;
    final content = core.tutorialStepContent(
      step,
      hasInsects: web.insects.isNotEmpty,
    );

    // 明るく残すもの。**土地と植えるは、実際に触るまで進めない**ので、
    // そこだけ穴を開けて指を通す。
    final target = switch (step) {
      0 => _landKey,
      1 => _plantKey,
      2 => web.insects.isNotEmpty ? _insectKey : null,
      _ => null,
    };

    return TutorialOverlay(
      targetKey: target,
      title: content.title,
      body: content.body,
      nextLabel: content.nextLabel,
      onNext: content.nextLabel == null
          ? null
          : () async {
              setState(() => g.tutorialStep = core.advanceTutorialStep(step));
              await _save();
            },
    );
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Text(
      text,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.8,
        color: kSub,
      ),
    ),
  );
}
