"""LP のヒーロー動画と、SNS 用の「新しい画面」動画を作る。

## なぜ作り直したか(2026-08-17)
アプリを Streamlit から Flutter に移したのに、LP の動画だけ**旧アプリのまま**
だった(「Sim」タブ・古い2本木の画面)。LP でいちばん大きく再生されるものが
別アプリを映していた。スクショを直しても、ここが古ければ意味がない。

## 素材の出どころ(作り話をしない)
 - 映像: **実機の画面録画**(`adb shell screenrecord`)と実機のスクショ。
   合成イメージは作らない。映っているものは全部いまのアプリ。
   ⚠️ **素材は上端(ステータスバー+DEBUG の帯)を落としてから置くこと。**
   録画側はこの道具が落とすが、静止画は置く前に切っておく。
 - 音: `landing/media/radio_src/` の**配布可(CC0/BY/BY-SA)**の録音だけ。
   xeno-canto のクレジットを画面に出す(`all_credit.json` から自動で組む)。
   アプリ同梱の音源には NC(非商用)が混ざっているので**使わない**。

## 文言
LP 本文と揃える。**「会った鳥がラジオに加わる」とは書かない** — 実装は
土地で絞って会った回数を重みにするので、変わるのは近さと群れの厚み
(2026-08-17 に LP の同じ誤りを直した)。

実行:
    py -3 tools/video_build/build_showcase.py lp      # LP のヒーロー(横1080)
    py -3 tools/video_build/build_showcase.py sns     # SNS 用(縦1080x1920)
    py -3 tools/video_build/build_showcase.py tiktok  # TikTok 8秒
    py -3 tools/video_build/build_showcase.py both
"""
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLIPS = os.path.join(ROOT, "tools", "video_build", "_showcase_src")
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")
LP_OUT = os.path.join(ROOT, "landing", "media", "showcase.mp4")
SNS_OUT = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材",
                       "s04_new_app_1080x1920.mp4")
TIKTOK_OUT = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材",
                          "s05_concept_8s_1080x1920.mp4")

FPS = 30
# 録画の上端(ステータスバー+DEBUG の帯)。720x1600 の録画での高さ。
STATUS = 64
DARK = (35, 48, 33)
SUB = (74, 92, 66)
PAPER = (247, 250, 242)
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"

# 章。実機の素材(録画 or 静止画)と、そこに重ねる一言。
# **一言は LP 本文と同じ主張にする**(片方だけ直すと食い違う)。
CHAPTERS = [
    ("plant.png",  "Plant a little.",            2.6, True),
    ("garden.mp4", "Then close the app.",        3.4, False),
    ("arrive.png", "Someone arrives while you are away.", 3.0, True),
    ("guide.mp4",  "Meet it up close, and it is yours to keep.", 4.2, False),
    ("radio.mp4",  "The birds of your land sing. Real recordings.", 4.4, False),
]

# TikTok 用の 8秒版。診断書(2026-08-08)の型に合わせる:
#   8.0秒 / 主役は0.3秒から出す / 止まって見える瞬間を作らない / CTAは入れない。
# 17.6秒版は LP のヒーロー用(そちらは完走を前提にできる)。
TIKTOK = [
    ("garden.mp4", "A garden you plant.",        2.0, False),
    ("arrive.png", "Birds come while you're away.", 2.0, True),
    ("guide.mp4",  "Meet one, and it's yours.",  2.0, False),
    ("radio.mp4",  "Then they sing to you.",     2.0, False),
]


def credits_line():
    """使う音源の録音者を、クレジットファイルから組む(手書きにしない)。"""
    path = os.path.join(RADIO, "all_credit.json")
    rows = json.load(open(path, encoding="utf-8"))
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
        raise SystemExit("配布可の録音が1つも無い。landing/media/radio_src を確認すること")
    return used, "Songs: xeno-canto — " + ", ".join(names[:4])


