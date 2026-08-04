"""旗艦(図鑑リビール型): 最強アセット=詳細ドット絵を主役に。
「♪ 本物の録音 — 誰が鳴いてる? 」謎のシルエット → 開いて色づき精密な鳥が現れる(本物の声)。
oddly-satisfying なリビール+ASMR。全フレーム PIL 描画 → ffmpeg。

実行: py -3 tools/video_build/build_reveal.py
"""
import math
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "toris_collection", "designbird")
OUT = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材")
RAW = os.path.join(OUT, "raw")
FR = os.path.join(os.path.dirname(__file__), "_rev")
os.makedirs(FR, exist_ok=True)

W, H, FPS, DUR = 1080, 1920, 30, 15.0
N = int(FPS * DUR)
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"
DARK = (35, 48, 33)
SUB = (74, 92, 66)
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")


def _card_bg():
    """やわらかな図鑑カード風の地(セージ→クリームの縦グラデ + 淡い枠)。"""
    img = Image.new("RGB", (W, H))
    top = (238, 242, 230)
    bot = (224, 232, 212)
    dr = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        dr.line([(0, y), (W, y)], fill=tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3)))
    return img


def _detail(bird_id, target_h=880):
    sp = Image.open(os.path.join(DB, bird_id + "_detail.png")).convert("RGBA")
    # 低α背景ピクセル(薄いグリッド等)を完全透明にして地の残りを消す
    r, g, b, a = sp.split()
    a = a.point(lambda v: 0 if v < 130 else v)
    sp = Image.merge("RGBA", (r, g, b, a))
    sp = sp.crop(sp.getbbox())
    w, h = sp.size
    s = target_h / h
    return sp.resize((round(w * s), round(h * s)), Image.LANCZOS)


BG = _card_bg()
CARD = {"cardinal": _detail("northern_cardinal"), "bluejay": _detail("blue_jay")}
TT = ImageFont.truetype(FT, 84)
NM = ImageFont.truetype(FT, 78)
BD = ImageFont.truetype(FB, 50)
SM = ImageFont.truetype(FB, 44)
CF = ImageFont.truetype(FB, 26)


def _silhouette(sp):
    """色を落とした濃いシルエット(α保持)。"""
    r, g, b, a = sp.split()
    dark = Image.new("L", sp.size, 40)
    return Image.merge("RGBA", (dark, Image.new("L", sp.size, 52), dark, a))


SIL = {k: _silhouette(v) for k, v in CARD.items()}


def _ctext(d, lines, cy):
    sizes = []
    tot = 0
    for txt, f, fill in lines:
        bb = d.textbbox((0, 0), txt, font=f)
        sizes.append((bb[2] - bb[0], bb[3] - bb[1], bb[1]))
        tot += bb[3] - bb[1]
    tot += 16 * (len(lines) - 1)
    y = cy - tot / 2
    for (txt, f, fill), (lw, lh, oy) in zip(lines, sizes):
        d.text(((W - lw) / 2, y - oy), txt, font=f, fill=fill)
        y += lh + 16


# (key, 表示名, 好きなもの(実際の餌), 開始, リビール時刻, 終了)
SCHED = [
    ("cardinal", "Northern Cardinal", "likes sunflower seeds", 0.0, 3.2, 6.8),
    ("bluejay", "Blue Jay", "likes acorns & insects", 6.8, 9.6, 12.6),
]
BIRD_CY = H * 0.40


def render(i):
    t = i / FPS
    frame = BG.copy()
    active = None
    for key, name, like, ti, tr, to in SCHED:
        if ti <= t < to:
            active = (key, name, like, ti, tr, to)
            break
    d = ImageDraw.Draw(frame)
    if active:
        key, name, like, ti, tr, to = active
        sp = CARD[key]
        sil = SIL[key]
        x = int((W - sp.width) / 2)
        y = int(BIRD_CY - sp.height / 2 + 6 * math.sin((t - ti) * 2))
        base = frame.convert("RGBA")
        if t < tr:
            base.alpha_composite(sil, (x, y))
        elif t < tr + 0.5:
            # 0.5秒でシルエット→色にクロスフェード
            f = (t - tr) / 0.5
            blend = Image.blend(sil.convert("RGBA"), sp, f)
            base.alpha_composite(blend, (x, y))
        else:
            base.alpha_composite(sp, (x, y))
        frame = base.convert("RGB")
        d = ImageDraw.Draw(frame)
        if t < tr:
            _ctext(d, [("Real recording.", TT, DARK),
                       ("Who's singing?", TT, DARK)], H * 0.82)
        else:
            _ctext(d, [(name, NM, DARK),
                       (like, SM, SUB)], H * 0.82)
    if t >= 12.6:
        frame = BG.copy()
        d = ImageDraw.Draw(frame)
        _ctext(d, [("Collect real birds", TT, DARK),
                   ("by their songs", TT, DARK),
                   ("", BD, SUB),
                   ("real recordings · free on Android", BD, SUB),
                   ("link in bio", BD, (90, 130, 70))], H * 0.5)
    cred = "Songs: xeno-canto — steve (CC BY-SA 4.0) · Anonymous (CC0)"
    cw = d.textlength(cred, font=CF)
    d.text(((W - cw) / 2, H - 60), cred, font=CF, fill=(70, 86, 60))
    frame.save(os.path.join(FR, f"f{i:04d}.png"))


print(f"rendering {N} frames...")
for i in range(N):
    render(i)
    if i % 90 == 0:
        print("  ", i)

out_path = os.path.join(OUT, "post11_reveal_1080x1920.mp4")
card_song = os.path.join(RADIO, "Northern_Cardinal.mp3")
jay_song = os.path.join(RADIO, "Blue_Jay.mp3")
cmd = [FF, "-y", "-framerate", str(FPS), "-i", os.path.join(FR, "f%04d.png"),
       "-ss", "8", "-t", "6.8", "-i", card_song,
       "-ss", "0", "-t", "5.8", "-i", jay_song,
       "-filter_complex",
       "[1:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.3[c];"
       "[2:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.3[j];"
       "[c][j]concat=n=2:v=0:a=1,afade=t=out:st=13.5:d=1.5,apad=whole_dur=15,"
       "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
       "-map", "0:v", "-map", "[aout]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
       "-r", "30", "-t", "15", "-c:a", "aac", "-ar", "44100", "-ac", "2",
       "-movflags", "+faststart", out_path]
print("encoding...")
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-2500:]); sys.exit("ffmpeg failed")
p = subprocess.run([FF, "-i", out_path], capture_output=True, text=True)
for ln in p.stderr.splitlines():
    if "Duration" in ln or "Stream #" in ln:
        print("  " + ln.strip())
cd = os.path.join(RAW, "revchk")
os.makedirs(cd, exist_ok=True)
for t in [1, 2, 3, 4, 5, 7, 8, 10, 11, 13, 14]:
    subprocess.run([FF, "-y", "-ss", str(t), "-i", out_path, "-frames:v", "1",
                    os.path.join(cd, f"t{t}.png")], capture_output=True, text=True)
print("done:", out_path)
