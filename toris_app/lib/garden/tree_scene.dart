/// 庭の情景 — **アメリカの裏庭**。
///
/// コンセプト: 植生をつくって鳥を呼び、その鳥で朝を迎える。その舞台が
/// 「餌台を置いていそうな裏庭」だと一目で分かること
/// (CEO 2026-08-16「アメリカの庭のバックヤードの Feeder をおいていそうな感じ」)。
///
/// 奥から手前へ:
///   空 → 家の端 → フェンス → 木(3層の枝)→ 餌台 → 植えたもの → 芝生
///
/// **鳥は木の枝に止まり、枝を移って近づいてくる。** 枝の3層はそのまま
/// 「近さ」(b1 が手前)で、会った回数で決まる(`radio.py` の _obs_to_depth)。
/// つつくと跳ねるのもそのまま(CEO「ぴょんぴょん飛ぶのはいい感じ」)。
///
/// **餌台・リス・タカは選択とそのまま連動する**(`feeder_chain`)。
/// 開放型を置けばリスが餌台の下に現れ、リスがタカを呼んでフェンスに止まる。
/// かご型に替えれば両方消える。文字で説明せず、絵で見せる。
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/bird_mark.dart';
import '../ui/plant_form.dart';

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
/// 右に寄せすぎると、フェンスのタカが奥の枝と重なって「大きい鳥」にしか
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
const Color _kFence = Color(0xFFCFBE9F);
const Color _kFenceLine = Color(0xFFB6A288);
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

  /// 植えたもの。地面に並べて描く(アイコンから形と色を引く)。
  final List<PlantLook> plants;

  /// 置いている餌台。`feeder_open` / `feeder_cage` / null。
  final String? feeder;

  /// 餌台に来ている動物が居るか(リスを描く)。
  final bool hasSquirrel;

  /// 猛禽が居るか(フェンスにタカを描く)。
  final bool hasRaptor;

  const TreeScene({
    super.key,
    required this.birds,
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
        // 裏庭そのもの(空・家・フェンス・木・餌台・植生・芝生・リス・タカ)
        Positioned.fill(
          child: CustomPaint(
            painter: _BackyardPainter(
              plants: widget.plants,
              feeder: widget.feeder,
              hasSquirrel: widget.hasSquirrel,
              hasRaptor: widget.hasRaptor,
            ),
          ),
        ),
      ];

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
  final List<PlantLook> plants;
  final String? feeder;
  final bool hasSquirrel;
  final bool hasRaptor;
  const _BackyardPainter({
    required this.plants,
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

    // ── フェンス(奥) ──
    final fenceTop = h * 0.37;
    canvas.drawRect(
        Rect.fromLTWH(houseW, fenceTop, w - houseW, ground - fenceTop),
        Paint()..color = _kFence);
    final line = Paint()
      ..color = _kFenceLine
      ..strokeWidth = 1.4;
    for (var i = 1; i < 4; i++) {
      final y = fenceTop + (ground - fenceTop) * i / 4;
      canvas.drawLine(Offset(houseW, y), Offset(w, y), line);
    }
    for (var x = houseW + 30.0; x < w; x += 64) {
      canvas.drawRect(
          Rect.fromLTWH(x, fenceTop - h * 0.015, 5, ground - fenceTop + h * 0.015),
          Paint()..color = _kFenceLine);
    }

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

    // ── タカ ──
    // 猛禽はフェンスの上から見ている。臆病な鳥が来にくいのは、この視線のせい。
    // **枝の届かない右端**に置く。枝と重なると、ただの大きい鳥に見える。
    if (hasRaptor) {
      _paintHawk(canvas, Offset(w * 0.91, h * 0.37), h * 0.125);
    }

    // ── 植えたもの ──
    // 餌台の右から画面いっぱいまで、**重ならない間隔**で並べる。
    // 鳥と同じで、狭い範囲に詰めると株が重なって何が生えているか分からなくなる
    // (実際に4株で重なった)。1株ぶんの幅を確保してから割る。
    if (plants.isNotEmpty) {
      final ph = h * 0.185; // 1株の高さ
      final pw = ph * 1.05; // 1株の幅(茂みがいちばん横に張る)
      final from = (feeder != null ? poleX + w * 0.10 : houseW + w * 0.02);
      final to = w - w * 0.02;
      final span = (to - from - pw).clamp(0.0, w);
      final step = plants.length == 1 ? 0.0 : span / (plants.length - 1);
      for (var i = 0; i < plants.length; i++) {
        final x = from + pw / 2 + step * i;
        // 前後に振って奥行きを出す(重なりは横の間隔で既に防いでいる)
        final y = ground + (h - ground) * (i.isEven ? 0.40 : 0.88);
        paintPlant(canvas, Offset(x, y), ph, plants[i]);
      }
    }

    // ── リス ──
    // **植生より後に描く。** 先に描くと茂みに隠れて、何が居るのか分からない。
    if (feeder != null && hasSquirrel) {
      _paintSquirrel(canvas, Offset(poleX + w * 0.02, ground + h * 0.09),
          h * 0.125);
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

  /// リス。餌台の下で種を拾っている。
  ///
  /// しっぽは**太さを一定に**した線で描く。塗りつぶしの多角形で描いたら
  /// 巨大な三日月になって、別の生き物に見えた(実機で確認して作り直した)。
  void _paintSquirrel(Canvas canvas, Offset base, double s) {
    const furColor = Color(0xFF9A8E80);
    final fur = Paint()..color = furColor;

    // しっぽ。体の後ろから立ち上がって背中の上へ。
    canvas.drawPath(
        Path()
          ..moveTo(base.dx + s * 0.28, base.dy - s * 0.18)
          ..cubicTo(
              base.dx + s * 0.95, base.dy - s * 0.30,
              base.dx + s * 1.00, base.dy - s * 1.05,
              base.dx + s * 0.42, base.dy - s * 1.28),
        Paint()
          ..color = furColor
          ..style = PaintingStyle.stroke
          ..strokeWidth = s * 0.40
          ..strokeCap = StrokeCap.round);

    // からだ(前かがみ)
    canvas.drawOval(
        Rect.fromCenter(
            center: Offset(base.dx, base.dy - s * 0.42),
            width: s * 0.72,
            height: s * 0.88),
        fur);
    // あたま
    canvas.drawCircle(
        Offset(base.dx - s * 0.20, base.dy - s * 0.95), s * 0.30, fur);
    // みみ
    canvas.drawCircle(
        Offset(base.dx - s * 0.30, base.dy - s * 1.22), s * 0.11, fur);
    // め
    canvas.drawCircle(Offset(base.dx - s * 0.34, base.dy - s * 1.00), s * 0.055,
        Paint()..color = const Color(0xFF2A2A2A));
    // 前あし(種を持っている)
    canvas.drawCircle(
        Offset(base.dx - s * 0.30, base.dy - s * 0.55), s * 0.10, fur);
  }

  /// タカ。フェンスの上から見ている。
  void _paintHawk(Canvas canvas, Offset base, double s) {
    final body = Paint()..color = const Color(0xFF6E5D4E);
    canvas.drawOval(
        Rect.fromLTWH(
            base.dx - s * 0.34, base.dy - s * 0.90, s * 0.68, s * 0.90),
        body);
    canvas.drawCircle(Offset(base.dx, base.dy - s * 0.95), s * 0.26, body);
    // くちばし(曲がっている ＝ 猛禽)
    canvas.drawPath(
        Path()
          ..moveTo(base.dx + s * 0.20, base.dy - s * 1.00)
          ..lineTo(base.dx + s * 0.52, base.dy - s * 0.94)
          ..lineTo(base.dx + s * 0.22, base.dy - s * 0.82)
          ..close(),
        Paint()..color = const Color(0xFFD8B84E));
    canvas.drawCircle(Offset(base.dx + s * 0.09, base.dy - s * 1.02), s * 0.07,
        Paint()..color = const Color(0xFFF2E9D8));
    canvas.drawCircle(Offset(base.dx + s * 0.10, base.dy - s * 1.02), s * 0.035,
        Paint()..color = const Color(0xFF1F1F1F));
    // 尾
    canvas.drawPath(
        Path()
          ..moveTo(base.dx - s * 0.28, base.dy - s * 0.30)
          ..lineTo(base.dx - s * 0.78, base.dy - s * 0.05)
          ..lineTo(base.dx - s * 0.26, base.dy - s * 0.02)
          ..close(),
        body);
  }

  @override
  bool shouldRepaint(_BackyardPainter old) =>
      old.feeder != feeder ||
      old.hasSquirrel != hasSquirrel ||
      old.hasRaptor != hasRaptor ||
      old.plants.length != plants.length;
}
