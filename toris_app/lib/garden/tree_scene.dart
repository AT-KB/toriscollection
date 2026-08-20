/// 庭の情景 — **アメリカの裏庭**。
///
/// コンセプト: 植生をつくって鳥を呼び、その鳥で朝を迎える。その舞台が
/// 「餌台を置いていそうな裏庭」だと一目で分かること
/// (CEO 2026-08-16「アメリカの庭のバックヤードの Feeder をおいていそうな感じ」)。
///
/// 奥から手前へ:
///   空 → 家の端 → 木(3層の枝)→ 餌台 → 植えたもの → 芝生
///
/// フェンスは**置かない**(CEO 2026-08-16「フェンス要らない」)。
/// 植えたものは**チップと同じアイコンをそのまま**置く(同「なんかアイコンと
/// 同じとかでいい」)。形と色を描き分ける版は作ったが、要らないと判断された。
///
/// **鳥は木の枝に止まり、枝を移って近づいてくる。** 枝の3層はそのまま
/// 「近さ」(b1 が手前)で、会った回数で決まる(`radio.py` の _obs_to_depth)。
/// つつくと跳ねるのもそのまま(CEO「ぴょんぴょん飛ぶのはいい感じ」)。
///
/// **餌台・リス・タカは選択とそのまま連動する**(`feeder_chain`)。
/// 開放型を置けば 🐿️ が餌台の下に現れ、リスが 🦅 を呼ぶ。
/// かご型に替えれば両方消える。文字で説明せず、絵で見せる。
/// **動物と植物は絵文字**。塗りで描くと、小さいと潰れ、大きいと鳥と紛れた。
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/bird_mark.dart';

class TreeSpec {
  final double branchTop; // 枝の高さ(情景の高さに対する%)
  final double halfWidth; // 枝の張り出し(幅に対する%、幹から左右へ)
  final double trunkW; // 幹の太さ(px)
  final double branchH; // 枝の厚み(px)
  final double canopy; // 樹冠の径(px)
  final double opacity;
  final String depth;
  const TreeSpec(this.branchTop, this.halfWidth, this.trunkW, this.branchH,
      this.canopy, this.opacity, this.depth);
}

/// 奥 → 手前。木は1本で、枝が3段。
/// 枝の張り出し(halfWidth)は**滞在の上限4羽が重ならない幅**が要る。
/// 木を右に寄せたときに奥の枝を狭くしすぎ、4羽で重なって試験に落ちた。
/// 変えるときは `test/tree_scene_test.dart` を必ず走らせること。
const List<TreeSpec> kTreeSpecs = [
  TreeSpec(30, 26, 14, 6, 78, 0.70, 'b3'), // 奥の枝
  TreeSpec(44, 30, 19, 9, 102, 0.86, 'b2'),
  TreeSpec(58, 34, 26, 12, 130, 1.00, 'b1'), // 手前の枝
];

/// 幹の位置(幅に対する%)。左に餌台、**右端はタカの席**として空ける。
/// 右に寄せすぎると、右上のタカが奥の枝と重なって「大きい鳥」にしか
/// 見えなくなる(実際にそうなった)。
const double kTrunkX = 55.0;

/// 情景の高さ(px)。裏庭にしたぶん、以前(195)より高い。
const double kSceneHeight = 260;

/// 地面の上端(情景の高さに対する%)。ここから下が芝生。
const double kGroundTop = 76.0;

const Color _kSky = Color(0xFFE3EFF4);
const Color _kSkyLow = Color(0xFFF2F6E8);
const Color _kLawn = Color(0xFF8FB56A);
const Color _kLawnDark = Color(0xFF83AA61);
const Color _kHouse = Color(0xFFE9E2D5);
const Color _kRoof = Color(0xFF9A7F6A);
const Color _kLeaf = Color(0xFF9CBF8A);
const Color _kBranch = Color(0xFF7A6A55);

/// 枝にとまっている鳥。
class PerchedBird {
  final String id;
  final String english;

  /// 近さ。b1 が手前。会った回数で決まる(現行の _obs_to_depth)。
  final String depth;

  /// ドット絵のパス(無ければ `BirdMark` で代用)。
  final String? sprite;

  /// 種データ(絵が無いとき、その鳥の色で代役を描くのに使う)。
  final Map<String, dynamic>? data;
  const PerchedBird(
      {required this.id,
      required this.english,
      required this.depth,
      this.data,
      this.sprite});
}

class TreeScene extends StatefulWidget {
  final List<PerchedBird> birds;

  /// 植えたもののアイコン(`plants.json` の icon)。芝から**少し立ち上げて**置く。
  final List<String> plants;

  /// 置いている餌台。`feeder_open` / `feeder_cage` / null。
  final String? feeder;

