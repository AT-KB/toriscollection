"""型#4 サウンドクイズ: 声だけで当てっこ → コメント誘発(参加型)。
#1リビールとの違い: answerを引っ張る(考える"間"を作る)→ 最後に詳細ドット絵で答え合わせ。
実データ(実録音・実クレジット)のみ使用。

実行: py -3 tools/video_build/build_quiz.py [bird_key]
  bird_key: robin(既定) / songsparrow
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
FR = os.path.join(os.path.dirname(__file__), "_quiz")
os.makedirs(FR, exist_ok=True)
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")

W, H, FPS, DUR = 1080, 1920, 30, 15.0
N = int(FPS * DUR)
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"
DARK = (35, 48, 33)
SUB = (74, 92, 66)

# key: (detail sprite, 表示名, 音源, 音の頭出し, クレジット, 実生態の一言)
BIRDS = {
    "robin": ("american_robin", "American Robin", "American_Robin.mp3", 6,
              "Song: xeno-canto — Doug Hynes (CC BY-SA 4.0) #570791",
              "likes worms & berries"),
    "songsparrow": ("suzume", "Song Sparrow", "Song_Sparrow.mp3", 9,
                    "Song: xeno-canto — Ryan Douglas (CC BY-SA 4.0) #1005250",
                    "likes seeds & insects"),
}
KEY = sys.argv[1] if len(sys.argv) > 1 else "robin"
SPRITE, NAME, SONG, SS, CRED, LIKE = BIRDS[KEY]


def _bg():
    img = Image.new("RGB", (W, H))
    top, bot = (238, 242, 230), (224, 232, 212)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3)))
    return img


def _detail(bird_id, target_h=760):
    p = os.path.join(DB, bird_id + "_detail.png")
    if not os.path.exists(p):
        p = os.path.join(DB, bird_id + ".png")
    sp = Image.open(p).convert("RGBA")
    r, g, b, a = sp.split()
    a = a.point(lambda v: 0 if v < 130 else v)
    sp = Image.merge("RGBA", (r, g, b, a))
    sp = sp.crop(sp.getbbox())
    w, h = sp.size
    s = target_h / h
    return sp.resize((round(w * s), round(h * s)), Image.LANCZOS)


BG = _bg()
BIRD = _detail(SPRITE)
TT = ImageFont.truetype(FT, 78)
NM = ImageFont.truetype(FT, 72)
BD = ImageFont.truetype(FB, 50)
SM = ImageFont.truetype(FB, 44)
CF = ImageFont.truetype(FB, 26)


def ctext(d, txt, font, cy, fill):
    w = d.textlength(txt, font=font)
    bb = d.textbbox((0, 0), txt, font=font)
    d.text(((W - w) / 2, cy - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=font, fill=fill)


def wave(d, t, cy):
    """声に合わせた波形(考える"間"の視覚化)。"""
    n = 26
    for k in range(n):
        x = int(W * 0.16 + (W * 0.68) * k / (n - 1))
        amp = 60 * abs(math.sin(t * 3 + k * 0.6)) + 8
        d.rounded_rectangle([x - 8, cy - amp, x + 8, cy + amp], radius=8,
                            fill=(150, 180, 120))


REVEAL = 9.0


def render(i):
    t = i / FPS
    frame = BG.copy().convert("RGBA")
    d = ImageDraw.Draw(frame)
    if t < REVEAL:
        # クイズ中: 波形+問い(答えを見せない)
        ctext(d, "Real recording.", TT, H * 0.30, DARK)
        ctext(d, "What bird is this?", TT, H * 0.30 + 100, DARK)
        wave(d, t, H * 0.55)
        if t > 3.5:
            ctext(d, "Guess in the comments", BD, H * 0.72, SUB)
        if t > 6.5:
            ctext(d, "Answer in 3… 2… 1…", SM, H * 0.78, SUB)
    else:
        # 答え合わせ: 詳細ドット絵
        f = min(1.0, (t - REVEAL) / 0.4)
        sp = BIRD if f >= 1.0 else BIRD.resize(
            (max(1, int(BIRD.width * (0.85 + 0.15 * f))),
             max(1, int(BIRD.height * (0.85 + 0.15 * f)))), Image.LANCZOS)
        y = int(H * 0.42 - sp.height / 2 + 6 * math.sin(t * 2))
        frame.alpha_composite(sp, (int((W - sp.width) / 2), y))
        d = ImageDraw.Draw(frame)
        ctext(d, NAME, NM, H * 0.80, DARK)
        ctext(d, LIKE, SM, H * 0.80 + 78, SUB)
    if t >= 13.2:
        frame = BG.copy().convert("RGBA")
        d = ImageDraw.Draw(frame)
        ctext(d, "Collect birds by ear.", TT, H * 0.44, DARK)
        ctext(d, "Free on Android · link in bio", BD, H * 0.44 + 100, (90, 130, 70))
    d.text(((W - d.textlength(CRED, font=CF)) / 2, H - 58), CRED, font=CF, fill=(70, 86, 60))
    frame.convert("RGB").save(os.path.join(FR, f"f{i:04d}.png"))


print(f"rendering {N} frames ({KEY})...")
for i in range(N):
    render(i)

out_path = os.path.join(OUT, f"post13_quiz_{KEY}_1080x1920.mp4")
cmd = [FF, "-y", "-framerate", str(FPS), "-i", os.path.join(FR, "f%04d.png"),
       "-ss", str(SS), "-t", "12", "-i", os.path.join(RADIO, SONG),
       "-filter_complex",
       "[1:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.4,afade=t=out:st=13:d=1.5,"
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
cd = os.path.join(RAW, "quizchk")
os.makedirs(cd, exist_ok=True)
for t in [1, 5, 8, 10, 12, 14]:
    subprocess.run([FF, "-y", "-ss", str(t), "-i", out_path, "-frames:v", "1",
                    os.path.join(cd, f"t{t}.png")], capture_output=True, text=True)
print("done:", out_path)
