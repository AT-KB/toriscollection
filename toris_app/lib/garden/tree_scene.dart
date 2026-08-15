/// 木の情景。**鳥が枝に止まっている絵**。`toris_collection/ritual.py` の移植。
///
/// 現行はここが庭の顔で、これが無いと「アメリカの庭をスマホに」が成立しない。
/// 幹が地面から生え、そこから水平の枝が出て、上に丸い葉の塊(キャノピー)。
/// 奥から手前へ3層(b3 → b2 → b1)で遠近を付ける。鳥はこの枝に止まる。
///
/// 数字は現行の `_TREE_SPECS` をそのまま使っている:
///   (枝の高さ%, 半幅%, 幹の太さpx, 枝の厚みpx, キャノピー径px, 濃さ, 重なり順)
library;

import 'dart:math';

import 'package:flutter/material.dart';

import '../ui/bird_mark.dart';

class TreeSpec {
  final double branchTop; // 枝の高さ(%)
  final double halfWidth; // 枝の半幅(%)
  final double trunkW; // 幹の太さ(px)
  final double branchH; // 枝の厚み(px)
  final double canopy; // キャノピー径(px)
  final double opacity;
  final String depth;
  const TreeSpec(this.branchTop, this.halfWidth, this.trunkW, this.branchH,
      this.canopy, this.opacity, this.depth);
}

/// 奥 → 手前。現行と同じ値。
const List<TreeSpec> kTreeSpecs = [
  TreeSpec(37, 27, 16, 6, 74, 0.70, 'b3'), // 奥
  TreeSpec(54, 35, 22, 9, 98, 0.86, 'b2'),
  TreeSpec(70, 43, 30, 13, 126, 1.00, 'b1'), // 手前
];

/// 枝の中央に空ける切れ目(%)。左右の木を分ける。
const double kGapHalf = 5.0;

/// 情景の高さ(px)。現行の _SCENE_H と同じ。
const double kSceneHeight = 195;

const Color _kLeaf = Color(0xFF9CBF8A);
const Color _kBranch = Color(0xFF7A6A55);
const Color _kSky = Color(0xFFEFF5E6);

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

/// 木と、そこに止まる鳥を描く。
class TreeScene extends StatefulWidget {
  final List<PerchedBird> birds;
  const TreeScene({super.key, required this.birds});

  @override
  State<TreeScene> createState() => _TreeSceneState();
}

class _TreeSceneState extends State<TreeScene> {
  final Random _rng = Random();

  /// 鳥ID → 枝の上での横位置(0..1)。ときどき跳ねて動く(ホップ)。
  final Map<String, double> _pos = {};

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth;
      final children = <Widget>[];

      // 空
      children.add(Positioned.fill(
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            gradient: const LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFFF7FAF2), _kSky],
            ),
          ),
        ),
      ));

      // 木を奥から手前へ
      for (final t in kTreeSpecs) {
        final topPx = t.branchTop / 100 * kSceneHeight;
        final lx = (50 - t.halfWidth) / 100 * w;
        final rx = (50 + t.halfWidth) / 100 * w;
        final gap = kGapHalf / 100 * w;

        // キャノピー(枝の奥に重なる)
        children.add(Positioned(
          top: topPx - t.canopy * 0.82,
          left: w / 2 - t.canopy / 2,
          child: Opacity(
            opacity: t.opacity * 0.9,
            child: Container(
              width: t.canopy,
              height: t.canopy,
              decoration: const BoxDecoration(
                  color: _kLeaf, shape: BoxShape.circle),
            ),
          ),
        ));
        // 左右の枝(中央に切れ目)
        for (final seg in [
          [lx, w / 2 - gap],
          [w / 2 + gap, rx],
        ]) {
          children.add(Positioned(
            top: topPx,
            left: seg[0],
            child: Opacity(
              opacity: t.opacity,
              child: Container(
                  width: (seg[1] - seg[0]).clamp(0, w),
                  height: t.branchH,
                  decoration: BoxDecoration(
                      color: _kBranch,
                      borderRadius: BorderRadius.circular(t.branchH / 2))),
            ),
          ));
        }
        // 幹
        children.add(Positioned(
          top: topPx,
          left: w / 2 - t.trunkW / 2,
          child: Opacity(
            opacity: t.opacity,
            child: Container(
                width: t.trunkW,
                height: kSceneHeight - topPx,
                color: _kBranch),
          ),
        ));
      }

      // 鳥を枝に置く
      for (final b in widget.birds) {
        final spec = kTreeSpecs.firstWhere((t) => t.depth == b.depth,
            orElse: () => kTreeSpecs.first);
        final p = _pos.putIfAbsent(b.id, () => _rng.nextDouble());
        final half = spec.halfWidth / 100 * w;
        // 左右どちらかの枝の上。中央の切れ目は避ける。
        final left = p < 0.5
            ? w / 2 - half + p * 2 * (half - kGapHalf / 100 * w)
            : w / 2 + kGapHalf / 100 * w + (p - 0.5) * 2 * (half - kGapHalf / 100 * w);
        final size = 34.0 * (spec.opacity * 0.5 + 0.6);
        children.add(AnimatedPositioned(
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          top: spec.branchTop / 100 * kSceneHeight - size + spec.branchH,
          left: left.clamp(0.0, w - size),
          child: GestureDetector(
            // つついて跳ねさせる。急かす仕掛けではなく、ただの反応。
            onTap: () => setState(() => _pos[b.id] = _rng.nextDouble()),
            child: Opacity(
              opacity: spec.opacity,
              child: b.sprite != null
                  ? Image.asset(b.sprite!,
                      width: size, height: size, filterQuality: FilterQuality.none)
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
