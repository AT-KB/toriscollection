"""「鳥と寝る」「鳥と起きる」の15秒動画を組み立てて作る。

`build_concept15.py` と同じ作り方(庭の絵・字幕の帯・音)を使い回す。
CEO 2026-08-18「寝る起きるも作っていいよ」。

## 守っていること(concept15 と同じ)
 - 絵は `toris_app/assets/sprites/` の**アプリ本物**。描き起こさない。
 - **メッセージは2つまで、起きる出来事は1つ。**
 - **アプリがしないことは言わない。**

## それぞれ、何が本当か(実装を読んで確かめたこと)

**寝る** — `radio/sleep_mode.dart` と `radio_engine.dart:422`。
15/30/60/90分のタイマーがあり、時間が来るまで鳴り続ける。タイマー中は
`RadioNative.setBrightness(0.0)` で**画面を実際に暗くする**。
だから「画面が暗くなっても鳴り続ける」は本当。
⚠️ ただし**庭の絵が夜になるわけではない**。ここで夜にしているのは時間の
経過を表す絵であって、アプリの画面ではない。字幕でもそうは言わない。

**起きる** — `BirdAlarmService`。1羽で始まり、`RAMP_MS`(5分)の1/3で2羽目、
2/3で3羽目が加わる。音量は 8%→100%。並びは `BirdAlarmSounds.KEYS` で
Northern Cardinal → American Robin → Song Sparrow。
だから「1羽で始まって、他が加わる」は本当。
⚠️ 2026-08-19 に目覚ましの作りが変わった(1羽目は選ぶ／2羽目・3羽目は
**出会った鳥から**その朝ごとに選ぶ)。**決まった3種を名指ししない。**

実行:
    py -3 tools/video_build/build_sleep_wake15.py sleep
    py -3 tools/video_build/build_sleep_wake15.py wake
    py -3 tools/video_build/build_sleep_wake15.py both
"""
import math
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import (  # noqa: E402
    BRANCH_X, BRANCH_Y, FB, FPS, FT, GROUND, H, ROOT, SPRITES, W,
    credits_line, draw_band, draw_garden, ease, zoom_to,
)

DUR = 15.0
OUT_DIR = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材")

# 夜の色。真っ黒にはしない(止まって見える瞬間を作らない)。
NIGHT = (18, 30, 52)
DAWN = (58, 52, 74)

# ── 寝る ──────────────────────────────────────────────────
SLEEP_L1 = "Leave the radio playing."
SLEEP_L2 = "They keep singing in the dark."
SLEEP_BIRD = "carolina_wren"

# ラジオの画面と同じ出し方(点が灯り、名前が並ぶ)。
#
# ⚠️ **画面に出す名前と、実際に鳴っている録音を一致させる。**
# 最初は実機で見た顔ぶれ(Carolina Wren ほか)を書いたが、動画で鳴らす録音は
# 別の種だった。**聞こえていない鳥の名前が光る**のは、アプリ側で直したのと
# 同じ誤り(原則4)。鳴らす録音そのものから名前を引く。
#
# ⚠️ 種は**土地をそろえる**。配布可プールには Eurasian Jay や
# Common Kingfisher も居るが、Charlotte の裏庭で鳴かせたら生態の嘘になる。
SLEEP_SPECIES = ["Downy Woodpecker", "Pileated Woodpecker",
                 "Ruby-throated Hummingbird"]

# ── 起きる ────────────────────────────────────────────────
WAKE_L1 = "It starts with one bird."
WAKE_L2 = "Then the others join."
# ⚠️ **2026-08-19 に作り直した。**
# 目覚ましは「1羽目は選ぶ / 2羽目・3羽目は**出会った鳥から**その朝ごとに選ぶ」
# に変わったので、**決まった3種を名指ししてはいけない**(人によって違う)。
# 名前の行も「出会った鳥が加わる」という事実に変えた。
#
# 絵は `alarmBirds` に居て**ドット絵がある**種から選ぶ。
# Song Sparrow は絵が無く、選択肢にも入っていないので使わない。
# 音もこの3種を実際に鳴らす(目覚ましが鳴らすのと同じ録音)。
WAKE_CHORUS = [
    ("northern_cardinal", "Northern Cardinal", 4.2),
    ("american_robin", "American Robin", 7.6),
    ("eastern_bluebird", "Eastern Bluebird", 10.4),
]

# 最後に出す一行。**種を名指ししない。**
WAKE_TAIL = "The birds you have met join in."


