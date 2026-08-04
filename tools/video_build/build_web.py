"""旗艦(ネットワーク/食物網 型): 「なぜその鳥が来るのか=本物の生態で繋がっている」を見せる。
🌸植物 → 🐛虫 → 詳細ドット絵の鳥、と連鎖が下へ繋がっていく。差別化の核(遊ぶほど生態系がわかる)。
全フレーム PIL 描画 → ffmpeg。

実行: py -3 tools/video_build/build_web.py
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
FR = os.path.join(os.path.dirname(__file__), "_web")
os.makedirs(FR, exist_ok=True)

W, H, FPS, DUR = 1080, 1920, 30, 15.0
N = int(FPS * DUR)
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"
EMJ = "C:/Windows/Fonts/seguiemj.ttf"
DARK = (35, 48, 33)
SUB = (74, 92, 66)
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")


def _bg():
    img = Image.new("RGB", (W, H))
    top, bot = (238, 242, 230), (224, 232, 212)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3)))
    return img


def _detail(bird_id, target_h):
    sp = Image.open(os.path.join(DB, bird_id + "_detail.png")).convert("RGBA")
    r, g, b, a = sp.split()
    a = a.point(lambda v: 0 if v < 130 else v)
    sp = Image.merge("RGBA", (r, g, b, a)).crop(Image.merge("RGBA", (r, g, b, a)).getbbox())
    w, h = sp.size
    s = target_h / h
    return sp.resize((round(w * s), round(h * s)), Image.LANCZOS)


BG = _bg()
CARDINAL = _detail("northern_cardinal", 300)
TT = ImageFont.truetype(FT, 66)
NM = ImageFont.truetype(FT, 60)
LB = ImageFont.truetype(FB, 46)
BD = ImageFont.truetype(FB, 48)
CF = ImageFont.truetype(FB, 26)
EMF = ImageFont.truetype(EMJ, 96)


def emoji(frame, ch, cx, cy):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(layer)
    dd.text((cx, cy), ch, font=EMF, embedded_color=True, anchor="mm")
    frame.alpha_composite(layer)


def ctext(d, txt, font, cy, fill):
    w = d.textlength(txt, font=font)
    bb = d.textbbox((0, 0), txt, font=font)
    d.text(((W - w) / 2, cy - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=font, fill=fill)


def arrow(d, y0, y1, prog):
    """縦の連結矢印を prog(0..1)で下へ伸ばす。"""
    x = W // 2
    yy = int(y0 + (y1 - y0) * prog)
    d.line([(x, y0), (x, yy)], fill=(120, 150, 95), width=8)
    if prog >= 0.98:
        d.polygon([(x - 16, y1 - 20), (x + 16, y1 - 20), (x, y1)], fill=(120, 150, 95))


PLANT_Y, INS_Y, BIRD_Y = 300, 720, 1200


def render(i):
    t = i / FPS
    frame = BG.copy().convert("RGBA")
    d = ImageDraw.Draw(frame)
    # 矢印(連鎖が繋がる)
    if t >= 2.0:
        arrow(d, PLANT_Y + 130, INS_Y - 110, min(1.0, (t - 2.0) / 0.7))
    if t >= 4.0:
        arrow(d, INS_Y + 110, BIRD_Y - 170, min(1.0, (t - 4.0) / 0.7))
    # ノード出現
    if t >= 0.4:
        emoji(frame, "🌸", W // 2, PLANT_Y)
        ctext(d, "Flowering Dogwood", LB, PLANT_Y + 105, SUB)
    if t >= 2.7:
        emoji(frame, "🐛", W // 2, INS_Y)
        ctext(d, "Tent Caterpillar", LB, INS_Y + 100, SUB)
    if t >= 4.7:
        frame.alpha_composite(CARDINAL, (int((W - CARDINAL.width) / 2), int(BIRD_Y - CARDINAL.height / 2)))
        ctext(d, "Northern Cardinal", NM, BIRD_Y + CARDINAL.height // 2 + 40, DARK)
    # 説明テキスト
    if t < 4.7:
        ctext(d, "Why does a cardinal visit?", TT, 130, DARK)
    elif t < 11.5:
        ctext(d, "A real food web — from GloBI.", TT, 130, DARK)
        ctext(d, "Plant the right thing,", BD, H - 300, SUB)
        ctext(d, "and the right bird comes.", BD, H - 240, SUB)
    if t >= 11.5:
        frame = BG.copy().convert("RGBA")
        d = ImageDraw.Draw(frame)
        ctext(d, "Grow a real ecosystem.", TT, H * 0.42, DARK)
        ctext(d, "Real birds. Real recorded songs.", BD, H * 0.42 + 110, SUB)
        ctext(d, "Free on Android · link in bio", BD, H * 0.42 + 175, (90, 130, 70))
    # クレジット
    d.text(((W - d.textlength("Song: xeno-canto — steve (CC BY-SA 4.0)", font=CF)) / 2, H - 58),
           "Song: xeno-canto — steve (CC BY-SA 4.0)", font=CF, fill=(70, 86, 60))
    frame.convert("RGB").save(os.path.join(FR, f"f{i:04d}.png"))


print(f"rendering {N} frames...")
for i in range(N):
    render(i)
    if i % 90 == 0:
        print("  ", i)

out_path = os.path.join(OUT, "post12_web_1080x1920.mp4")
cmd = [FF, "-y", "-framerate", str(FPS), "-i", os.path.join(FR, "f%04d.png"),
       "-ss", "8", "-t", "15", "-i", os.path.join(RADIO, "Northern_Cardinal.mp3"),
       "-filter_complex",
       "[1:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.5,afade=t=out:st=13.5:d=1.5,"
       "apad=whole_dur=15,aformat=sample_rates=44100:channel_layouts=stereo[aout]",
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
cd = os.path.join(RAW, "webchk")
os.makedirs(cd, exist_ok=True)
for t in [1, 3, 5, 7, 9, 13]:
    subprocess.run([FF, "-y", "-ss", str(t), "-i", out_path, "-frames:v", "1",
                    os.path.join(cd, f"t{t}.png")], capture_output=True, text=True)
print("done:", out_path)
