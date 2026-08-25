"""鳴き声の当てっこ、15秒 × 3本(バッチ5)。**ループする作り。**

CEO 2026-08-25「鳴き声系のクイズとかでやっていこう」。
根拠は `marketing/phase-1/SNS部/2026-08-25_TikTokに注力する_事例と考察.md`。

## なぜこの型か

BirdTok で唯一、**強い事例がある形**(RSPB の bird call quiz が
数十万いいね・数千コメント)。しかも「声はすれど姿は見えず」の識別が
伸びている地域が **Eastern US** — うちの Charlotte の顔ぶれそのもの。
実録音・ドット絵・図鑑という一次資産が、**そのまま素材になる**。

## 事例から採った作りの決めごと(全部、理由がある)

**(1) ループさせる。** リウォッチは**1再生の2倍の重み**で効く上位シグナル。
20〜25秒未満がループの適地とされ、15秒はそこに入る。
使ったのは2つ:
  - **視覚の鏡** — 最後の絵を、最初の絵に戻す
  - **問いの呼び戻し** — 最後にもう一度、同じ声を鳴らす
    (答えを知った耳で聴き直したくなる = 自分から巻き戻す)

**(2) ⚠️「コメントして」と書かない。**
2026 は "comment below" 系の呼びかけが**エンゲージメント・ベイトとして
検出され、実際に順位が下がる**。TikTok が欲しいのは
「本当にその話題について話している人」。
→ **2択を出すだけにして、答えたくなる気持ちのほうに任せる。**
   最後の一言も、汎用の号令ではなく**その場の本当の問い**にする
   ("Which one is in your yard?")。

**(3) 冒頭0秒から音を鳴らす。** 無音で始めない。TikTok は音が主役の場で、
うちの商品も音。**最初の0.5秒で「鳴いている」ことが分かる**ようにする。

**(4) CTA は最後の札をやめ、帯の中の1行にする。**
15秒のうち2.8秒(19%)を札に使うと、**完走の直前に離脱の理由を置く**ことになる。
CEO 判断で CTA は入れる、は変えない。**置き方だけ変えた。**

## 守っていること
 - **鳴らすのは必ず「答え」の種の録音。** 外れの種の声は一度も鳴らさない。
 - 絵はアプリ本物のドット絵と詳細画。**絵の無い種は出さない。**
 - 音は配布可(CC0/BY/BY-SA)と、同梱のうち商用可のものだけ。
 - 一言の中身(Likes)は `data.py` から実行して取る。手で書かない。

実行:
    py -3 tools/video_build/build_quiz15.py           # 3本
    py -3 tools/video_build/build_quiz15.py q01       # 1本だけ
    py -3 tools/video_build/build_quiz15.py --remux   # 音だけ作り直す
"""
import array
import math
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import (  # noqa: E402
    FB, FPS, FT, H, PAPER, ROOT, W, draw_band, ease, fit,
)
from build_sleep_wake15 import pick_app_songs, pick_radio  # noqa: E402
import build_feature15 as F  # noqa: E402
from build_feature15 import INK, ON, SUB, card, emo, mix, sprite, text_a  # noqa: E402

DUR = 15.0
OUT_DIR = F.OUT_DIR

# 帯の中に常設する1行。**最後の札の代わり。**
BRAND = "TORIS COLLECTION   ·   Free on Google Play"

# 下に薄く敷く環境音。**アプリのラジオと同じ構成**(環境音 + 鳥)。
# 答え合わせの数秒がまるごと無音になるのを埋めるためでもある。
# `toris_app/assets/ambience/_credits.json` の全7層とも **CC0**(表示義務なし)。
# それでも出典は書く — アプリ内でもそうしている。
AMBIENCE = os.path.join(ROOT, "toris_app", "assets", "ambience", "wind.mp3")
AMB_VOL = 0.16

