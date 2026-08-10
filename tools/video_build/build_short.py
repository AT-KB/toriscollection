"""型#1(図鑑リビール)の8秒ループ版 — TikTok立て直しの仕様。

なぜ作り直したか(`marketing/phase-1/SNS部/2026-08-08_TikTok立て直し_診断と仕様変更.md`):
  既存の15秒版は冒頭3.2秒がシルエットのまま動かず、TikTokが視聴を判断する時間帯に
  「止まって見える」。しかも最強アセットの詳細ドット絵を、誰も見ていない時間まで隠していた。

この版の決めごと:
  - 8.0秒・ループ(末尾が先頭に繋がる)。完全視聴率と2周目を取りにいく。
  - **詳細ドット絵は0秒から色つきで出す**。隠すのは「絵」ではなく「答え」。
  - 1本1羽。問いは「見ても分からないこと」= その鳥が実際に警戒する相手(GloBI実データ)。
  - CTAは入れない(低実績アカウントの外部誘導は配信が絞られるため)。
  - 常にゆっくり動かす(ズーム+上下)。静止して見える瞬間を作らない。

答えの中身は `toris_collection/bird_profile.py` と同じ実データから引く(作り話をしない=原則4)。
音は `landing/media/radio_src/`(CC0/BY/BY-SA の配布可プール)からのみ。

実行: py -3 tools/video_build/build_short.py           # 一覧
      py -3 tools/video_build/build_short.py cardinal  # 指定して書き出し
      py -3 tools/video_build/build_short.py all       # バッチ1を全部
"""
import json
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
RADIO = os.path.join(ROOT, "landing", "media", "radio_src")
sys.path.insert(0, os.path.join(ROOT, "toris_collection"))

W, H, FPS, DUR = 1080, 1920, 30, 8.0
N = int(FPS * DUR)
REVEAL = 4.2          # 答えが出る時刻
FT = "C:/Windows/Fonts/georgiab.ttf"
FB = "C:/Windows/Fonts/segoeui.ttf"
DARK = (35, 48, 33)
SUB = (74, 92, 66)
ACCENT = (150, 70, 60)

# バッチ1: 3本とも同じ型で、変えるのは鳥だけ(型と素材を切り分けるため)。
CAST = {
    "cardinal": {
        "bird_id": "northern_cardinal", "name": "Northern Cardinal",
        "audio": "Northern_Cardinal.mp3", "audio_at": 8,
        "out": "s01_cardinal_1080x1920.mp4",
    },
    "bluejay": {
        "bird_id": "blue_jay", "name": "Blue Jay",
        "audio": "Blue_Jay.mp3", "audio_at": 0,
        "out": "s02_bluejay_1080x1920.mp4",
    },
    "sparrow": {
        "bird_id": "suzume", "name": "Eurasian Tree Sparrow",
        "audio": "Eurasian_Tree_Sparrow.mp3", "audio_at": 0,
        "out": "s03_sparrow_1080x1920.mp4",
    },
}


def fears_of(bird_id):
    """図鑑と同じ実データ(GloBI由来)から「こわいもの」を英語で取る。"""
    import i18n
    import predators
    i18n.set_lang("en")
    labels = predators.labels(bird_id)
    if not labels:
        raise SystemExit(f"{bird_id}: 天敵データが無いので、この型では作れない")
    return labels, predators.is_genus_level(bird_id)


def credit_for(audio_file):
    """実際に使う録音の録音者とライセンスからクレジットを組む(手書きにしない)。"""
    try:
        with open(os.path.join(RADIO, "all_credit.json"), encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return "Song: xeno-canto"
    r = next((x for x in rows if os.path.basename(x.get("file", "")) == audio_file), None)
    if not r:
        return "Song: xeno-canto"
    lic = r.get("lic", "")
    if "publicdomain" in lic or "zero" in lic:
        tag = "CC0"
    else:
        bits = lic.rstrip("/").split("/licenses/")[-1].split("/")
        tag = "CC " + bits[0].upper() + (" " + bits[1] if len(bits) > 1 else "")
    return f"Song: xeno-canto — {r.get('rec')} ({tag})"


def bg():
    img = Image.new("RGB", (W, H))
    top, bot = (238, 242, 230), (222, 231, 209)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3)))
    return img


def detail(bird_id, target_h=980):
    """詳細ドット絵を読み、背景を抜いて指定の高さに揃える。

    24枚のうち11枚(日本の鳥はほぼ全部)は**不透明な白背景**で保存されており、
    α を削るだけでは白い箱が残る。かといって「白い画素を全部消す」と、スズメの腹や
    アオカケスの胸など**鳥自身の白**まで抜けてしまう。
    そこで四隅から塗りつぶし(flood fill)で外側だけを辿り、地続きの背景だけを抜く。
    """
    sp = Image.open(os.path.join(DB, bird_id + "_detail.png")).convert("RGBA")
    r, g, b, a = sp.split()

    if a.getextrema()[0] == 255:            # α が全面不透明 = 背景が塗り潰されている
        rgb = sp.convert("RGB")
        corner = rgb.getpixel((0, 0))
        if min(corner) > 235:               # 四隅が白っぽいときだけ処理する
            SENTINEL = (255, 0, 255)
            for xy in ((0, 0), (rgb.width - 1, 0),
                       (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1)):
                if min(rgb.getpixel(xy)) > 235:
                    ImageDraw.floodfill(rgb, xy, SENTINEL, thresh=40)
            mask = rgb.point(lambda v: 0)   # ダミー(サイズ合わせ)
            px = rgb.load()
            alpha = Image.new("L", rgb.size, 255)
            ap = alpha.load()
            for y in range(rgb.height):
                for x in range(rgb.width):
                    if px[x, y] == SENTINEL:
                        ap[x, y] = 0
            sp = Image.merge("RGBA", (r, g, b, alpha))
    else:
        a = a.point(lambda v: 0 if v < 130 else v)
        sp = Image.merge("RGBA", (r, g, b, a))

    sp = sp.crop(sp.getbbox())
    w, h = sp.size
    s = target_h / h
    return sp.resize((round(w * s), round(h * s)), Image.LANCZOS)


