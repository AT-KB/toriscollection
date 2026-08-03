"""Phase 1 第1週の短尺2本(V2 Sound Quiz / V3 Ambience)を書き出すビルドスクリプト.

方針(2026-08-02 改訂): 背景に既存の実写/UI録画(showcase.mp4)を使うと文字だらけの
アプリ画面が透けて雑然とするため、**splash と同じ世界観**——セージ地(#ecf1e3)+鳥の
ドット絵(splash_bird.png)+濃緑の字幕——のクリーンな縦動画にする。音(実録音)が主役の
Sound Quiz / Ambience にはこの静かな背景が最も合う(交渉不能の原則5=かわいさ/静けさ)。

- 1080x1920(9:16)/30fps/15s。字幕/クレジットは PIL で透過 PNG を描き、ffmpeg の
  overlay+enable で時間窓ごとに重ねる。**必ず安全マージン(左右96px)内に収め全文が切れない**。
- 出典クレジットは焼き込み必須(原則4)。文字列は実音源ファイル由来で改変しない。

実行: py -3 tools/video_build/build_week1_v2v3.py
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

W, H, FPS = 1080, 1920, 30
MARGIN = 96
USABLE = W - 2 * MARGIN                 # 888px: テキストはこの幅に必ず収める
DARK = (35, 48, 33, 255)                # 濃緑(splash のタイトル色に合わせる)
SUB = (74, 92, 66, 255)                 # やや薄い緑(サブ/クレジット)

FONT_TITLE = "C:/Windows/Fonts/georgiab.ttf"   # セリフ太字(タイトル/鳥名)
FONT_BODY = "C:/Windows/Fonts/segoeui.ttf"     # サンセリフ(サブ/CTA)

_BIRD_SRC = os.path.join(ROOT, "android_app", "android", "app", "src", "main",
                         "res", "drawable-xxxhdpi", "splash_bird.png")
BIRDCALL = os.path.join(ROOT, "landing", "media", "birdcall.mp3")
GARDEN = os.path.join(ROOT, "landing", "media", "garden_radio.mp3")
SAGE_RGB = (236, 241, 227)


def _make_bird_on_sage():
    """鳥をセージ地に合成した正方PNG。背景(同色セージPNG)と同じ色経路にすることで、
    lavfi色ソースとPNGのYUV変換差で出ていた鳥背後の薄い矩形(seam)を解消する。"""
    bird = Image.open(_BIRD_SRC).convert("RGBA")
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
    """blocks=[(text, font, fill)] を中央寄せで center_y を中心に積む(セージ地・スクリムなし)。"""
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
        # 可読性の微妙な持ち上げ(セージ地に淡い白の影)
        draw.text((cx + 1, cy - oy + 2), line, font=font, fill=(255, 255, 255, 90))
        draw.text((cx, cy - oy), line, font=font, fill=fill)
        cy += lh + gap


def make_overlay(name, blocks, center_y):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, blocks, center_y)
    path = os.path.join(TMP, name + ".png")
    img.save(path)
    return path


def make_credit(name, text, size=30):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(img, [(text, _font(FONT_BODY, size), SUB)], center_y=H - 150)
    path = os.path.join(TMP, name + ".png")
    img.save(path)
    return path


def build(out_name, audio_path, audio_filter, ov_list, frames):
    out_path = os.path.join(OUT_DIR, out_name)
    # 入力: [0]=セージ地(PNG), [1]=audio, [2]=鳥(セージ合成), [3..]=字幕/クレジット PNG
    cmd = [FFMPEG, "-y",
           "-loop", "1", "-t", "15", "-i", SAGE_BASE,
           "-i", audio_path,
           "-loop", "1", "-i", BIRD]
    for png, _, _ in ov_list:
        cmd += ["-loop", "1", "-i", png]

    fc = ["[0:v]fps=30,format=rgba[base]",
          "[2:v]scale=470:-1[bird]",
          # 鳥をゆっくり上下に揺らす(生きている感じ)
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

# ---- V2 Sound Quiz ----
CRED_V2 = "Rec: Katsuhiro Morishita · CC BY 4.0 · xeno-canto #782307"
v2_items = [
    (make_overlay("v2_hook", [("Real recording.\nWhat bird is this?", TITLE(74), DARK)], H * 0.55), 0.0, 2.2),
    (make_overlay("v2_guess", [("Guess…", BODY(60), SUB)], H * 0.55), 2.2, 5.0),
    (make_overlay("v2_here", [("Here it is —", BODY(58), SUB)], H * 0.55), 5.0, 7.0),
    (make_overlay("v2_name", [("Bull-headed Shrike", TITLE(76), DARK)], H * 0.55), 7.0, 12.0),
    (make_overlay("v2_cta", [("Comment your guess —\nI'll pin the answer.", BODY(54), DARK)], H * 0.55), 12.0, 15.0),
    (make_credit("v2_credit", CRED_V2, size=29), 2.2, 15.0),
]
build(
    "post2_sound_quiz_1080x1920.mp4",
    BIRDCALL,
    "[1:a]afade=t=out:st=6:d=1.5,apad=whole_dur=15,"
    "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
    v2_items,
    [("frame_hook", 1.0), ("frame_name", 9.0), ("frame_cta", 13.0)],
)

# ---- V3 Ambience ----
CRED_V3 = ("Songs: xeno-canto — Cardinal / Chickadee / Blue Jay / "
           "Song Sparrow / Robin. Credits in caption.")
v3_items = [
    (make_overlay("v3_hook", [("A radio made only of\nbirds you've met.", TITLE(70), DARK)], H * 0.55), 0.0, 3.4),
    (make_overlay("v3_end", [("Nothing to do here.\nThat's the point.", BODY(58), DARK)], H * 0.55), 11.0, 15.0),
    (make_credit("v3_credit", CRED_V3, size=27), 0.0, 15.0),
]
build(
    "post3_ambience_1080x1920.mp4",
    GARDEN,
    "[1:a]atrim=0:15,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1.5,"
    "afade=t=out:st=13.5:d=1.5,"
    "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
    v3_items,
    [("frame_hook", 1.5), ("frame_mid", 7.0), ("frame_end", 13.0)],
)

print("done.")
