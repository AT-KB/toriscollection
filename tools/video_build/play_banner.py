"""「Google Play にあります」の札を、動画に**常設**で入れる。

CEO 2026-08-25「やっぱアプリの宣伝のバナーみたいなのはあるべきだね。
Google Play で実装してるよってやつ」。

## なぜ札にするか(最後の大きなカードをやめた経緯)

最初は**最後の2.8秒に大きなカード**を出していた。15秒の19%を広告に使うと、
**完走の直前に離脱の理由を置く**ことになる(2026-08-25 の考察 §3-C)。
そこで一度、字幕の帯の中の1行に落とした。

CEO の指摘は「1行だと弱い、バナーが要る」。そこで:
**尺は1秒も食わず、最初から最後までずっと出ている小さな札**にした。
見ている全員に届き、完走も殺さない。

## ⚠️ Google の公式バッジは使っていない

"Get it on Google Play" の**公式バッジ画像はブランド規約があり、
支給された画像をそのまま使う**決まり(色や形を作り直してはいけない)。
ここでは公式バッジを**真似ずに**、うちのアイコンと文字だけで作っている。

公式バッジを出したい場合は、Google のブランド資料から落として
`marketing/phase-1/SNS部/素材/store/google-play-badge.png` に置く。
置いてあれば**そちらを使う**(下の `_official()`)。無ければ自前の札のまま。

使い方:
    # 既存の mp4 に後から重ねる(絵は作り直さない。音はそのまま)
    py -3 tools/video_build/play_banner.py                 # 素材の全 mp4
    py -3 tools/video_build/play_banner.py f01_alarm...mp4 # 1本だけ
"""
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import FB, FT, H, PAPER, ROOT, W  # noqa: E402
import build_feature15 as F  # noqa: E402

OUT_DIR = F.OUT_DIR
ICON = F.ICON
OFFICIAL = os.path.join(OUT_DIR, "store", "google-play-badge.png")

# 字幕の帯の上端。札はここより上に置く(帯の文字と重ねない)。
BANDH = int(H * 0.245)
BTOP = H - BANDH

INK = (31, 59, 36)
SUB = (108, 134, 106)


def _official():
    """公式バッジが置いてあれば、それを使う。**加工しない。**"""
    if not os.path.exists(OFFICIAL):
        return None
    im = Image.open(OFFICIAL).convert("RGBA")
    # 高さだけ合わせる(縦横比は変えない = 規約どおり)。
    h = 112
    return im.resize((int(im.size[0] * h / im.size[1]), h), Image.LANCZOS)


def banner_layer():
    """1080x1920 の透明な板に、右下(帯のすぐ上)へ札を1つ描いて返す。"""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    badge = _official()
    pad = int(W * 0.045)
    hgt = 132
    y1 = BTOP - 26
    y0 = y1 - hgt

    if badge is not None:
        # 公式バッジは**そのまま置く**。背景も付けない(規約)。
        im.alpha_composite(badge, (W - pad - badge.size[0],
                                   y1 - (hgt + badge.size[1]) // 2))
        return im

    # 自前の札: アイコン + 2行。
    fn = ImageFont.truetype(FB, int(W * 0.023))
    fp = ImageFont.truetype(FT, int(W * 0.032))
    t1, t2 = "TORIS COLLECTION", "Free on Google Play"
    tw = max(d.textlength(t1, font=fn), d.textlength(t2, font=fp))
    icon = hgt - 34
    w = icon + 22 + int(tw) + 46
    x0 = W - pad - w

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle([x0, y0, x0 + w, y1], 30,
                                         fill=PAPER + (238,))
    im.alpha_composite(ov)

    ic = Image.open(ICON).convert("RGBA").resize((icon, icon), Image.LANCZOS)
    mask = Image.new("L", (icon, icon), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, icon - 1, icon - 1], fill=255)
    ic.putalpha(mask)
    im.alpha_composite(ic, (x0 + 22, y0 + 17))

    tx = x0 + 22 + icon + 22
    dd = ImageDraw.Draw(im)
    dd.text((tx, y0 + 24), t1, font=fn, fill=SUB)
    dd.text((tx, y0 + 58), t2, font=fp, fill=INK)
    return im


def stamp(path, layer_png):
    """出来上がった mp4 に札を重ねる。**音はそのまま**(再エンコードしない)。"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = path + ".tmp.mp4"
    r = subprocess.run(
        [ff, "-y", "-i", path, "-i", layer_png,
         "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", tmp],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-600:])
        raise SystemExit(f"重ねるのに失敗: {path}")
    os.replace(tmp, path)
    return os.path.getsize(path) // 1024


def main():
    layer_png = os.path.join(os.path.dirname(__file__), "_play_banner.png")
    banner_layer().save(layer_png)
    print("公式バッジ: " + ("使う" if _official() is not None
                            else "無いので自前の札"))

    names = sys.argv[1:]
    if not names:
        names = sorted(n for n in os.listdir(OUT_DIR)
                       if n.endswith(".mp4") and n[0] in "fgqr")
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(OUT_DIR, n)
        if not os.path.exists(p):
            print(f"  無い: {n}")
            continue
        print(f"  {os.path.basename(p)}  {stamp(p, layer_png)} KB")


if __name__ == "__main__":
    main()