def pick_radio(names):
    """配布可プールから、指定した種の録音だけを取る。"""
    import json
    rows = json.load(open(os.path.join(ROOT, "landing", "media", "radio_src",
                                       "all_credit.json"), encoding="utf-8"))
    files, recs = [], []
    for want in names:
        for r in rows:
            if (r.get("en") or "") == want and os.path.exists(r["file"]):
                files.append(r["file"])
                if r.get("rec") and r["rec"] not in recs:
                    recs.append(r["rec"])
                break
    if len(files) != len(names):
        raise SystemExit(f"配布可プールに揃っていない: {names}")
    return files, "Songs: xeno-canto — " + ", ".join(recs)


def pick_app_songs(bird_ids):
    """アプリ同梱の鳴き声から取る。**license_class が commercial のものだけ。**

    同梱音源には NC(非商用)が混ざっているので、1件ずつ確かめてから使う
    (36件中、商用可は6件しかない)。
    """
    import json
    creds = json.load(open(os.path.join(
        ROOT, "toris_app", "assets", "birds", "_credits.json"),
        encoding="utf-8"))
    by_id = {r["id"]: r for r in creds}
    files, recs = [], []
    for bid in bird_ids:
        r = by_id.get(bid)
        if not r or r.get("license_class") != "commercial":
            raise SystemExit(f"{bid} は商用に使えない({r and r.get('license_class')})")
        f = os.path.join(ROOT, "toris_app", "assets", "birds", f"{bid}.mp3")
        if not os.path.exists(f):
            raise SystemExit(f"{bid}.mp3 が無い")
        files.append(f)
        if r.get("recordist") and r["recordist"] not in recs:
            recs.append(r["recordist"])
    return files, "Songs: xeno-canto — " + ", ".join(recs)


def veil(im, color, alpha):
    if alpha <= 0:
        return
    im.alpha_composite(Image.new("RGBA", (W, H), color + (int(alpha),)))


def perch(im, bird_id, size, x, y, dark=0.0):
    """枝にとまる姿。[dark] が 1 に近いほど影になる(夜明け前)。"""
    sp = Image.open(os.path.join(SPRITES, f"{bird_id}.png")).convert("RGBA")
    sp = sp.resize((size, size), Image.NEAREST)
    if dark > 0:
        px = sp.load()
        for j in range(sp.size[1]):
            for i in range(sp.size[0]):
                r, g, b, a = px[i, j]
                if a:
                    px[i, j] = (int(r * (1 - dark) + 26 * dark),
                                int(g * (1 - dark) + 38 * dark),
                                int(b * (1 - dark) + 58 * dark), a)
    im.alpha_composite(sp, (x, y))


# 絵がまだ無い種の色。`data.py` の song_sparrow の color。
SPARROW_COLOR = (138, 106, 74)


def bird_mark(d, x, y, s, color):
    """絵がまだ無い種。**描き起こさず**、その種の色の鳥のかたちで代える。

    アプリの `ui/bird_mark.dart` と同じ考え方。宣伝のために別の絵を
    でっち上げると、アプリを開いた人が「居ない鳥」を探すことになる。
    影(真っ黒)にしたら、明るい夜明けの中で浮いて事故に見えた。
    """
    d.ellipse([x, y + s * 0.22, x + s * 0.85, y + s], fill=color)
    d.ellipse([x + s * 0.48, y, x + s * 0.95, y + s * 0.46], fill=color)
    d.polygon([(x + s * 0.92, y + s * 0.18), (x + s * 1.12, y + s * 0.26),
               (x + s * 0.92, y + s * 0.32)], fill=(90, 68, 46))


def voices_panel(im, d, t):
    """ラジオの「いま鳴いている」。点が灯って名前が並ぶ。"""
    if t <= 0:
        return
    x, y = int(W * 0.10), int(H * 0.50)
    f = ImageFont.truetype(FB, int(W * 0.036))
    for i, name in enumerate(SLEEP_SPECIES):
        k = ease(t * len(SLEEP_SPECIES) - i)
        if k <= 0:
            continue
        cy = y + i * int(H * 0.055)
        # 灯った点。ゆっくり息をする(速い点滅は急かす表示になる)。
        pulse = 0.72 + 0.28 * (0.5 + 0.5 * math.sin(t * 3.0 + i))
        r = int(11 * k)
        d.ellipse([x - r, cy - r, x + r, cy + r],
                  fill=(int(120 * pulse), int(196 * pulse), int(128 * pulse),
                        int(255 * k)))
        d.text((x + 34, cy - int(W * 0.022)), name, font=f,
               fill=(214, 232, 206, int(255 * k)))