  /// 餌台に来ている動物が居るか(リスを描く)。
  final bool hasSquirrel;

  /// 猛禽が居るか(空にタカを描く)。
  final bool hasRaptor;

  /// いま驚かされているか。'squirrel' / 'hawk' / null。
  ///
  /// CEO 2026-08-18「リスや鷹が木に近づいて、鳥が逃げていくアクション」。
  /// **鳥が下がるのは儀式側の仕事**(`Ritual._hop`)で、ここは
  /// 「近づいてくる絵」だけを受け持つ。両方をここでやると、絵と記録が
  /// ずれる(絵では逃げているのに数字は近づいたまま、になりうる)。
  final String? scare;

  const TreeScene({
    super.key,
    required this.birds,
    this.scare,
    this.plants = const [],
    this.feeder,
    this.hasSquirrel = false,
    this.hasRaptor = false,
  });

  @override
  State<TreeScene> createState() => _TreeSceneState();
}

class _TreeSceneState extends State<TreeScene> {
  /// 鳥ごとの、席の中でのゆらぎ(0〜1)。つつくと引き直す。
  final Map<String, double> _pos = {};
  final Random _rng = Random();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final children = <Widget>[
        // 裏庭そのもの(空・家・木・餌台・芝生・リス・タカ)
        Positioned.fill(
          child: CustomPaint(
            painter: _BackyardPainter(
              feeder: widget.feeder,
              hasSquirrel: widget.hasSquirrel,
              hasRaptor: widget.hasRaptor,
            ),
          ),
        ),
      ];

      // 植えたものを、地面にアイコンのまま並べる。
      // **重ならない間隔**で置く(鳥と同じ理由。詰めると何が生えているか
      // 分からなくなる)。手前・奥に振って、平らに見えないようにする。
      if (widget.plants.isNotEmpty) {
        const iconSize = 30.0;
        final ground = kGroundTop / 100 * kSceneHeight;
        final from = widget.feeder != null ? w * 0.30 : w * 0.20;
        // 絵文字は指定より横に広い。右端で切れないよう余白を多めに取る。
        final to = w - iconSize * 1.4;
        final span = (to - from - iconSize).clamp(0.0, w);
        final step = widget.plants.length == 1
            ? 0.0
            : span / (widget.plants.length - 1);
        for (var i = 0; i < widget.plants.length; i++) {
          // **茎で少し持ち上げる**(CEO 2026-08-20「今地面に置いている感じに
          // なっていて、少しだけ高さほしい」)。絵文字だけだと芝に転がって
          // 見えて、植わっている感じにならなかった。
          //
          // 長さは一定にしない。同じ丈で並ぶと生垣のように見える。
          final stem = 11.0 + (i % 3) * 5.0;
          // 足元は今までと同じ場所。**伸びた分だけ上に置き直す**ので、
          // 並びの奥行き(手前・奥の振り分け)は変わらない。
          final base = ground +
              (kSceneHeight - ground) * (i.isEven ? 0.10 : 0.46) -
              iconSize * 0.2;
          children.add(Positioned(
            left: from + step * i,
            top: base - stem,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(widget.plants[i],
                    style: const TextStyle(fontSize: iconSize)),
                Container(
                  width: 3,
                  height: stem,
                  decoration: BoxDecoration(
                    color: const Color(0xFF6E9A55),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ],
            ),
          ));
        }
      }

      // リスとタカは**絵文字**で置く(CEO 2026-08-16「リス 鷹は絵文字のを
      // 庭に入れれないか」)。塗りで描いた版もあったが、小さくすると潰れ、
      // 大きくすると枝の鳥と紛れた。絵文字なら小さくても何か分かる。
      // 驚かせている間は**木に寄る**。終われば元の場所へ戻る。
      final scared = widget.scare;
      if (widget.feeder != null && widget.hasSquirrel) {
        final near = scared == 'squirrel';
        children.add(AnimatedPositioned(
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOut,
          left: near ? w * 0.42 : w * 0.20,
          top: kGroundTop / 100 * kSceneHeight - (near ? 34 : 6),
          child: Text('🐿️', style: TextStyle(fontSize: near ? 34 : 26)),
        ));
      }
      if (widget.hasRaptor) {
        // 空の右上。枝の届かないところ(重なると「大きい鳥」に見える)。
        final near = scared == 'hawk';
        children.add(AnimatedPositioned(
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOut,
          right: near ? w * 0.34 : w * 0.05,
          top: near ? kSceneHeight * 0.20 : kSceneHeight * 0.06,
          child: Text('🦅', style: TextStyle(fontSize: near ? 40 : 24)),
        ));
      }

