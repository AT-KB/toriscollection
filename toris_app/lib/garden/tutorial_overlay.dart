/// チュートリアルモードの覆い。**次に触るものだけ**を明るく残す。
///
/// CEO 2026-08-16「ポップアップの通り踏まないとほか押せない、次進めない」。
///
/// ## 作り
///  - 画面全体を暗い幕で覆い、対象のまわりだけ**穴を開ける**
///    (`saveLayer` + `BlendMode.clear`)。
///  - 穴の外は、**幕の上に置いた4枚の板がタップを吸う**。
///    穴の中には板を置かないので、下の widget にそのまま指が届く。
///    当たり判定を細工するより、板を4枚置くほうが確実で読める。
///  - 対象の位置は `GlobalKey` から測る。画面が動いたら測り直す。
///
/// ## 触らないこと
///  - **急かす飾りを足さない**(残り時間・進捗バー・カウントダウン)。
///    段の番号すら出さない。原則1「受動的である」。
library;

import 'package:flutter/material.dart';

import '../ui/theme.dart';

/// 覆いの1枚ぶん。
class TutorialOverlay extends StatelessWidget {
  /// 明るく残すもの。null なら穴を開けない(全面が暗いまま)。
  final GlobalKey? targetKey;

  final String title;
  final String body;

  /// ボタンの文字。**null なら、実際に操作するまで進めない。**
  final String? nextLabel;
  final VoidCallback? onNext;

  const TutorialOverlay({
    super.key,
    required this.title,
    required this.body,
    this.targetKey,
    this.nextLabel,
    this.onNext,
  });

  /// 対象の画面上の位置。測れなければ null。
  Rect? _targetRect() {
    final ctx = targetKey?.currentContext;
    if (ctx == null) return null;
    final box = ctx.findRenderObject();
    if (box is! RenderBox || !box.hasSize) return null;
    final origin = box.localToGlobal(Offset.zero);
    return Rect.fromLTWH(origin.dx, origin.dy, box.size.width, box.size.height)
        .inflate(8);
  }

  @override
  Widget build(BuildContext context) {
    final screen = MediaQuery.of(context).size;
    final hole = _targetRect();

    // カードは、穴とぶつからない側に置く。
    final holeBottom = hole?.bottom ?? 0;
    final cardOnTop = hole != null && holeBottom > screen.height * 0.55;

    return Stack(children: [
      // ① 暗い幕(穴つき)
      Positioned.fill(
        child: IgnorePointer(
          child: CustomPaint(painter: _ScrimPainter(hole)),
        ),
      ),

      // ② 穴の外だけ、タップを吸う4枚の板
      ..._blockers(screen, hole),

      // ③ 案内カード
      Positioned(
        left: 20,
        right: 20,
        top: cardOnTop ? screen.height * 0.10 : null,
        bottom: cardOnTop ? null : 28,
        child: _Card(
          title: title,
          body: body,
          nextLabel: nextLabel,
          onNext: onNext,
        ),
      ),
    ]);
  }

  /// 穴の上下左右を塞ぐ板。穴の中には**置かない**ので、指が下まで届く。
  List<Widget> _blockers(Size s, Rect? hole) {
    Widget block(double? left, double? top, double? width, double? height) =>
        Positioned(
          left: left ?? 0,
          top: top ?? 0,
          width: width ?? s.width,
          height: height ?? s.height,
          // 吸うだけ。押しても何も起きない(誤操作で先へ進ませない)。
          child: GestureDetector(
              behavior: HitTestBehavior.opaque, onTap: () {}),
        );

    if (hole == null) return [block(0, 0, s.width, s.height)];
    return [
      block(0, 0, s.width, hole.top), // 上
      block(0, hole.bottom, s.width, s.height - hole.bottom), // 下
      block(0, hole.top, hole.left, hole.height), // 左
      block(hole.right, hole.top, s.width - hole.right, hole.height), // 右
    ];
  }
}

/// 幕。穴の部分だけ切り抜く。
class _ScrimPainter extends CustomPainter {
  final Rect? hole;
  const _ScrimPainter(this.hole);

  @override
  void paint(Canvas canvas, Size size) {
    final full = Offset.zero & size;
    canvas.saveLayer(full, Paint());
    canvas.drawRect(full, Paint()..color = const Color(0xC4243A20));
    if (hole != null) {
      canvas.drawRRect(
          RRect.fromRectAndRadius(hole!, const Radius.circular(14)),
          Paint()..blendMode = BlendMode.clear);
    }
    canvas.restore();

    // 穴のふち。どこを触ればいいか、ひと目で分かるように。
    if (hole != null) {
      canvas.drawRRect(
          RRect.fromRectAndRadius(hole!, const Radius.circular(14)),
          Paint()
            ..color = const Color(0xFFDCE8CC)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(_ScrimPainter old) => old.hole != hole;
}

class _Card extends StatelessWidget {
  final String title;
  final String body;
  final String? nextLabel;
  final VoidCallback? onNext;
  const _Card(
      {required this.title,
      required this.body,
      this.nextLabel,
      this.onNext});

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.transparent,
        child: Container(
          padding: const EdgeInsets.fromLTRB(22, 20, 22, 20),
          decoration: BoxDecoration(
            color: const Color(0xFFF7FAF1),
            borderRadius: BorderRadius.circular(18),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: const TextStyle(
                      fontSize: 20,
                      height: 1.25,
                      fontWeight: FontWeight.w700,
                      color: kInk)),
              const SizedBox(height: 8),
              Text(body,
                  style: const TextStyle(
                      fontSize: 15, height: 1.5, color: kSub)),
              if (nextLabel != null) ...[
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                      onPressed: onNext, child: Text(nextLabel!)),
                ),
              ],
            ],
          ),
        ),
      );
}