def render_sleep(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)
    perch(im, SLEEP_BIRD, 200, BRANCH_X - 60, BRANCH_Y - 178)

    # **起きる出来事はこれ1つ** — 明かりが落ちていく。
    k = ease((t - 2.2) / 7.5)
    veil(im, NIGHT, 190 * k)
    d = ImageDraw.Draw(im)

    # 星。夜になってから、ぽつぽつと。
    if k > 0.45:
        s = ease((k - 0.45) / 0.4)
        for i, (sx, sy) in enumerate([(0.16, 0.09), (0.34, 0.05), (0.62, 0.11),
                                      (0.82, 0.07), (0.90, 0.17)]):
            a = int(200 * s * (0.6 + 0.4 * math.sin(t * 1.7 + i)))
            px, py = int(W * sx), int(H * sy)
            d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(255, 255, 255, a))

    voices_panel(im, d, (t - 8.2) / 2.0)
    head = SLEEP_L1 if t < 7.2 else SLEEP_L2
    ap = t / 0.6 if t < 7.2 else (t - 7.2) / 0.6
    draw_band(im, d, head, None, credit, ap)
    return im


def render_wake(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # **起きる出来事はこれ1つ** — 夜が明けて、鳴く鳥が増えていく。
    night = 1.0 - ease((t - 1.5) / 9.0)
    veil(im, NIGHT, 205 * night)
    veil(im, DAWN, 70 * (1 - abs(night - 0.5) * 2))
    d = ImageDraw.Draw(im)

    seats = [(BRANCH_X - 210, BRANCH_Y - 150),
             (BRANCH_X + 30, BRANCH_Y - 150),
             (BRANCH_X + 180, BRANCH_Y - 118)]
    for i, (bid, _name, at) in enumerate(WAKE_CHORUS):
        if t < at:
            continue
        k = ease((t - at) / 0.8)
        x, y = seats[i]
        y += int((1 - k) * -40)
        if bid is None:
            bird_mark(d, x, y, 132, SPARROW_COLOR)
        else:
            perch(im, bid, 170, x, y, dark=night * 0.85)
            d = ImageDraw.Draw(im)

    # 最後に、鳴く順のまま3種の名前(絵が無い種も文字なら出せる)。
    if t >= 11.6:
        k = ease((t - 11.6) / 0.8)
        f = ImageFont.truetype(FB, int(W * 0.029))
        line = WAKE_TAIL
        tw = d.textlength(line, font=f)
        ty = int(H * 0.455)
        # 下地を敷く。芝の緑に淡い字を置いたら読めなかった。
        plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle(
            [(W - tw) / 2 - 26, ty - 14, (W + tw) / 2 + 26, ty + 50], 22,
            fill=(247, 250, 242, int(232 * k)))
        im.alpha_composite(plate)
        ImageDraw.Draw(im).text(((W - tw) / 2, ty), line, font=f,
                                fill=(44, 68, 44))

    head = WAKE_L1 if t < 7.4 else WAKE_L2
    ap = t / 0.6 if t < 7.4 else (t - 7.4) / 0.6
    draw_band(im, d, head, None, credit, ap)
    return im


def sleep_audio():
    return pick_radio(SLEEP_SPECIES)


def wake_audio():
    # **目覚ましが実際に鳴らしている3種**。画面の並びと同じ順に重なる。
    return pick_app_songs([b for b, _n, _t in WAKE_CHORUS if b])


# ── 儀式 ──────────────────────────────────────────────────
# 型1 The Reveal。診断書がいちばん強いとしている型で、他の収集ゲームと
# 違う点(捕まえない)がそのまま絵になる唯一の題材。
#
# ⚠️ **作り話をしない。** アプリの儀式は本当にこう動く:
#   - 「Listen closely」を押すと、鳥が枝を移りながら近づいてくる
#   - 2.5秒ごとに1歩。前へ行くとは限らず、**下がることもある**
#   - 手前の枝に2歩とどまると「出会い」
# だから字幕も「行ったり来たりして、やがて留まる」と言う。
# 一直線に近づいてくる絵にすると、それは別のアプリの宣伝になる。
RITUAL_L1 = "Listen closely."
RITUAL_L2 = "It comes and goes. Then it stays."
RITUAL_BIRD = "carolina_wren"

# (時刻, 枝) 0=奥 1=中 2=手前。**下がる回**を入れてある。
RITUAL_PATH = [(1.4, 1), (3.0, 0), (4.4, 1), (5.8, 2), (7.2, 1), (8.6, 2)]
RITUAL_SETTLE = 9.6   # ここで手前に留まる = 出会い


def _branch_seat(depth):
    """枝の位置と大きさ。奥ほど小さく、高く、薄い。"""
    if depth == 0:
        return (BRANCH_X - 250, BRANCH_Y - 236, 110, 0.55)
    if depth == 1:
        return (BRANCH_X - 60, BRANCH_Y - 196, 150, 0.78)
    return (BRANCH_X + 70, BRANCH_Y - 246, 210, 1.0)


def render_ritual(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # いまどの枝に居るか。**跳ぶ瞬間だけ動かす**(間はじっとしている)。
    depth = 0
    for at, br in RITUAL_PATH:
        if t >= at:
            depth = br
    if t >= RITUAL_SETTLE:
        depth = 2
    x, y, size, alpha = _branch_seat(depth)

    # 跳んだ直後だけ、ぴょこっと弾む。
    hop = 0.0
    for at, _br in RITUAL_PATH + [(RITUAL_SETTLE, 2)]:
        if 0 <= t - at < 0.45:
            hop = math.sin((t - at) / 0.45 * math.pi) * 26
    sp = Image.open(os.path.join(SPRITES, f"{RITUAL_BIRD}.png")).convert("RGBA")
    sp = sp.resize((size, size), Image.NEAREST)
    if alpha < 1.0:
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * alpha)))
    im.alpha_composite(sp, (x, int(y - hop)))

    # 留まったら、図鑑の絵で「出会えた」ことを見せる(アプリと同じ順番 —
    # 手前に留まった瞬間に板が出る)。
    if t >= RITUAL_SETTLE + 1.2:
        im = zoom_to(im, BRANCH_X + 120, BRANCH_Y - 150,
                     1.0 + 0.5 * ease((t - RITUAL_SETTLE - 1.2) / 1.4))
        d = ImageDraw.Draw(im)

    head = RITUAL_L1 if t < 6.6 else RITUAL_L2
    ap = t / 0.6 if t < 6.6 else (t - 6.6) / 0.6
    draw_band(im, d, head, None, credit, ap)
    return im


