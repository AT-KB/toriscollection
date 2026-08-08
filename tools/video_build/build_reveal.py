"""旗艦(図鑑リビール型): 最強アセット=詳細ドット絵を主役に。
「♪ 本物の録音 — 誰が鳴いてる? 」謎のシルエット → 開いて色づき精密な鳥が現れる(本物の声)。
oddly-satisfying なリビール+ASMR。全フレーム PIL 描画 → ffmpeg。

種を差し替えて増産できるよう VARIANTS で構成を持つ。**音は
`landing/media/radio_src/`(CC0 / CC BY / CC BY-SA だけを選んだ配布可プール)からのみ**取る。
アプリ内キャッシュ(.xeno_canto_cache)は NC/ND が大半で動画には使えない。
プールを増やすには `py -3 tools/xc_marketing_pull.py --download`。

実行: py -3 tools/video_build/build_reveal.py            # 一覧
      py -3 tools/video_build/build_reveal.py post14     # 指定して書き出し
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


# ── 動画の構成(種を差し替えて増産する) ─────────────────────────
# 1本 = 鳥2種のリビール + 締め。各鳥は (鳥ID, 表示名, 実際の食べもの, 音源, 音の開始秒)。
# 「好きなもの」は図鑑と同じく**実際の餌**を書く(作り話をしない=原則4)。
VARIANTS = {
    # 既存の投稿済み。再現用に残す(通常は再ビルドしない)。
    "post11": {
        "out": "post11_reveal_1080x1920.mp4",
        "birds": [
            ("northern_cardinal", "Northern Cardinal",
             "likes sunflower seeds", "Northern_Cardinal.mp3", 8),
            ("blue_jay", "Blue Jay",
             "likes acorns & insects", "Blue_Jay.mp3", 0),
        ],
    },
    # 追加分: シャーロットの庭でよく会う2種。
    "post14": {
        "out": "post14_reveal_robin_bluebird_1080x1920.mp4",
        "birds": [
            ("american_robin", "American Robin",
             "likes berries & earthworms", "American_Robin.mp3", 2),
            ("eastern_bluebird", "Eastern Bluebird",
             "likes caterpillars & berries", "Eastern_Bluebird.mp3", 0),
        ],
    },
    # 追加分: 京都の庭。日本の鳥での初のリビール(音源プール拡張で可能になった)。
    "post15": {
        "out": "post15_reveal_kyoto_1080x1920.mp4",
        "birds": [
            ("suzume", "Eurasian Tree Sparrow",
             "likes rice & caterpillars", "Eurasian_Tree_Sparrow.mp3", 0),
            ("kawasemi", "Common Kingfisher",
             "likes dragonflies & frogs", "Common_Kingfisher.mp3", 0),
        ],
    },
}

VARIANT = sys.argv[1] if len(sys.argv) > 1 else ""
if VARIANT not in VARIANTS:
    print("使い方: py -3 tools/video_build/build_reveal.py <variant>")
    for k, v in VARIANTS.items():
        print(f"  {k:8s} {' + '.join(b[1] for b in v['birds']):48s} -> {v['out']}")
    sys.exit(0)
CONF = VARIANTS[VARIANT]

BG = _card_bg()
CARD = {b[0]: _detail(b[0]) for b in CONF["birds"]}
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
# 1羽目 0.0-6.8(3.2で色づく) / 2羽目 6.8-12.6(9.6で色づく) / 12.6- 締め。
SPAN = [(0.0, 3.2, 6.8), (6.8, 9.6, 12.6)]
SCHED = [
    (b[0], b[1], b[2], *SPAN[i]) for i, b in enumerate(CONF["birds"])
]
OUTRO_AT = SPAN[-1][2]
BIRD_CY = H * 0.40


def _credit_line():
    """使った録音の実際の録音者とライセンスからクレジット文を組む。
    (手書きにすると差し替え時に嘘になるので、必ず credit json から作る)"""
    path = os.path.join(RADIO, "all_credit.json")
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except Exception:
        return "Songs: xeno-canto"
    by_file = {os.path.basename(r.get("file", "")): r for r in rows}
    parts = []
    for b in CONF["birds"]:
        r = by_file.get(b[3])
        if not r:
            continue
        lic = r.get("lic", "")
        if "publicdomain" in lic or "zero" in lic:
            tag = "CC0"
        else:
            # .../licenses/by-sa/4.0/ -> CC BY-SA 4.0
            bits = lic.rstrip("/").split("/licenses/")[-1].split("/")
            tag = "CC " + bits[0].upper() + (" " + bits[1] if len(bits) > 1 else "")
        parts.append(f"{r.get('rec')} ({tag})")
    return "Songs: xeno-canto — " + " · ".join(parts) if parts else "Songs: xeno-canto"


CREDIT = _credit_line()


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
    if t >= OUTRO_AT:
        frame = BG.copy()
        d = ImageDraw.Draw(frame)
        _ctext(d, [("Collect real birds", TT, DARK),
                   ("by their songs", TT, DARK),
                   ("", BD, SUB),
                   ("real recordings · free on Android", BD, SUB),
                   ("link in bio", BD, (90, 130, 70))], H * 0.5)
    cw = d.textlength(CREDIT, font=CF)
    d.text(((W - cw) / 2, H - 60), CREDIT, font=CF, fill=(70, 86, 60))
    frame.save(os.path.join(FR, f"f{i:04d}.png"))


print(f"rendering {N} frames...")
for i in range(N):
    render(i)
    if i % 90 == 0:
        print("  ", i)

out_path = os.path.join(OUT, CONF["out"])
# 1羽目は 1羽目の持ち時間ぶん、2羽目は「2羽目の持ち時間 - 1秒」だけ鳴らす
# (締めに入る手前で自然に引く)。音源は radio_src からのみ。
seg = [SPAN[0][2] - SPAN[0][0], SPAN[1][2] - SPAN[1][0] - 1.0]
cmd = [FF, "-y", "-framerate", str(FPS), "-i", os.path.join(FR, "f%04d.png")]
for i, b in enumerate(CONF["birds"]):
    cmd += ["-ss", str(b[4]), "-t", f"{seg[i]:.1f}",
            "-i", os.path.join(RADIO, b[3])]
cmd += ["-filter_complex",
        "[1:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.3[c];"
        "[2:a]loudnorm=I=-16:TP=-1.5,afade=t=in:st=0:d=0.3[j];"
        "[c][j]concat=n=2:v=0:a=1,afade=t=out:st=13.5:d=1.5,apad=whole_dur=15,"
        "aformat=sample_rates=44100:channel_layouts=stereo[aout]",
        "-map", "0:v", "-map", "[aout]"]
cmd += [
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
cd = os.path.join(RAW, f"revchk_{VARIANT}")
os.makedirs(cd, exist_ok=True)
for t in [1, 2, 3, 4, 5, 7, 8, 10, 11, 13, 14]:
    subprocess.run([FF, "-y", "-ss", str(t), "-i", out_path, "-frames:v", "1",
                    os.path.join(cd, f"t{t}.png")], capture_output=True, text=True)
print("done:", out_path)
