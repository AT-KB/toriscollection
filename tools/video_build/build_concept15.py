"""15秒のコンセプト動画を**組み立てて**作る(画面録画ではない)。

## なぜ作ったか(2026-08-18)
CEO「S5全然機能していない」「意図が伝わらない、何を見せられてるの？」
「テーマを絞ってほしい」「必ずしも実機の撮影ではなくていい」。

画面録画版(`build_showcase.py` の tiktok15)には限界がある:
 - アプリのUI(土地の切替・チップ・タブ)が常に映り、初見の人には雑音。
 - いちばん見せたい「鳥が来る瞬間」が、実時間でしか起きないので撮れない。
 - 図鑑の「なぜ来たか」は画面の下にあり、字幕の帯に隠れて映らない。

そこで**組み立てる**。ただし守ることが2つある:

**(1) 絵は本物を使う。** 鳥は `toris_app/assets/sprites/` の、アプリに
入っているドット絵そのもの。宣伝用に描き起こした別物は使わない。

**(2) 言うことは本当のことだけ。** アプリがしないことは言わない。
「捕まえない/鳥が自分で来る」は実装そのもの(押して進める仕掛けは無く、
到来は留守のあいだに確率で起きる)。交渉不能の原則4「生態に誠実」は
宣伝物にも効く。

## テーマは1本
    「捕まえない。鳥が自分で来る。」
ラジオも目覚ましも図鑑の全体も**出さない**。それらは別の動画でやる。

実行:
    py -3 tools/video_build/build_concept15.py
"""
import json
import math
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "toris_collection"))

SPRITES = os.path.join(ROOT, "toris_app", "assets", "sprites")
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")
OUT = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材",
                   "s08_concept_built_15s_1080x1920.mp4")

W, H, FPS, DUR = 1080, 1920, 30, 15.0
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"

# 画面写真から採った色。アプリの庭と同じ見え方にする。
SKY_TOP = (226, 238, 243)
SKY_LOW = (233, 242, 231)
HOUSE = (226, 219, 205)
WINDOW = (198, 214, 221)
WOOD = (150, 120, 90)
CANOPY = (168, 206, 142)
CANOPY_D = (146, 188, 120)
TRUNK = (139, 112, 84)
LAWN = (150, 197, 121)
LAWN_D = (132, 180, 104)
BAND = (24, 34, 22)
PAPER = (243, 249, 236)
MUTED = (178, 205, 165)

# 主役。**アプリに入っている種**から選ぶ。
# CEO 2026-08-18「Jayとかみたいな、Detailのが映るほうが好ましい」。
# 図鑑の詳細画(1024px)を大きく使う。
BIRD = "blue_jay"
BIRD_NAME = "Blue Jay"

# ## 言うことは**2つだけ**(CEO「メッセージ数が多すぎる」)
#
# 15秒に4行入れたら、読んでいるうちに絵が変わって何も残らなかった。
# 伝えたいことは1つ ——「捕まえない。鳥が自分で来る」。
# それを前半と後半の2行に割るだけにして、あとは**絵に語らせる**。
#
# 動く出来事も**1つだけ**にする。植えるところは見せない(前は植物がせり上がる
# 動きと鳥の飛来がぶつかって、どっちが本題か分からなかった)。
# 庭は最初から出来上がっていて、起きることは**鳥が来ること**だけ。
LINE_1 = "You don't catch them."
LINE_2 = "They come to you."

FLY_IN, LAND = 3.6, 6.4      # 飛び始め / とまる
CLOSE_UP = 9.0               # ここから寄って、図鑑の絵に変わる
#                              とまってから **2.6秒そのまま**見せる。
#                              ここが本題なので、すぐ切り替えない。
#                              とまってから 1.2 秒**そのまま見せる**。
#                              すぐ寄ると「来た」ことが読み取れない。


def credits_line():
    """使う録音と、その録音者。**配布可のものだけ**を使う。"""
    rows = json.load(open(os.path.join(RADIO, "all_credit.json"),
                          encoding="utf-8"))
    names, used = [], []
    for r in rows:
        f = r["file"]
        if not os.path.exists(f):
            continue
        used.append(f)
        rec = (r.get("rec") or "").strip()
        if rec and rec not in names:
            names.append(rec)
    if not used:
        raise SystemExit("配布可の録音が無い。landing/media/radio_src を確認")
    return used, "Songs: xeno-canto — " + ", ".join(names[:4])


