"""Sound Quiz の追加分(象徴的な鳥3種)を書き出す。build_week1_v4v5.py と同じ
セージ地+鳥+濃緑セリフのパイプライン(鳥の矩形seam修正済み)。

追加: Northern Cardinal / American Robin / Song Sparrow。実録音は radio_src/、
クレジットは radio_src/all_credit.json 由来(改変禁止・原則4)。各鳥の音源は
無音/間を避けたクリーンな窓を頭出しし、loudnorm で音量を揃える。

実行: py -3 tools/video_build/build_quiz_extra.py
"""
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材")
FRAME_DIR = os.path.join(ROOT, "imagepictures")
TMP = os.path.join(os.path.dirname(__file__), "_overlays")
os.makedirs(TMP, exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)

W, H = 1080, 1920
MARGIN = 96
USABLE = W - 2 * MARGIN
DARK = (35, 48, 33, 255)
SUB = (74, 92, 66, 255)
SAGE_RGB = (236, 241, 227)

FONT_TITLE = "C:/Windows/Fonts/georgiab.ttf"
FONT_BODY = "C:/Windows/Fonts/segoeui.ttf"

BIRD_SRC = os.path.join(ROOT, "android_app", "android", "app", "src", "main",
                        "res", "drawable-xxxhdpi", "splash_bird.png")
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")


def _make_bird_on_sage():
    bird = Image.open(BIRD_SRC).convert("RGBA")
    side = max(bird.size)
    canvas = Image.new("RGBA", (side, side), SAGE_RGB + (255,))
    canvas.alpha_composite(bird, ((side - bird.width) // 2, (side - bird.height) // 2))
    p = os.path.join(TMP, "bird_on_sage.png")
    canvas.save(p)
    return p


def _make_sage_base():
    p = os.path.join(TMP, "sage_base.png")
    Image.new("RGB", (W, H), SAGE_RGB).save(p)
    return p


BIRD = _make_bird_on_sage()
SAGE_BASE = _make_sage_base()


def _font(p, s):
    return ImageFont.truetype(p, s)


def _wrap(draw, text, font, mw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            t = w if not cur else cur + " " + w
            if draw.textlength(t, font=font) <= mw:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _draw_block(img, blocks, cy):
    d = ImageDraw.Draw(img)
    r = []
    for text, font, fill in blocks:
        for line in _wrap(d, text, font, USABLE):
            bb = d.textbbox((0, 0), line, font=font)
            r.append((line, font, fill, bb[2] - bb[0], bb[3] - bb[1], bb[1]))
    gap = 18
    total = sum(x[4] for x in r) + gap * (len(r) - 1)
    y = cy - total / 2
    for line, font, fill, lw, lh, oy in r:
        cx = (W - lw) / 2
        d.text((cx + 1, y - oy + 2), line, font=font, fill=(255, 255, 255, 90))
        d.text((cx, y - oy), line, font=font, fill=fill)
        y += lh + gap


def overlay(name, blocks, cy):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, blocks, cy)
    p = os.path.join(TMP, name + ".png")
    img.save(p)
    return p


def credit(name, text, size=29):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, [(text, _font(FONT_BODY, size), SUB)], H - 150)
    p = os.path.join(TMP, name + ".png")
    img.save(p)
    return p


TITLE = lambda s: _font(FONT_TITLE, s)
BODY = lambda s: _font(FONT_BODY, s)


def build(out_name, audio_path, ss, reveal, cred, key):
    items = [
        (overlay(key + "_hook", [("Real recording.\nWhat bird is this?", TITLE(74), DARK)], H * 0.55), 0.0, 2.2),
        (overlay(key + "_guess", [("Guess…", BODY(60), SUB)], H * 0.55), 2.2, 5.0),
        (overlay(key + "_here", [("Here it is —", BODY(58), SUB)], H * 0.55), 5.0, 7.0),
        (overlay(key + "_name", [(reveal, TITLE(76 if len(reveal) < 16 else 64), DARK)], H * 0.55), 7.0, 12.0),
        (overlay(key + "_cta", [("Comment your guess —\nI'll pin the answer.", BODY(54), DARK)], H * 0.55), 12.0, 15.0),
        (credit(key + "_credit", cred), 2.2, 15.0),
    ]
    audio_filter = (
        f"[1:a]atrim={ss}:{ss+7},asetpts=PTS-STARTPTS,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "afade=t=out:st=6:d=1.0,apad=whole_dur=15,"
        "aformat=sample_rates=44100:channel_layouts=stereo[aout]"
    )
    out_path = os.path.join(OUT_DIR, out_name)
    cmd = [FFMPEG, "-y", "-loop", "1", "-t", "15", "-i", SAGE_BASE,
           "-i", audio_path, "-loop", "1", "-i", BIRD]
    for png, _, _ in items:
        cmd += ["-loop", "1", "-i", png]
    fc = ["[0:v]fps=30,format=rgba[base]", "[2:v]scale=470:-1[bird]",
          "[base][bird]overlay=x=(W-w)/2:y='(H*0.20)+16*sin(2*t)'[bg]"]
    cur = "bg"
    for i, (png, s, e) in enumerate(items):
        nxt = f"v{i}"
        fc.append(f"[{cur}][{i+3}:v]overlay=0:0:enable='between(t,{s},{e})'[{nxt}]")
        cur = nxt
    fc.append(audio_filter)
    cmd += ["-filter_complex", ";".join(fc), "-map", f"[{cur}]", "-map", "[aout]",
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-t", "15",
            "-movflags", "+faststart", out_path]
    print("building", out_name)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2500:]); sys.exit("ffmpeg failed " + out_name)
    p = subprocess.run([FFMPEG, "-i", out_path], capture_output=True, text=True)
    for ln in p.stderr.splitlines():
        if "Duration" in ln or "Stream #" in ln:
            print("  " + ln.strip())
    for lbl, t in [("hook", 1.0), ("name", 9.0)]:
        fp = os.path.join(FRAME_DIR, key + "_frame_" + lbl + ".png")
        subprocess.run([FFMPEG, "-y", "-ss", str(t), "-i", out_path, "-frames:v", "1", fp],
                       capture_output=True, text=True)
        print("  frame:", fp)


# (out_name, mp3, ss起点, リビール名, クレジット, キー)
QUIZZES = [
    ("post6_sound_quiz_cardinal_1080x1920.mp4", os.path.join(RADIO, "Northern_Cardinal.mp3"),
     8, "Northern Cardinal", "Rec: steve · CC BY-SA 4.0 · xeno-canto #797998", "post6"),
    ("post7_sound_quiz_robin_1080x1920.mp4", os.path.join(RADIO, "American_Robin.mp3"),
     6, "American Robin", "Rec: Doug Hynes · CC BY-SA 4.0 · xeno-canto #570791", "post7"),
    ("post8_sound_quiz_songsparrow_1080x1920.mp4", os.path.join(RADIO, "Song_Sparrow.mp3"),
     9, "Song Sparrow", "Rec: Ryan Douglas · CC BY-SA 4.0 · xeno-canto #1005250", "post8"),
]

for q in QUIZZES:
    build(*q)
print("done.")
