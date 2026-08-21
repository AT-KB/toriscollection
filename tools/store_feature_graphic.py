"""Google Play のフィーチャーグラフィック(1024x500・掲載に必須)を作る。

**絵は描き起こさない。** 使うのは `toris_app/assets/sprites/` にある
アプリ本物のドット絵、色は `lib/ui/theme.dart` と `lib/garden/tree_scene.dart`
の実値、文言は landing/page.html の確定コピーだけ。
(交渉不能5原則 原則4「映っていないものを宣伝で言わない」)

    py -3 tools/store_feature_graphic.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "toris_app" / "assets" / "sprites"
OUT = ROOT / "marketing" / "phase-1" / "SNS部" / "素材" / "store" / "feature_graphic.png"
FONTS = Path(r"C:/Users/kubok/flutter/bin/cache/artifacts/material_fonts")  # Roboto (Apache-2.0)

W, H = 1024, 500

# tree_scene.dart / theme.dart の実値
SKY = (227, 239, 244)
SKY_LOW = (242, 246, 232)
LAWN = (143, 181, 106)
LAWN_DARK = (131, 170, 97)
INK = (47, 74, 42)
SUB = (63, 107, 46)

# landing/page.html の確定コピー
TITLE = "Toris Collection"
LINE1 = "Grow a tiny ecosystem."
LINE2 = "The birds come —"
LINE3 = "and become your radio."

BIRDS = ["american_goldfinch_detail", "northern_cardinal_detail", "blue_jay_detail"]


def main() -> None:
    im = Image.new("RGB", (W, H), SKY)
    d = ImageDraw.Draw(im)

    lawn_top = 372
    for y in range(lawn_top):  # 空のグラデーション
        t = y / lawn_top
        d.line([(0, y), (W, y)],
               fill=tuple(round(a + (b - a) * t) for a, b in zip(SKY, SKY_LOW)))
    d.rectangle([0, lawn_top, W, H], fill=LAWN)
    d.rectangle([0, lawn_top, W, lawn_top + 10], fill=LAWN_DARK)

    # 鳥は本物のドット絵。芝の上に立たせる。
    # **右端からはみ出させない**(1度やらかした)。並べる幅を先に測り、
    # 右余白 RIGHT に収まるよう倍率を決めてから貼る。
    RIGHT, GAP = 964, 30
    box_left = 600
    raw = [Image.open(SPRITES / f"{n}.png").convert("RGBA") for n in BIRDS]
    rel = [0.82, 1.0, 0.82]                  # 真ん中を少し大きく
    base = 230                               # 真ん中の高さの目安
    heights = [round(base * r) for r in rel]
    widths = [round(s.width * h / s.height) for s, h in zip(raw, heights)]
    total = sum(widths) - GAP * (len(raw) - 1)
    avail = RIGHT - box_left
    if total > avail:                        # 収まらなければ全体を縮める
        k = avail / total
        heights = [round(h * k) for h in heights]
        widths = [round(s.width * h / s.height) for s, h in zip(raw, heights)]
        total = sum(widths) - GAP * (len(raw) - 1)
    x = RIGHT - total
    for s, h, w in zip(raw, heights, widths):
        s = s.resize((w, h), Image.LANCZOS)
        im.paste(s, (x, lawn_top + 24 - h), s)
        x += w - GAP
    assert x + GAP <= RIGHT + 1, "鳥が右端からはみ出している"

    big = ImageFont.truetype(str(FONTS / "roboto-bold.ttf"), 64)
    mid = ImageFont.truetype(str(FONTS / "roboto-regular.ttf"), 30)
    d.text((64, 116), TITLE, font=big, fill=INK)
    for i, line in enumerate((LINE1, LINE2, LINE3)):
        d.text((66, 208 + i * 40), line, font=mid, fill=SUB)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    im.save(OUT)
    print(f"{OUT}  {im.size}  {im.mode}")


if __name__ == "__main__":
    main()