      // 鳥を枝に置く。
      //
      // **同じ枝の鳥は重ねない。** 以前は位置を鳥ごとの乱数で決めていたため、
      // たまたま近い値を引くと2羽が重なって、どちらも読めなくなっていた
      // (実機で Blue Jay と Song Sparrow が重なった)。
      // 枝の使える幅を**ピクセルで**割って席にする。
      final byDepth = <String, List<PerchedBird>>{};
      for (final b in widget.birds) {
        byDepth.putIfAbsent(b.depth, () => []).add(b);
      }
      for (final list in byDepth.values) {
        list.sort((a, b) => a.id.compareTo(b.id)); // 並びを毎回同じにする
      }

      for (final b in widget.birds) {
        final spec = kTreeSpecs.firstWhere((t) => t.depth == b.depth,
            orElse: () => kTreeSpecs.first);
        final mates = byDepth[b.depth]!;
        final slot = mates.indexOf(b);
        final size = 34.0 * (spec.opacity * 0.5 + 0.6);

        final seg = branchSegments(spec, w);
        final usable = (seg[0][1] - seg[0][0]) + (seg[1][1] - seg[1][0]) - size;
        final seat = usable / mates.length;
        // 持ち場が絵より狭ければ揺らさない(それ以上は枝の広さの問題)。
        final room = (seat - size).clamp(0.0, seat);
        final jitter = _pos.putIfAbsent(b.id, () => _rng.nextDouble());
        var offset = seat * slot + (room > 0 ? jitter * room : 0.0);
        offset = offset.clamp(0.0, usable > 0 ? usable : 0.0);

        // 使える幅の中の位置を、左の枝 → 右の枝の順に割り当てる。
        final leftRoom = seg[0][1] - seg[0][0];
        final left = offset < leftRoom
            ? seg[0][0] + offset
            : seg[1][0] + (offset - leftRoom);

        children.add(AnimatedPositioned(
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          top: spec.branchTop / 100 * kSceneHeight - size + spec.branchH,
          left: left.clamp(0.0, w - size),
          child: GestureDetector(
            // 試験から1羽ずつ拾えるようにする(重なっていないことを見るため)
            key: ValueKey('perch_${b.id}'),
            // つついて跳ねさせる。急かす仕掛けではなく、ただの反応。
            onTap: () => setState(() => _pos[b.id] = _rng.nextDouble()),
            child: Opacity(
              opacity: spec.opacity,
              child: b.sprite != null
                  ? Image.asset(b.sprite!,
                      width: size,
                      height: size,
                      filterQuality: FilterQuality.none)
                  // 絵が無い種は、その鳥の色をした小鳥のかたちで代える。
                  // (以前は Flutter のマスコットが出ていた)
                  : BirdMark.forBird(b.data, size: size),
            ),
          ),
        ));
      }

      return SizedBox(
        height: kSceneHeight,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(18),
          child: Stack(children: children),
        ),
      );
    });
  }
}

/// その枝の、鳥が止まれる区間(幹の左側・右側)。絵と鳥の配置で同じものを使う。
List<List<double>> branchSegments(TreeSpec t, double w) {
  final trunk = kTrunkX / 100 * w;
  final reach = t.halfWidth / 100 * w;
  final half = t.trunkW / 2;
  return [
    [trunk - reach, trunk - half],
    [trunk + half, trunk + reach],
  ];
}

