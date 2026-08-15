/// ドット絵が無い種の代役。
///
/// 37種のうち絵があるのは25種。残り12種は今まで `Icons.flutter_dash`
/// (**Flutter のマスコット**)が出ていた。世界観の異物で、CEO から
/// 「アイコンじゃないやつ」と指摘された箇所(2026-08-15)。
///
/// 絵が描き上がるまでのあいだ、**その鳥の色をした小鳥のかたち**で代える。
/// 種ごとに色が違うので、並んでも見分けがつく。
/// 交渉不能の原則5「かわいさ最優先」— 代役でも、まず鳥に見えること。
library;

import 'package:flutter/material.dart';

class BirdMark extends StatelessWidget {
  final double size;

  /// 種の色(`data.py` の color)。無ければ枝の色。
  final Color color;
  const BirdMark({super.key, required this.size, required this.color});

  /// 種データの `color`("#7ba87b" 形式)から作る。
  factory BirdMark.forBird(Map<String, dynamic>? bird, {required double size}) {
    final raw = bird?['color'];
    var c = const Color(0xFF8A9A7B);
    if (raw is String && raw.startsWith('#') && raw.length == 7) {
      final v = int.tryParse(raw.substring(1), radix: 16);
      if (v != null) c = Color(0xFF000000 | v);
    }
    return BirdMark(size: size, color: c);
  }

  @override
  Widget build(BuildContext context) =>
      CustomPaint(size: Size(size, size), painter: _BirdPainter(color));
}

class _BirdPainter extends CustomPainter {
  final Color color;
  _BirdPainter(this.color);

  @override
  void paint(Canvas canvas, Size s) {
    final w = s.width, h = s.height;
    final body = Paint()..color = color;

    // からだ(丸め)
    canvas.drawOval(
        Rect.fromLTWH(w * 0.14, h * 0.34, w * 0.60, h * 0.46), body);
    // あたま
    canvas.drawCircle(Offset(w * 0.66, h * 0.34), w * 0.20, body);
    // しっぽ
    final tail = Path()
      ..moveTo(w * 0.20, h * 0.52)
      ..lineTo(w * 0.02, h * 0.44)
      ..lineTo(w * 0.18, h * 0.70)
      ..close();
    canvas.drawPath(tail, body);
    // くちばし
    final beak = Path()
      ..moveTo(w * 0.84, h * 0.32)
      ..lineTo(w * 0.99, h * 0.37)
      ..lineTo(w * 0.84, h * 0.42)
      ..close();
    canvas.drawPath(beak, Paint()..color = const Color(0xFFC98A3C));
    // め
    canvas.drawCircle(
        Offset(w * 0.72, h * 0.30), w * 0.045, Paint()..color = Colors.white);
    canvas.drawCircle(Offset(w * 0.73, h * 0.30), w * 0.025,
        Paint()..color = const Color(0xFF2A2A2A));
    // あし
    final leg = Paint()
      ..color = const Color(0xFF7A6A50)
      ..strokeWidth = w * 0.05
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(w * 0.38, h * 0.78), Offset(w * 0.38, h * 0.93), leg);
    canvas.drawLine(Offset(w * 0.52, h * 0.78), Offset(w * 0.52, h * 0.93), leg);
  }

  @override
  bool shouldRepaint(_BirdPainter old) => old.color != color;
}
