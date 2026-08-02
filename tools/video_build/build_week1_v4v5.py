"""Phase 1 第1週の追加2本(V4 Sound Quiz #2 = Blue Jay / V5 価値観ピース)を書き出す.

build_week1_v2v3.py と同じ「セージ地+鳥のドット絵+濃緑セリフ」の世界観を踏襲。
- V4: Blue Jay の実録音(radio_src/Blue_Jay.mp3・CC0・xeno-canto #924514。冒頭から連続して
  明瞭に鳴っている=クイズ向き)で「What bird is this?」→ 鳥名リビール。
- V5: 受動的・無料の価値観を静かに宣言(原則1・原則3)。庭のラジオ(5種ミックス)。

改善: 鳥PNGを一度セージ地に合成してから重ね、背後の薄い矩形(前バッチで僅かに見えた)を解消。

実行: py -3 tools/video_build/build_week1_v4v5.py
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
SAGE_HEX = "0xECF1E3"

FONT_TITLE = "C:/Windows/Fonts/georgiab.ttf"
FONT_BODY = "C:/Windows/Fonts/segoeui.ttf"

BIRD_SRC = os.path.join(ROOT, "android_app", "android", "app", "src", "main",
                        "res", "drawable-xxxhdpi", "splash_bird.png")
BLUEJAY = os.path.join(ROOT, "landing", "media", "radio_src", "Blue_Jay.mp3")
GARDEN = os.path.join(ROOT, "landing", "media", "garden_radio.mp3")


def _make_bird_on_sage():
    """鳥をセージ地(不透明)に合成した正方PNGを作る。セージ base(同色PNG)に重ねると
    RGB→YUV変換が同一経路になり継ぎ目が出ない(lavfi色ソースとPNGでは変換が微妙に異なり
    矩形が薄く見えたため、背景もPNGに統一する)。"""
    bird = Image.open(BIRD_SRC).convert("RGBA")
    side = max(bird.size)
    canvas = Image.new("RGBA", (side, side), SAGE_RGB + (255,))
    canvas.alpha_composite(bird, ((side - bird.width) // 2, (side - bird.height) // 2))
    path = os.path.join(TMP, "bird_on_sage.png")
    canvas.save(path)
    return path


def _make_sage_base():
    """1080x1920 のセージ地 PNG(背景)。bird_on_sage と同じ色経路にするため lavfi ではなく PNG。"""
    img = Image.new("RGB", (W, H), SAGE_RGB)
    path = os.path.join(TMP, "sage_base.png")
    img.save(path)
    return path


BIRD = _make_bird_on_sage()
SAGE_BASE = _make_sage_base()


def _font(path, size):
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def _draw_block(img, blocks, center_y):
    draw = ImageDraw.Draw(img)
    rendered = []
    for text, font, fill in blocks:
        for line in _wrap(draw, text, font, USABLE):
            bbox = draw.textbbox((0, 0), line, font=font)
            rendered.append((line, font, fill, bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]))
    gap = 18
    total_h = sum(r[4] for r in rendered) + gap * (len(rendered) - 1)
    cy = center_y - total_h / 2
    for line, font, fill, lw, lh, oy in rendered:
        cx = (W - lw) / 2
        draw.text((cx + 1, cy - oy + 2), line, font=font, fill=(255, 255, 255, 90))
        draw.text((cx, cy - oy), line, font=font, fill=fill)
        cy += lh + gap


def make_overlay(name, blocks, center_y):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, blocks, center_y)
    path = os.path.join(TMP, name + ".png")
    img.save(path)
    return path


def make_credit(name, text, size=29):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, [(text, _font(FONT_BODY, size), SUB)], center_y=H - 150)
    path = os.path.join(TMP, name + ".png")
    img.save(path)
    return path


def build(out_name, audio_path, audio_filter, ov_list, frames):
    out_path = os.path.join(OUT_DIR, out_name)
    cmd = [FFMPEG, "-y",
           "-loop", "1", "-t", "15", "-i", SAGE_BASE,
           "-i", audio_path,
           "-loop", "1", "-i", BIRD]
    for png, _, _ in ov_list:
        cmd += ["-loop", "1", "-i", png]
    fc = ["[0:v]fps=30,format=rgba[base]",
          "[2:v]scale=470:-1[bird]",
          "[base][bird]overlay=x=(W-w)/2:y='(H*0.20)+16*sin(2*t)'[bg]"]
    cur = "bg"
    for idx, (png, s, e) in enumerate(ov_list):
        inp = idx + 3
        nxt = f"v{idx}"
        fc.append(f"[{cur}][{inp}:v]overlay=0:0:enable='between(t,{s},{e})'[{nxt}]")
        cur = nxt
    fc.append(audio_filter)
    cmd += ["-filter_complex", ";".join(fc),
            "-map", f"[{cur}]", "-map", "[aout]",
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-t", "15", "-movflags", "+faststart", out_path]
    print("building", out_name)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit("ffmpeg failed for " + out_name)
    p = subprocess.run([FFMPEG, "-i", out_path], capture_output=True, text=True)
    for line in p.stderr.splitlines():
        if "Duration" in line or "Stream #" in line:
            print("  " + line.strip())
    for label, t in frames:
        fp = os.path.join(FRAME_DIR, out_name.split("_")[0] + "_" + label + ".png")
        subprocess.run([FFMPEG, "-y", "-ss", str(t), "-i", out_path,
                        "-frames:v", "1", fp], capture_output=True, text=True)
        print("  frame:", fp)


TITLE = lambda sz: _font(FONT_TITLE, sz)
BODY = lambda sz: _font(FONT_BODY, sz)

# ---- V4 Sound Quiz #2 (Blue Jay) ----
CRED_V4 = "Rec: Anonymous · CC0 · xeno-canto #924514"
v4_items = [
    (make_overlay("v4_hook", [("Real recording.\nWhat bird is this?", TITLE(74), DARK)], H * 0.55), 0.0, 2.2),
    (make_overlay("v4_guess", [("Guess…", BODY(60), SUB)], H * 0.55), 2.2, 5.0),
    (make_overlay("v4_here", [("Here it is —", BODY(58), SUB)], H * 0.55), 5.0, 7.0),
    (make_overlay("v4_name", [("Blue Jay", TITLE(78), DARK)], H * 0.55), 7.0, 12.0),
    (make_overlay("v4_cta", [("Comment your guess —\nI'll pin the answer.", BODY(54), DARK)], H * 0.55), 12.0, 15.0),
    (make_credit("v4_credit", CRED_V4), 2.2, 15.0),
]
build(
    "post4_sound_quiz_bluejay_1080x1920.mp4",
    BLUEJAY,
    "[1:a]atrim=0:7,asetpts=PTS-STARTPTS,volume=0.9,afade=t=out:st=6:d=1.0,"
    "apad=whole_dur=15,aformat=sample_rates=44100:channel_layouts=stereo[aout]",
    v4_items,
    [("frame_hook", 1.0), ("frame_name", 9.0), ("frame_cta", 13.0)],
)

# ---- V5 価値観ピース(受動的・無料) ----
CRED_V5 = ("Songs: xeno-canto — Cardinal / Chickadee / Blue Jay / "
           "Song Sparrow / Robin. Credits in caption.")
v5_items = [
    (make_overlay("v5_hook", [("Nothing here asks\nfor your time.", TITLE(72), DARK)], H * 0.55), 0.0, 3.4),
    (make_overlay("v5_mid", [("No streaks. No timers.\nJust birds, when they come.", BODY(54), DARK)], H * 0.55), 5.0, 9.0),
    (make_overlay("v5_free", [("The birdsong and the calm\nare always free.", TITLE(60), DARK)], H * 0.55), 11.0, 15.0),
    (make_credit("v5_credit", CRED_V5, size=27), 0.0, 15.0),
]
build(
    "post5_quiet_by_design_1080x1920.mp4",
    GARDEN,
    "[1:a]atrim=0:15,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1.5,"
    "afade=t=out:st=13.5:d=1.5,"
    "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
    v5_items,
    [("frame_hook", 1.5), ("frame_mid", 7.0), ("frame_free", 13.0)],
)

print("done.")