def ritual_audio():
    # 近づいてくる鳥の声。**その鳥の録音**を鳴らす。
    return pick_radio(["Downy Woodpecker", "Pileated Woodpecker"])


# ── 集める(図鑑) ──────────────────────────────────────────
# 「?」が名前に変わっていくところを見せる。
#
# ⚠️ 言うことは実装どおり:
#   - 庭に来た鳥は図鑑に載る(名前まで)。近くで会うのは儀式を経てから。
#   - **記録は減らない。** 撹乱で庭が痩せても、図鑑も会った日数も減らない
#     (交渉不能の原則2)。生態ログには消す関数が無く、試験で固定してある。
# 「Nothing is ever taken away.」はここが根拠。煽りではなく仕様。
COLLECT_L1 = "Meet a bird. It joins your guide."
COLLECT_L2 = "Nothing is ever taken away."

# (種, 表示名, 現れる時刻)。ドット絵がある種から。
COLLECT_ROWS = [
    ("carolina_wren", "Carolina Wren", 1.2),
    ("northern_cardinal", "Northern Cardinal", 2.6),
    ("blue_jay", "Blue Jay", 4.0),
    ("american_goldfinch", "American Goldfinch", 5.4),
    ("downy_woodpecker", "Downy Woodpecker", 6.8),
    ("eastern_bluebird", "Eastern Bluebird", 8.2),
]