def fit(draw, text, path, start, max_w):
    size = start
    while size > 14:
        f = ImageFont.truetype(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(path, 14)


def caption_png(text, w, h, credit, out):
    """字幕の帯。動画の上に重ねる(下寄せ)。"""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = int(w * 0.06)
    band_h = int(h * 0.16)
    d.rectangle([0, h - band_h, w, h], fill=(24, 34, 22, 216))
    f = fit(d, text, FT, int(w * 0.052), w - pad * 2)
    tw = d.textlength(text, font=f)
    d.text(((w - tw) / 2, h - band_h + int(band_h * 0.22)), text,
           font=f, fill=(240, 246, 232, 255))
    fc = ImageFont.truetype(FB, max(12, int(w * 0.018)))
    cw = d.textlength(credit, font=fc)
    d.text(((w - cw) / 2, h - int(band_h * 0.30)), credit,
           font=fc, fill=(176, 196, 168, 255))
    im.save(out)


def build(kind):
    used, credit = credits_line()
    chapters = CHAPTERS
    if kind == "lp":
        W, H, out = 720, 1600, LP_OUT
    elif kind == "tiktok":
        W, H, out = 1080, 1920, TIKTOK_OUT
        chapters = TIKTOK
    else:
        W, H, out = 1080, 1920, SNS_OUT

    tmp = os.path.join(CLIPS, "_work")
    os.makedirs(tmp, exist_ok=True)
    parts = []
    for i, (src, text, dur, is_still) in enumerate(chapters):
        p = os.path.join(CLIPS, src)
        if not os.path.exists(p):
            raise SystemExit(f"素材が無い: {p}\n"
                             "実機から撮り直すこと(README を参照)")
        cap = os.path.join(tmp, f"cap{i}.png")
        caption_png(text, W, H, credit, cap)
        seg = os.path.join(tmp, f"seg{i}.mp4")
        if is_still:
            # 静止画はゆっくり寄る(止まって見える瞬間を作らない)
            vf = (f"scale={W*2}:-2,zoompan=z='min(zoom+0.0009,1.12)':"
                  f"d={int(dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                  f"s={W}x{H}:fps={FPS}")
            cmd = [FF, "-y", "-loop", "1", "-i", p, "-i", cap,
                   "-filter_complex", f"[0:v]{vf}[v];[v][1:v]overlay=0:0",
                   "-t", str(dur), "-pix_fmt", "yuv420p", "-r", str(FPS), seg]
        else:
            # ⚠️ **DEBUG の帯とステータスバーを落とす。**
            # debug ビルドの印で、製品には出ない。宣伝物に映すと未完成に見える
            # (静止画では落としていたのに、録画では落としていなかった)。
            vf = (f"crop=iw:ih-{STATUS}:0:{STATUS},"
                  f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                  f"crop={W}:{H},fps={FPS}")
            cmd = [FF, "-y", "-t", str(dur), "-i", p, "-i", cap,
                   "-filter_complex", f"[0:v]{vf}[v];[v][1:v]overlay=0:0",
                   "-pix_fmt", "yuv420p", "-r", str(FPS), "-an", seg]
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if r.returncode:
            print(r.stderr[-900:])
            raise SystemExit(f"{src} の書き出しに失敗")
        parts.append(seg)

    total = sum(c[2] for c in chapters)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    # 音: 配布可の録音を順に薄く重ねる(1本ずつ、間を空けて)
    ain, amix = [], []
    for i, a in enumerate(used[:4]):
        ain += ["-i", a]
        delay = int(i * (total / max(1, min(4, len(used)))) * 1000)
        amix.append(f"[{i+1}:a]atrim=0:{total},adelay={delay}|{delay},"
                    f"volume=0.55[a{i}]")
    mix = "".join(a + ";" for a in amix)
    mix += "".join(f"[a{i}]" for i in range(len(amix)))
    mix += f"amix=inputs={len(amix)}:duration=first:dropout_transition=2,"
    mix += f"afade=t=in:st=0:d=0.6,afade=t=out:st={total-1.0}:d=1.0[aout]"

    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", lst] + ain + [
        "-filter_complex", mix, "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-t", str(total), "-movflags",
        "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-1200:])
        raise SystemExit("連結に失敗")
    print(f"  {os.path.relpath(out, ROOT)}  "
          f"{os.path.getsize(out)//1024} KB  {total:.1f}秒  {W}x{H}")
    print(f"  {credit}")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    for k in (["lp", "sns", "tiktok"] if what == "both" else [what]):
        build(k)