def fit(d, text, path, start, max_w):
    size = start
    while size > 16:
        f = ImageFont.truetype(path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(path, 16)


def ease(t):
    """0→1 をなめらかに。急に動かない(原則1「受動的である」)。"""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ── 庭を描く ───────────────────────────────────────────────
GROUND = int(H * 0.62)      # 芝の上端
BRANCH_Y = int(H * 0.335)   # 鳥がとまる枝の高さ
BRANCH_X = int(W * 0.52)


def draw_garden(d, plants_in):
    """裏庭。[plants_in] は 0→1 で、植えたものがせり上がる量。"""
    for y in range(GROUND):
        k = y / GROUND
        d.line([(0, y), (W, y)], fill=(
            int(SKY_TOP[0] + (SKY_LOW[0] - SKY_TOP[0]) * k),
            int(SKY_TOP[1] + (SKY_LOW[1] - SKY_TOP[1]) * k),
            int(SKY_TOP[2] + (SKY_LOW[2] - SKY_TOP[2]) * k)))

    # 家の角(左)。アメリカの裏庭らしさはここで出る。
    d.rectangle([0, int(H * 0.10), int(W * 0.22), GROUND], fill=HOUSE)
    d.rectangle([int(W * 0.05), int(H * 0.16), int(W * 0.16), int(H * 0.27)],
                fill=WINDOW)

    # 芝
    d.rectangle([0, GROUND, W, H], fill=LAWN)
    d.rectangle([0, GROUND, W, GROUND + 8], fill=LAWN_D)

    # 木(幹 → 枝 → 葉)
    d.rectangle([BRANCH_X - 22, BRANCH_Y, BRANCH_X + 22, GROUND], fill=TRUNK)
    d.ellipse([BRANCH_X - 300, BRANCH_Y - 250, BRANCH_X + 300, BRANCH_Y + 110],
              fill=CANOPY)
    d.ellipse([BRANCH_X - 190, BRANCH_Y - 300, BRANCH_X + 170, BRANCH_Y + 30],
              fill=CANOPY_D)
    d.rectangle([BRANCH_X - 250, BRANCH_Y + 4, BRANCH_X + 250, BRANCH_Y + 16],
                fill=WOOD)

    # 餌台(右)。開放型 — アプリで選べるものと同じかたち。
    fx = int(W * 0.80)
    d.rectangle([fx - 8, int(H * 0.40), fx + 8, GROUND], fill=WOOD)
    d.rectangle([fx - 70, int(H * 0.40), fx + 70, int(H * 0.425)], fill=WOOD)
    d.polygon([(fx - 80, int(H * 0.40)), (fx + 80, int(H * 0.40)),
               (fx, int(H * 0.355))], fill=(122, 96, 70))

    # 植えたもの。**もう咲いている**(植える動きは見せない。本題は鳥が来ること)。
    for i, px in enumerate([0.30, 0.40, 0.66, 0.74]):
        cx = int(W * px)
        d.rectangle([cx - 4, GROUND - 30, cx + 4, GROUND + 40],
                    fill=(96, 148, 78))
        d.ellipse([cx - 20, GROUND - 50, cx + 20, GROUND - 10],
                  fill=(226, 142, 176) if i % 2 == 0 else (150, 106, 190))


def draw_band(im, d, head, sub, credit, appear):
    """字幕の帯。**塗りつぶす**(透けると下の絵と混ざって読めない)。"""
    band = int(H * 0.245)
    top = H - band
    fade = int(band * 0.10)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for i in range(fade):
        od.line([(0, top + i), (W, top + i)],
                fill=BAND + (int(255 * i / fade),))
    od.rectangle([0, top + fade, W, H], fill=BAND + (255,))
    im.alpha_composite(ov)

    pad = int(W * 0.06)
    d.text((pad, top + int(band * 0.13)), "TORIS COLLECTION",
           font=ImageFont.truetype(FT, int(W * 0.029)), fill=(139, 168, 128))

    # 見出しは下から少し上がってくる(切り替わりが分かる)
    dy = int((1 - ease(appear)) * 26)
    fh = fit(d, head, FT, int(W * 0.064), W - pad * 2)
    d.text((pad, top + int(band * 0.31) + dy), head, font=fh, fill=PAPER)
    if sub:
        d.text((pad, top + int(band * 0.62) + dy), sub,
               font=ImageFont.truetype(FB, int(W * 0.031)), fill=MUTED)
    d.text((pad, H - int(band * 0.15)), credit,
           font=ImageFont.truetype(FB, max(12, int(W * 0.018))),
           fill=(132, 156, 126))


def zoom_to(im, cx, cy, z):
    """[cx,cy] を中心に z 倍に寄る。寄っても画面の外を映さない。"""
    if z <= 1.001:
        return im
    big = im.resize((int(W * z), int(H * z)), Image.LANCZOS)
    x = int(cx * z - W / 2)
    y = int(cy * z - H / 2)
    x = max(0, min(int(W * z) - W, x))
    y = max(0, min(int(H * z) - H, y))
    return big.crop((x, y, x + W, y + H))


def draw_detail(im, d, t):
    """図鑑の詳細画(1024px)を大きく出す。

    CEO 2026-08-18「Jayとかみたいな、Detailのが映るほうが好ましい」。
    ドット絵の小さいのは庭に居るとき用で、**顔を見せるのはこちら**。
    """
    if t <= 0:
        return
    k = ease(t)
    src = Image.open(os.path.join(SPRITES, f"{BIRD}_detail.png")).convert("RGBA")
    side = int(W * 0.66)
    src = src.resize((side, int(side * src.size[1] / src.size[0])),
                     Image.LANCZOS)
    if k < 1.0:
        a = src.getchannel("A").point(lambda v: int(v * k))
        src.putalpha(a)
    x = (W - src.size[0]) // 2
    y = int(H * 0.30) - src.size[1] // 2 + int((1 - k) * 40)
    im.alpha_composite(src, (x, max(0, y)))

    if k > 0.55:
        f = ImageFont.truetype(FT, int(W * 0.046))
        tw = d.textlength(BIRD_NAME, font=f)
        ty = max(0, y) + src.size[1] + 16
        # 名前の下地。木の緑に濃い字を直接置くと読めなかった。
        plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            [(W - tw) / 2 - 30, ty - 14, (W + tw) / 2 + 30, ty + 68], 26,
            fill=(247, 250, 242, 235))
        im.alpha_composite(plate)
        ImageDraw.Draw(im).text(((W - tw) / 2, ty), BIRD_NAME, font=f,
                                fill=(31, 59, 36))