/// 裏庭を描く。奥から手前へ順番に。
class _BackyardPainter extends CustomPainter {
  final String? feeder;
  final bool hasSquirrel;
  final bool hasRaptor;
  const _BackyardPainter({
    required this.feeder,
    required this.hasSquirrel,
    required this.hasRaptor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final ground = kGroundTop / 100 * h;

    // ── 空 ──
    canvas.drawRect(
        Rect.fromLTWH(0, 0, w, ground),
        Paint()
          ..shader = const LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [_kSky, _kSkyLow],
          ).createShader(Rect.fromLTWH(0, 0, w, ground)));

    // ── 家の端(左) ──
    // 全部は描かない。**角だけ**見せて「自分の家の裏」だと伝える。
    final houseW = w * 0.15;
    final eaves = h * 0.08;
    canvas.drawRect(Rect.fromLTWH(0, eaves, houseW, ground - eaves),
        Paint()..color = _kHouse);
    canvas.drawRect(Rect.fromLTWH(0, eaves, houseW, h * 0.035),
        Paint()..color = _kRoof);
    final win =
        Rect.fromLTWH(houseW * 0.24, eaves + h * 0.09, houseW * 0.52, h * 0.12);
    canvas.drawRRect(RRect.fromRectAndRadius(win, const Radius.circular(2)),
        Paint()..color = const Color(0xFFC6D6DA));
    canvas.drawLine(
        Offset(win.center.dx, win.top),
        Offset(win.center.dx, win.bottom),
        Paint()
          ..color = _kHouse
          ..strokeWidth = 2);

    // ── 芝生 ──
    canvas.drawRect(
        Rect.fromLTWH(0, ground, w, h - ground), Paint()..color = _kLawn);
    for (var i = 0; i < 3; i++) {
      canvas.drawRect(
          Rect.fromLTWH(
              0, ground + (h - ground) * (i * 2 + 1) / 6, w, (h - ground) / 12),
          Paint()..color = _kLawnDark);
    }

    // ── 木(奥の枝から手前へ) ──
    final trunkX = kTrunkX / 100 * w;
    for (final t in kTreeSpecs) {
      final topPx = t.branchTop / 100 * h;
      canvas.drawCircle(Offset(trunkX, topPx - t.canopy * 0.30), t.canopy / 2,
          Paint()..color = _kLeaf.withValues(alpha: t.opacity * 0.9));
      for (final seg in branchSegments(t, w)) {
        canvas.drawRRect(
            RRect.fromRectAndRadius(
                Rect.fromLTWH(
                    seg[0], topPx, (seg[1] - seg[0]).clamp(0, w), t.branchH),
                Radius.circular(t.branchH / 2)),
            Paint()..color = _kBranch.withValues(alpha: t.opacity));
      }
      canvas.drawRect(
          Rect.fromLTWH(trunkX - t.trunkW / 2, topPx, t.trunkW, ground - topPx),
          Paint()..color = _kBranch.withValues(alpha: t.opacity));
    }

    // ── 餌台 ──
    final poleX = w * 0.17;
    if (feeder != null) {
      final poleTop = h * 0.44;
      canvas.drawRect(
          Rect.fromLTWH(poleX - 3, poleTop, 6, ground + h * 0.06 - poleTop),
          Paint()..color = const Color(0xFF6E6152));
      _paintFeeder(canvas, Offset(poleX, poleTop), h, feeder!);
    }
  }

  /// 餌台。開放型は皿、かご型は筒に金網。
  void _paintFeeder(Canvas canvas, Offset top, double h, String kind) {
    final roof = Paint()..color = const Color(0xFF6E5638);
    final s = h * 0.12;

    if (kind == 'feeder_cage') {
      // 筒 + 金網。リスは中身に届かない。
      canvas.drawRRect(
          RRect.fromRectAndRadius(
              Rect.fromLTWH(top.dx - s * 0.28, top.dy, s * 0.56, s * 1.10),
              Radius.circular(s * 0.16)),
          Paint()..color = const Color(0xFFCBAE7E));
      final mesh = Paint()
        ..color = const Color(0xFF5E5646)
        ..strokeWidth = 1.1
        ..style = PaintingStyle.stroke;
      final cage = RRect.fromRectAndRadius(
          Rect.fromLTWH(
              top.dx - s * 0.52, top.dy - s * 0.08, s * 1.04, s * 1.26),
          Radius.circular(s * 0.20));
      canvas.drawRRect(cage, mesh);
      for (var i = 1; i < 4; i++) {
        final x = top.dx - s * 0.52 + s * 1.04 * i / 4;
        canvas.drawLine(
            Offset(x, top.dy - s * 0.08), Offset(x, top.dy + s * 1.18), mesh);
      }
      canvas.drawPath(
          Path()
            ..moveTo(top.dx - s * 0.62, top.dy - s * 0.08)
            ..lineTo(top.dx, top.dy - s * 0.52)
            ..lineTo(top.dx + s * 0.62, top.dy - s * 0.08)
            ..close(),
          roof);
    } else {
      // 開放型。皿に種が見えていて、誰でも来られる。
      canvas.drawRect(
          Rect.fromLTWH(
              top.dx - s * 0.62, top.dy + s * 0.42, s * 1.24, s * 0.32),
          Paint()..color = const Color(0xFF8B6F4E));
      canvas.drawRect(
          Rect.fromLTWH(
              top.dx - s * 0.50, top.dy + s * 0.26, s * 1.00, s * 0.18),
          Paint()..color = const Color(0xFFD8BE86)); // 種
      canvas.drawPath(
          Path()
            ..moveTo(top.dx - s * 0.72, top.dy + s * 0.22)
            ..lineTo(top.dx, top.dy - s * 0.30)
            ..lineTo(top.dx + s * 0.72, top.dy + s * 0.22)
            ..close(),
          roof);
    }
  }

  @override
  bool shouldRepaint(_BackyardPainter old) =>
      old.feeder != feeder ||
      old.hasSquirrel != hasSquirrel ||
      old.hasRaptor != hasRaptor;
}