def fit_font(d, txt, path, start, max_w):
    """max_w に収まるまで字を小さくしたフォントを返す(はみ出し防止)。"""
    size = start
    while size > 28:
        f = ImageFont.truetype(path, size)
        if d.textlength(txt, font=f) <= max_w:
            return f
        size -= 3
    return ImageFont.truetype(path, 28)


def ctext(d, txt, font, cy, fill):
    w = d.textlength(txt, font=font)
    bb = d.textbbox((0, 0), txt, font=font)
    d.text(((W - w) / 2, cy - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=font, fill=fill)


def build(key):
    conf = CAST[key]
    labels, genus = fears_of(conf["bird_id"])
    answer = " · ".join(labels)
    cred = credit_for(conf["audio"])

    BG = bg()
    SP = detail(conf["bird_id"])
    NM = ImageFont.truetype(FT, 66)
    Q = ImageFont.truetype(FT, 76)
    A = ImageFont.truetype(FT, 68)
    SMALL = ImageFont.truetype(FB, 38)
    CF = ImageFont.truetype(FB, 26)

    fr = os.path.join(os.path.dirname(__file__), f"_short_{key}")
    os.makedirs(fr, exist_ok=True)

    for i in range(N):
        t = i / FPS
        frame = BG.copy().convert("RGBA")

        # 常にゆっくり動かす(止まって見える瞬間を作らない)
        zoom = 1.0 + 0.05 * (t / DUR)
        sw, sh = int(SP.width * zoom), int(SP.height * zoom)
        sp = SP.resize((sw, sh), Image.LANCZOS)
        y = int(H * 0.40 - sh / 2 + 8 * math.sin(t * 1.6))
        # 冒頭0.25秒だけ、わずかに立ち上げる(パッと出すぎない)
        if t < 0.25:
            f = t / 0.25
            tmp = Image.new("RGBA", sp.size, (0, 0, 0, 0))
            sp = Image.blend(tmp, sp, 0.35 + 0.65 * f)
        frame.alpha_composite(sp, (int((W - sw) / 2), y))

        d = ImageDraw.Draw(frame)
        ctext(d, conf["name"], NM, H * 0.115, DARK)

        if t < REVEAL:
            ctext(d, "What is this bird", Q, H * 0.79, DARK)
            ctext(d, "afraid of?", Q, H * 0.79 + 92, DARK)
        else:
            # 答えは0.35秒で立ち上げ、末尾0.5秒で引く(ループを繋ぐ)
            a = min(1.0, (t - REVEAL) / 0.35)
            if t > DUR - 0.5:
                a *= max(0.0, (DUR - t) / 0.5)
            col = tuple(int(238 + (ACCENT[k] - 238) * a) for k in range(3))
            sub = tuple(int(238 + (SUB[k] - 238) * a) for k in range(3))
            ctext(d, answer, fit_font(d, answer, FT, 68, W * 0.86), H * 0.79, col)
            if genus:
                ctext(d, "(from records of close relatives)", SMALL,
                      H * 0.79 + 78, sub)
            else:
                ctext(d, "real feeding records", SMALL, H * 0.79 + 78, sub)

        cw = d.textlength(cred, font=CF)
        d.text(((W - cw) / 2, H - 58), cred, font=CF, fill=(70, 86, 60))
        frame.convert("RGB").save(os.path.join(fr, f"f{i:04d}.png"))

    out_path = os.path.join(OUT, conf["out"])
    cmd = [FF, "-y", "-framerate", str(FPS), "-i", os.path.join(fr, "f%04d.png"),
           "-ss", str(conf["audio_at"]), "-t", str(DUR),
           "-i", os.path.join(RADIO, conf["audio"]),
           "-filter_complex",
           "[1:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.25,"
           f"afade=t=out:st={DUR-0.6}:d=0.6,apad=whole_dur={DUR},"
           "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
           "-map", "0:v", "-map", "[aout]",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-r", str(FPS), "-t", str(DUR), "-c:a", "aac", "-ar", "44100", "-ac", "2",
           "-movflags", "+faststart", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("ffmpeg failed")

    # フレーム監査用(エラー/豆腐/見切れを目視するため)
    cd = os.path.join(RAW, f"shortchk_{key}")
    os.makedirs(cd, exist_ok=True)
    for tt in ["0.2", "1.0", "2.5", "4.0", "4.5", "6.0", "7.8"]:
        subprocess.run([FF, "-y", "-ss", tt, "-i", out_path, "-frames:v", "1",
                        os.path.join(cd, f"t{tt}.png")], capture_output=True, text=True)
    print(f"done: {conf['out']}  answer='{answer}'  {cred}")
    return out_path


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "all":
        for k in CAST:
            build(k)
    elif arg in CAST:
        build(arg)
    else:
        print("使い方: py -3 tools/video_build/build_short.py <key|all>")
        for k, v in CAST.items():
            print(f"  {k:9s} {v['name']:26s} -> {v['out']}")