def main():
    used, credit = credits_line()
    tmp = os.path.join(os.path.dirname(__file__), "_built")
    os.makedirs(tmp, exist_ok=True)

    small = Image.open(os.path.join(SPRITES, f"{BIRD}.png")).convert("RGBA")
    # 庭に居るときの姿は**大きめに**。小さいと、来たことが一目で分からない
    # (CEO 2026-08-18「鳥が来ている様子がパット分からない」)。
    small = small.resize((230, 230), Image.NEAREST)

    n = int(DUR * FPS)
    for f in range(n):
        t = f / FPS
        im = Image.new("RGBA", (W, H), SKY_TOP + (255,))
        d = ImageDraw.Draw(im)
        draw_garden(d, 1.0)
        # 出だしは**ごくゆっくり引く**。完全に止まった絵は飛ばされる
        # (診断書 2026-08-08「止まって見える瞬間を作らない」)。
        if t < FLY_IN + 1.0:
            im = zoom_to(im, W // 2, int(H * 0.42),
                         1.05 - 0.05 * ease(t / (FLY_IN + 1.0)))
            d = ImageDraw.Draw(im)

        # **起きることはこれ1つ。** 右の外から入ってきて、枝にとまる。
        if FLY_IN <= t < CLOSE_UP + 0.5:
            k = ease((t - FLY_IN) / (LAND - FLY_IN))
            bx = int(W * 1.12 + (BRANCH_X - 40 - W * 1.12) * k)
            by = int(H * 0.10 + (BRANCH_Y - 205 - H * 0.10) * k)
            if k < 1.0:
                by += int(math.sin(t * 8.5) * 18 * (1 - k))
            im.alpha_composite(small, (bx, by))

        # とまったあと、枝へ寄る。寄りながら図鑑の絵に変わる。
        if t >= CLOSE_UP:
            im = zoom_to(im, BRANCH_X, BRANCH_Y - 90,
                         1.0 + 0.85 * ease((t - CLOSE_UP) / 1.8))
            d = ImageDraw.Draw(im)
            draw_detail(im, d, (t - CLOSE_UP - 0.5) / 1.1)
            d = ImageDraw.Draw(im)

        if t < CLOSE_UP:
            head, appear = LINE_1, t / 0.6
        else:
            head, appear = LINE_2, (t - CLOSE_UP) / 0.6
        draw_band(im, d, head, None, credit, appear)
        im.convert("RGB").save(os.path.join(tmp, f"f{f:04d}.png"))

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    silent = os.path.join(tmp, "silent.mp4")
    r = subprocess.run(
        [ff, "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", silent],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit("連番の書き出しに失敗")

    ain, amix = [], []
    for i, aud in enumerate(used[:4]):
        ain += ["-i", aud]
        delay = int(i * (DUR / 4) * 1000)
        amix.append(f"[{i+1}:a]atrim=0:{DUR},adelay={delay}|{delay},"
                    f"volume=0.55[a{i}]")
    mix = "".join(x + ";" for x in amix)
    mix += "".join(f"[a{i}]" for i in range(len(amix)))
    mix += f"amix=inputs={len(amix)}:duration=first:dropout_transition=2,"
    mix += f"afade=t=in:st=0:d=0.6,afade=t=out:st={DUR-1.2}:d=1.2[aout]"
    r = subprocess.run(
        [ff, "-y", "-i", silent] + ain +
        ["-filter_complex", mix, "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", str(DUR),
         "-movflags", "+faststart", OUT],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit("音の合成に失敗")
    print(f"  {os.path.relpath(OUT, ROOT)}  "
          f"{os.path.getsize(OUT)//1024} KB  {DUR}秒  {W}x{H}")
    print(f"  {credit}")


if __name__ == "__main__":
    main()