# ── 時間割 ────────────────────────────────────────────────
T_OPTIONS = 1.0      # 2択が出る
T_PAUSE = 6.6        # 声が止む(考える間)
T_REVEAL = 7.6       # 答え合わせ
T_FACT = 10.2        # 実データの一言
T_LOOP = 13.2        # 最初の絵に戻る + もう一度鳴る

# ── 3本 ──────────────────────────────────────────────────
# (答え, 外れ)。**答えの録音があること**と、両方に絵があることが条件。
QUIZ = {
    "q01": {"answer": ("pileated_woodpecker", "Pileated Woodpecker"),
            "decoy": ("downy_woodpecker", "Downy Woodpecker"),
            "pool": "radio",
            "out": "q01_call_woodpecker_15s_1080x1920.mp4"},
    "q02": {"answer": ("northern_cardinal", "Northern Cardinal"),
            "decoy": ("american_robin", "American Robin"),
            "pool": "app",
            "out": "q02_call_cardinal_15s_1080x1920.mp4"},
    "q03": {"answer": ("eastern_bluebird", "Eastern Bluebird"),
            "decoy": ("american_goldfinch", "American Goldfinch"),
            "pool": "app",
            "out": "q03_call_bluebird_15s_1080x1920.mp4"},
}

L1 = "Which one is singing?"
L2 = "Which one is in your yard?"

SKY_TOP = (247, 250, 242)
SKY_LOW = (231, 240, 226)


def _fact(bird_id):
    """その鳥の「好きなもの」を1つ。**data.py から実行して取る。**"""
    sys.path.insert(0, os.path.join(ROOT, "toris_collection"))
    import data  # noqa: E402
    import bird_profile as bp  # noqa: E402
    b = data.BIRDS[bird_id]
    prof = bp.build(bird_id, b, data.PLANTS, data.INSECTS, data.BIOMES)
    likes = prof["likes"]
    if not likes:
        return ("", "")
    e = likes[0]["entity"]
    icon = e.get("icon", "🐛") if likes[0]["kind"] == "plant" else "🐛"
    return (icon, e["english"])