def render_collect(t, credit):
    im = Image.new("RGBA", (W, H), (247, 250, 242, 255))
    d = ImageDraw.Draw(im)

    # 図鑑の版面。上に見出し、下に行。
    fh = ImageFont.truetype(FT, int(W * 0.052))
    shown = sum(1 for _b, _n, at in COLLECT_ROWS if t >= at)
    d.text((int(W * 0.08), int(H * 0.085)), f"Guide  {shown}/37",
           font=fh, fill=(31, 59, 36))

    y = int(H * 0.17)
    fn = ImageFont.truetype(FB, int(W * 0.040))
    fq = ImageFont.truetype(FT, int(W * 0.046))
    for bid, name, at in COLLECT_ROWS:
        k = ease((t - at) / 0.55)
        if k <= 0:
            # まだ会っていない行。図鑑と同じ「?」。
            d.text((int(W * 0.09), y + 18), "?", font=fq, fill=(214, 92, 82))
            d.text((int(W * 0.20), y + 24), "???", font=fn,
                   fill=(150, 165, 145))
        else:
            sp = Image.open(os.path.join(SPRITES, f"{bid}.png")).convert("RGBA")
            s = int(84 * (0.7 + 0.3 * k))
            sp = sp.resize((s, s), Image.NEAREST)
            if k < 1.0:
                sp.putalpha(sp.getchannel("A").point(lambda v: int(v * k)))
            im.alpha_composite(sp, (int(W * 0.07), y + (84 - s) // 2))
            d.text((int(W * 0.20), y + 24), name, font=fn, fill=(31, 59, 36))
        y += int(H * 0.072)
        d.line([(int(W * 0.07), y - 12), (int(W * 0.93), y - 12)],
               fill=(226, 234, 220))

    head = COLLECT_L1 if t < 9.4 else COLLECT_L2
    ap = t / 0.6 if t < 9.4 else (t - 9.4) / 0.6
    draw_band(im, d, head, None, credit, ap)
    return im


def collect_audio():
    """音は**商用に使える録音だけ**。

    ⚠️ アプリ本体は「商用にしないから」で条件を緩めたが(CEO 2026-08-19)、
    **宣伝物はこちら側の判断で厳しいまま**にする。動画は配布物で、
    無料アプリの宣伝でも非商用条項の解釈を賭けたくない。
    ここで Carolina Wren を並べようとして pick_app_songs に止められた
    (歯止めが効いた例)。

    絵の方は種を選ばない — ドット絵は自前の素材なので条件が違う。
    行は図鑑の一覧であって「いま鳴いている鳥」ではないので、
    音と絵が別の種でも嘘にならない。
    """
    return pick_app_songs(
        ["northern_cardinal", "american_robin", "eastern_bluebird"])


FILMS = {
    "sleep": (render_sleep, "s09_sleep_15s_1080x1920.mp4", sleep_audio),
    "wake": (render_wake, "s10_wake_15s_1080x1920.mp4", wake_audio),
    "ritual": (render_ritual, "s11_ritual_15s_1080x1920.mp4", ritual_audio),
    "collect": (render_collect, "s12_collect_15s_1080x1920.mp4", collect_audio),
}


def build(kind):
    render, name, audio = FILMS[kind]
    used, credit = audio()
    out = os.path.join(OUT_DIR, name)
    tmp = os.path.join(os.path.dirname(__file__), f"_built_{kind}")
    os.makedirs(tmp, exist_ok=True)

    n = int(DUR * FPS)
    for f in range(n):
        im = render(f / FPS, credit)
        im.convert("RGB").save(os.path.join(tmp, f"f{f:04d}.png"))

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    silent = os.path.join(tmp, "silent.mp4")
    r = subprocess.run(
        [ff, "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "f%04d.png"),
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", silent],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit(f"{kind}: 連番の書き出しに失敗")

    # 音が増える時刻を、**画面で鳥が増える時刻に合わせる**。
    # ばらばらだと、鳴いていない鳥が光って見える。
    if kind == "wake":
        starts = [at for _b, _n, at in WAKE_CHORUS]
    else:
        starts = [8.2 + i * 0.7 for i in range(len(used))]
    ain, amix = [], []
    for i, aud in enumerate(used[:4]):
        ain += ["-i", aud]
        delay = int(starts[i] * 1000) if i < len(starts) else 0
        amix.append(f"[{i+1}:a]atrim=0:{DUR},adelay={delay}|{delay},"
                    f"volume=0.55[a{i}]")
    mix = "".join(x + ";" for x in amix)
    mix += "".join(f"[a{i}]" for i in range(len(amix)))
    mix += f"amix=inputs={len(amix)}:duration=first:dropout_transition=2,"
    mix += f"afade=t=in:st=0:d=0.8,afade=t=out:st={DUR-1.2}:d=1.2[aout]"
    r = subprocess.run(
        [ff, "-y", "-i", silent] + ain +
        ["-filter_complex", mix, "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-t", str(DUR),
         "-movflags", "+faststart", out],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-800:])
        raise SystemExit(f"{kind}: 音の合成に失敗")
    print(f"  {os.path.relpath(out, ROOT)}  "
          f"{os.path.getsize(out)//1024} KB  {DUR}秒  {W}x{H}")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    for k in (["sleep", "wake", "ritual", "collect"] if what == "both" else [what]):
        build(k)
