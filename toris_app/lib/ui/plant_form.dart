/// 植物を、庭の絵にどう描くか。
///
/// ## 新しいデータを足さずに決める(原則4「生態に誠実」)
/// `plants.json` が持っているのは biome / english / icon / scientific / temp_fit
/// だけで、**色も形も持っていない**。恣意的な指標を新しく作らないため、
/// すでに人が選んだ `icon` から形と色を引く。
/// 🌲 は針葉樹、🟣 は紫の実がなる低木、🌾 は草 — アイコンがすでに両方を語っている。
///
/// アイコンが増えたら、この表に足す。表に無いものは低木として緑で描く
/// (何も描かないより、そこに何かが生えている方が正しい)。
library;

import 'package:flutter/material.dart';

/// 描き分けるかたち。
enum PlantForm {
  /// 針葉樹(三角に重なる)
  conifer,

  /// 広葉樹(丸い樹冠)
  broadleaf,

  /// 低木(丸い茂み)
  shrub,

  /// 実のなる低木(茂みに粒がつく)
  berryShrub,

  /// 草花(茎の先に花)
  flower,

  /// 草(細い葉が数本)
  grass,
}

class PlantLook {
  final PlantForm form;
  final Color color;

  /// 実や花の色(茂みや草の緑とは別)。
  final Color accent;
  const PlantLook(this.form, this.color, this.accent);
}

const Color _leafGreen = Color(0xFF6E9C5A);
const Color _darkGreen = Color(0xFF4C7A4A);

/// アイコン → 見た目。`plants.json` の icon をそのまま鍵にする。
const Map<String, PlantLook> kPlantLooks = {
  // 木
  '🌳': PlantLook(PlantForm.broadleaf, _leafGreen, Color(0xFF88B072)),
  '🌲': PlantLook(PlantForm.conifer, _darkGreen, Color(0xFF3E6B3E)),
  '🍁': PlantLook(PlantForm.broadleaf, Color(0xFFC4643C), Color(0xFFD98A4E)),
  '🍂': PlantLook(PlantForm.broadleaf, Color(0xFFB08248), Color(0xFFE0A860)),
  // 花の咲く木・低木
  '🌸': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFFF0A8BE)),
  '🌺': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFFD9566A)),
  '🌼': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFFF2E3A0)),
  '🤍': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFFF6F4EE)),
  '🌹': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFFC1425A)),
  '🌿': PlantLook(PlantForm.shrub, _leafGreen, Color(0xFF7FAE68)),
  // 実のなるもの
  '🟣': PlantLook(PlantForm.berryShrub, _leafGreen, Color(0xFF8E4BA8)),
  '🍇': PlantLook(PlantForm.berryShrub, _leafGreen, Color(0xFF6B3E8F)),
  '🍒': PlantLook(PlantForm.berryShrub, _leafGreen, Color(0xFFC03A46)),
  // 草
  '🌾': PlantLook(PlantForm.grass, Color(0xFFB9A96A), Color(0xFFCFC08A)),
  '🌻': PlantLook(PlantForm.flower, _leafGreen, Color(0xFFE8B93C)),
};

/// 表に無いアイコンでも、必ず何かを返す。
PlantLook plantLook(String? icon) =>
    kPlantLooks[icon] ?? const PlantLook(PlantForm.shrub, _leafGreen, _leafGreen);

/// 地面の点 [base] に、高さ [h] で1株描く。
void paintPlant(Canvas canvas, Offset base, double h, PlantLook look) {
  final stem = Paint()..color = const Color(0xFF6B6146);
  final body = Paint()..color = look.color;
  final accent = Paint()..color = look.accent;

  switch (look.form) {
    case PlantForm.conifer:
      canvas.drawRect(
          Rect.fromLTWH(base.dx - h * 0.05, base.dy - h * 0.22, h * 0.10,
              h * 0.22),
          stem);
      for (var i = 0; i < 3; i++) {
        final top = base.dy - h * (1.0 - i * 0.24);
        final wHalf = h * (0.20 + i * 0.09);
        final bottom = top + h * 0.36;
        canvas.drawPath(
            Path()
              ..moveTo(base.dx, top)
              ..lineTo(base.dx - wHalf, bottom)
              ..lineTo(base.dx + wHalf, bottom)
              ..close(),
            body);
      }
      break;

    case PlantForm.broadleaf:
      canvas.drawRect(
          Rect.fromLTWH(base.dx - h * 0.055, base.dy - h * 0.38, h * 0.11,
              h * 0.38),
          stem);
      canvas.drawCircle(Offset(base.dx, base.dy - h * 0.62), h * 0.34, body);
      canvas.drawCircle(
          Offset(base.dx - h * 0.22, base.dy - h * 0.48), h * 0.24, body);
      canvas.drawCircle(
          Offset(base.dx + h * 0.22, base.dy - h * 0.48), h * 0.24, body);
      break;

    case PlantForm.shrub:
    case PlantForm.berryShrub:
      canvas.drawCircle(Offset(base.dx, base.dy - h * 0.34), h * 0.30, body);
      canvas.drawCircle(
          Offset(base.dx - h * 0.26, base.dy - h * 0.22), h * 0.24, body);
      canvas.drawCircle(
          Offset(base.dx + h * 0.26, base.dy - h * 0.22), h * 0.24, body);
      if (look.form == PlantForm.berryShrub) {
        // 実。数を決め打ちして、毎回同じ形にする(揺れると気が散る)。
        const spots = [
          Offset(-0.20, -0.42), Offset(0.10, -0.52), Offset(0.28, -0.26),
          Offset(-0.32, -0.16), Offset(0.0, -0.20),
        ];
        for (final s in spots) {
          canvas.drawCircle(
              Offset(base.dx + s.dx * h, base.dy + s.dy * h), h * 0.075,
              accent);
        }
      } else {
        // 花。実より少なく、大きめに。
        const spots = [
          Offset(-0.22, -0.40), Offset(0.14, -0.50), Offset(0.26, -0.22),
        ];
        for (final s in spots) {
          canvas.drawCircle(
              Offset(base.dx + s.dx * h, base.dy + s.dy * h), h * 0.10,
              accent);
        }
      }
      break;

    case PlantForm.flower:
      canvas.drawRect(
          Rect.fromLTWH(base.dx - h * 0.04, base.dy - h * 0.72, h * 0.08,
              h * 0.72),
          Paint()..color = look.color);
      canvas.drawCircle(Offset(base.dx, base.dy - h * 0.78), h * 0.20, accent);
      canvas.drawCircle(
          Offset(base.dx, base.dy - h * 0.78), h * 0.09,
          Paint()..color = const Color(0xFF7A5A2A));
      // 葉
      canvas.drawOval(
          Rect.fromCenter(
              center: Offset(base.dx - h * 0.16, base.dy - h * 0.34),
              width: h * 0.28,
              height: h * 0.14),
          Paint()..color = look.color);
      break;

    case PlantForm.grass:
      for (var i = -2; i <= 2; i++) {
        final tip = Offset(base.dx + i * h * 0.11, base.dy - h * (0.9 - (i.abs() * 0.16)));
        canvas.drawPath(
            Path()
              ..moveTo(base.dx, base.dy)
              ..quadraticBezierTo(
                  base.dx + i * h * 0.06, base.dy - h * 0.45, tip.dx, tip.dy)
              ..quadraticBezierTo(base.dx + i * h * 0.10, base.dy - h * 0.4,
                  base.dx, base.dy)
              ..close(),
            body);
      }
      // 穂
      canvas.drawCircle(Offset(base.dx, base.dy - h * 0.92), h * 0.07, accent);
      break;
  }
}