def _envelope(path, onset, length, step=1.0 / FPS):
    """録音を実際に鳴らす区間の**音の大きさ**を、動画のコマ数ぶん返す。

    波形の絵をこれで動かす。**鳴っていない時に棒が踊るのを止める**ため。
    """
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run(
        [ff, "-v", "quiet", "-ss", f"{onset:.3f}", "-t", f"{length:.3f}",
         "-i", path, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"],
        capture_output=True)
    pcm = array.array("h")
    pcm.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    win = int(8000 * step)
    out = []
    for i in range(0, max(0, len(pcm) - win), win):
        acc = 0
        for v in pcm[i:i + win]:
            acc += v * v
        out.append(math.sqrt(acc / win))
    peak = max(out) if out else 1.0
    return [min(1.0, v / peak) if peak else 0.0 for v in out]


def _segment(path):
    """録音の**ひと節**を測る。返すのは (頭出し, ひと節の長さ)。

    ⚠️ ここは2回踏んだ:
      1. 頭出しを入れるまで、q02 は**冒頭2秒が無音**で書き出されていた
         (Cardinal の録音は頭に間がある)。TikTok で無音の2秒は致命傷。
      2. 頭出しだけ直したら、今度は**15秒のうち10秒が無音**になった。
         鳥の歌は数秒鳴いて長く休むので、録音をそのまま流すと間が空く。
    → **ひと節を測って、繰り返して鳴らす。** 鳥は実際にひと節を繰り返すので、
      これは作り話ではない。当てっこは何度か聴けたほうが成立もする。

    旧 `build_quiz.py` の手打ちの「音の頭出し」は 1. への対処だった。
    **手で入れず、測って出す。**
    """
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run(
        [ff, "-v", "quiet", "-i", path, "-f", "s16le", "-ac", "1",
         "-ar", "8000", "-"], capture_output=True)
    pcm = array.array("h")
    pcm.frombytes(r.stdout[:len(r.stdout) // 2 * 2])
    win = 400                      # 0.05 秒
    rms = []
    for i in range(0, max(0, len(pcm) - win), win):
        acc = 0
        for v in pcm[i:i + win]:
            acc += v * v
        rms.append(math.sqrt(acc / win))
    if not rms:
        return (0.0, 2.0)
    peak = max(rms)
    start = next((i for i, v in enumerate(rms) if v > peak * 0.35), 0)

    # ひと節の終わり = 0.6秒ぶん静かになったところ。長すぎるものは切る。
    quiet = 0
    end = len(rms)
    for i in range(start, len(rms)):
        quiet = quiet + 1 if rms[i] < peak * 0.12 else 0
        if quiet >= 12:
            end = i - 12
            break
    onset = max(0.0, start * 0.05 - 0.15)
    seg = min(3.2, max(1.2, (end - start) * 0.05 + 0.3))
    return (onset, seg)


def placements(seg, gap=0.45):
    """ひと節を、どの時刻に鳴らすか。問いの区間を埋め、ループ地点にも1回。"""
    out, t = [], 0.3
    while t + seg <= T_PAUSE:
        out.append(t)
        t += seg + gap
    if not out:
        out = [0.3]
    return out, [T_LOOP]


def envelope_track(src, onset, seg, at_play, at_loop):
    """15秒ぶんの「いま鳴っている大きさ」。鳴っていない所は 0。"""
    env = [0.0] * int(DUR * FPS)
    vals = _envelope(src, onset, seg)
    for start in list(at_play) + list(at_loop):
        base = int(round(start * FPS))
        for i, v in enumerate(vals):
            if 0 <= base + i < len(env):
                env[base + i] = v
    return env


def _bg(im):
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(
            int(SKY_TOP[0] + (SKY_LOW[0] - SKY_TOP[0]) * k),
            int(SKY_TOP[1] + (SKY_LOW[1] - SKY_TOP[1]) * k),
            int(SKY_TOP[2] + (SKY_LOW[2] - SKY_TOP[2]) * k)))


def _wave(im, t, cy, amp):
    """鳴っていることを絵にする。**棒の高さは実際の音の大きさ**([amp])。

    鳴っていない間(amp=0)は凪いで平らになる。前は時間だけで踊らせていて、
    録音が終わったあとも棒が動いていた = **鳴っていない音を絵にしていた。**
    """
    d = ImageDraw.Draw(im)
    n = 27
    span = int(W * 0.62)
    x0 = (W - span) // 2
    for i in range(n):
        ph = math.sin(t * 7.0 + i * 0.7) * math.sin(t * 2.3 + i * 0.31)
        h = int(14 + 84 * abs(ph) * amp) + 6
        x = x0 + int(i * span / (n - 1))
        d.rounded_rectangle([x - 6, cy - h // 2, x + 6, cy + h // 2], 6,
                            fill=(126, 176, 126) if amp > 0.08
                            else (206, 218, 202))


def _mark(im, t):
    """「?」。**最初の0.5秒で出て、脈を打つ**(静止画に見せない)。"""
    k = ease(t / 0.4)
    if k <= 0:
        return
    pulse = 1.0 + 0.04 * math.sin(t * 3.4)
    f = ImageFont.truetype(FT, int(W * 0.30 * pulse))
    d = ImageDraw.Draw(im)
    tw = d.textlength("?", font=f)
    text_a(im, ((W - tw) / 2, int(H * 0.128)), "?", f, (146, 180, 142), k)


def _option(im, t, i, bird_id, name, state):
    """2択の1つ。[state] は 'ask' / 'win' / 'lose'。"""
    x = int(W * (0.09 if i == 0 else 0.53))
    y = int(H * 0.300)
    w = int(W * 0.38)
    k = ease((t - T_OPTIONS - i * 0.25) / 0.5)
    if k <= 0:
        return
    dim = 0.32 if state == "lose" else 1.0
    fill = mix((255, 255, 255), ON, 0.16) if state == "win" else (255, 255, 255)
    card(im, [x, y, x + w, y + int(H * 0.200)], 34, fill, int(238 * k * dim))
    if state == "win":
        ImageDraw.Draw(im).rounded_rectangle(
            [x, y, x + w, y + int(H * 0.200)], 34, outline=ON + (255,), width=7)

    sprite(im, bird_id, 156, x + (w - 156) // 2, y + int(H * 0.018), k * dim)
    f = ImageFont.truetype(FB, int(W * 0.028))
    d = ImageDraw.Draw(im)
    for j, part in enumerate(name.split(" ", 1)):
        tw = d.textlength(part, font=f)
        text_a(im, (x + (w - tw) / 2, y + int(H * 0.128) + j * 38), part, f,
               INK, k * dim)

    # A / B の札。
    lab = "A" if i == 0 else "B"
    fl = ImageFont.truetype(FT, int(W * 0.040))
    card(im, [x + 18, y + 18, x + 90, y + 90], 24,
         ON if state == "win" else (236, 242, 230), int(240 * k * dim))
    tw = d.textlength(lab, font=fl)
    text_a(im, (x + 54 - tw / 2, y + 32), lab, fl,
           PAPER if state == "win" else SUB, k * dim)


def render(t, credit, q, fact, env):
    a_id, a_name = q["answer"]
    d_id, d_name = q["decoy"]
    # 答えが A か B かは本ごとに変える(いつも同じ側だと当てっこにならない)。
    a_slot = q["a_slot"]

    im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    _bg(im)

    # **最後は最初の絵に戻す**(視覚の鏡 → 自分から巻き戻す)。
    looping = t >= T_LOOP
    revealed = T_REVEAL <= t < T_LOOP

    _mark(im, t if not looping else t - T_LOOP + 0.4)
    fi = int(round(t * FPS))
    _wave(im, t, int(H * 0.285), env[fi] if 0 <= fi < len(env) else 0.0)

    for i in range(2):
        is_answer = (i == a_slot)
        bid, nm = (a_id, a_name) if is_answer else (d_id, d_name)
        if revealed:
            state = "win" if is_answer else "lose"
        else:
            state = "ask"
        _option(im, t if not looping else T_OPTIONS + 0.9,
                i, bid, nm, state)

    # 答え合わせ — 詳細画に育つ。図鑑の「会うと絵が育つ」と同じ演出。
    if revealed:
        k = ease((t - T_REVEAL - 0.3) / 0.9)
        # ⚠️ k がごく小さいフレームで side が 0 になり、resize が落ちた
        # (数フレームだけの確認では踏まなかった)。**2px 未満は描かない。**
        if int(W * 0.42 * k) >= 2:
            side = int(W * 0.42 * k)
            sp = Image.open(os.path.join(
                F.SPRITES, f"{a_id}_detail.png")).convert("RGBA")
            sp = sp.resize((side, int(side * sp.size[1] / sp.size[0])),
                           Image.LANCZOS)
            if k < 1.0:
                sp.putalpha(sp.getchannel("A").point(lambda v: int(v * k)))
            im.alpha_composite(sp, ((W - sp.size[0]) // 2,
                                    int(H * 0.640) - sp.size[1] // 2))

    # 答えの名前と、実データの一言。**帯の副題に入れる。**
    # 浮かせた札にすると詳細画と場所を取り合って、どちらも読めなくなった。
    sub = None
    if T_FACT <= t < T_LOOP:
        sub = a_name + (f"  —  likes {fact[1]}" if fact[1] else "")

    # **ループ地点では見出しも最初に戻す**(視覚の鏡を完成させる)。
    if looping or t < T_REVEAL:
        head, ap = L1, (t / 0.6 if t < T_REVEAL else (t - T_LOOP) / 0.5)
    else:
        head, ap = L2, (t - T_REVEAL) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, sub, credit, ap, brand=BRAND)
    return im


def audio_for(q):
    a_id, a_name = q["answer"]
    if q["pool"] == "radio":
        return pick_radio([a_name])
    return pick_app_songs([a_id])


def build(key, remux=False):
    q = dict(QUIZ[key])
    # 答えの位置は本ごとに入れ替える(q01=A / q02=B / q03=A)。
    q["a_slot"] = {"q01": 0, "q02": 1, "q03": 0}[key]
    used, credit = audio_for(q)
    credit += "   ·   Ambience: Freesound (CC0)"
    fact = _fact(q["answer"][0])
    out = os.path.join(OUT_DIR, q["out"])
    tmp = os.path.join(os.path.dirname(__file__), f"_quiz15_{key}")
    os.makedirs(tmp, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    silent = os.path.join(tmp, "silent.mp4")

    src = used[0]
    onset, seg = _segment(src)
    at_play, at_loop = placements(seg)
    env = envelope_track(src, onset, seg, at_play, at_loop)
    print(f"  頭出し {onset:.2f}s / ひと節 {seg:.2f}s / 鳴らす時刻 "
          + ", ".join(f"{x:.1f}" for x in at_play + at_loop))

    if not (remux and os.path.exists(silent)):
        for f in range(int(DUR * FPS)):
            im = render(f / FPS, credit, q, fact, env)
            im.convert("RGB").save(os.path.join(tmp, f"f{f:04d}.png"))
        r = subprocess.run(
            [ff, "-y", "-framerate", str(FPS),
             "-i", os.path.join(tmp, "f%04d.png"),
             "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", silent],
            capture_output=True, text=True, errors="replace")
        if r.returncode:
            print(r.stderr[-800:])
            raise SystemExit(f"{key}: 連番の書き出しに失敗")

    # 音は**同じ録音を2回**。1回目が問い、2回目(ループ地点)が呼び戻し。
    # ⚠️ `duration=first` だと1本目が終わった時点で切れて、
    # ループ地点の2回目が消える。**longest** にする。
    # `normalize=0` を付けないと amix が入力数で割って半分の音量になる。
    # **ひと節を、測った時刻に置いていく。** 0 から取ると録音の頭の間が
    # そのまま無音になり、1回しか鳴らさないと15秒のうち10秒が無音になる。
    times = at_play + at_loop
    parts, tags, ain = [], [], []
    for i, at in enumerate(times):
        ain += ["-i", src]
        parts.append(f"[{i+1}:a]atrim=start={onset:.3f}:end={onset+seg:.3f},"
                     f"asetpts=PTS-STARTPTS,"
                     f"adelay={int(at*1000)}|{int(at*1000)}[s{i}]")
        tags.append(f"[s{i}]")
    n = len(times)
    ain += ["-i", AMBIENCE]
    parts.append(f"[{n+1}:a]atrim=0:{DUR},asetpts=PTS-STARTPTS,"
                 f"volume={AMB_VOL}[amb]")
    tags.append("[amb]")
    core = (";".join(parts) + ";" + "".join(tags)
            + f"amix=inputs={n + 1}:duration=longest:normalize=0,")

    measured = F._measure(ff, silent, ain, core)
    mix_f = core + F._loudnorm(measured) + ","
    mix_f += f"afade=t=in:st=0:d=0.25,afade=t=out:st={DUR-0.4}:d=0.4[aout]"
    r = subprocess.run(
        [ff, "-y", "-i", silent] + ain +
        ["-filter_complex", mix_f, "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", str(DUR),
         "-movflags", "+faststart", out],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit(f"{key}: 音の合成に失敗")
    print(f"  {os.path.relpath(out, ROOT)}  "
          f"{os.path.getsize(out)//1024} KB  {DUR}秒  {W}x{H}")
    print(f"  答え = {q['answer'][1]} / 外れ = {q['decoy'][1]}")
    print(f"  {credit}")


if __name__ == "__main__":
    args = sys.argv[1:]
    remux = "--remux" in args
    want = [a for a in args if not a.startswith("-")] or list(QUIZ)
    for k in want:
        if k not in QUIZ:
            raise SystemExit(f"知らない題目: {k} / 使えるのは {list(QUIZ)}")
        print(f"[{k}]")
        build(k, remux=remux)
