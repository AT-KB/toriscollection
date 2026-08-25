"""機能を1つずつ宣伝して DL につなげる15秒動画(バッチ3)。

CEO 2026-08-24「Tiktokで機能を宣伝しDLにつなげるように。15秒程度。
目覚まし・寝落ち・鳥が起こしてくれる…いっぱいあるから1つずつ作成して」。

## 既存の `s09`〜`s13`(build_sleep_wake15.py)との違い

あちらは**気分**を見せる。こちらは**機能**を見せて、最後に置き場所を言う:

 - 画面の文言は**アプリの実物の文字列**を使う("Wake with the birds" /
   "First to sing" / "Garden radio" / "Listen closely" / "You met a bird")。
   宣伝用に言い換えると、入れた人が同じ言葉を探して見つけられない。
 - 最後の2.8秒に**アイコン + Free on Google Play** の札を出す。

⚠️ **CTA は SNS部の作法(2026-08-08 診断書)では「入れない」ことになっている。**
低実績アカウントで "link in bio" を出すと配信が絞られる、が理由。
CEO の指示で今回は入れる。`CTA = False` にすれば同じ動画を CTA 無しでも
書き出せるので、比較したくなったら両方出せる。

## 守っていること(concept15 / sleep_wake15 と同じ)
 - 絵は `toris_app/assets/sprites/` の**アプリ本物**。描き起こさない。
 - **アプリがしないことは言わない。** 数字(5分・15/30/60/90分・37種)は
   実装から取った。根拠は各節のコメントに書いてある。
 - 音は**配布可(CC0/BY/BY-SA)の録音だけ**。同梱音源は license_class が
   commercial のものだけを使う(`pick_app_songs` が弾く)。
 - 画面に**名前を出した鳥は、実際にその録音を鳴らす**。
   例外は図鑑・ネットワークの一覧で、あれは「いま鳴いている鳥」ではない。

実行:
    py -3 tools/video_build/build_feature15.py            # 7本ぜんぶ
    py -3 tools/video_build/build_feature15.py alarm      # 1本だけ
"""
import json
import math
import os
import re
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import (  # noqa: E402
    BRANCH_X, BRANCH_Y, FB, FPS, FT, GROUND, H, PAPER, ROOT, SPRITES, W,
    draw_band, draw_garden, ease, fit,
)
from build_sleep_wake15 import (  # noqa: E402
    DAWN, NIGHT, pick_app_songs, pick_radio, veil,
)

DUR = 15.0
OUT_DIR = os.path.join(ROOT, "marketing", "phase-1", "SNS部", "素材")

# 字幕の帯。`draw_band` と同じ寸法(CTA の札はこの中に置く)。
BANDH = int(H * 0.245)
BTOP = H - BANDH

# 絵文字。**アプリが絵文字で出しているものだけ**をここでも絵文字で出す
# (🐿️🦅 = tree_scene.dart / 🌧🍃💧 = kAmbienceLabel / ❓🐦🪶 = guide_page.dart)。
# 2026-08-20 に「Windows のフォントで豆腐になる」と書き残されていたが、
# Segoe UI Emoji を `embedded_color=True` で焼けばカラーのまま出る(確認済み)。
FE = "C:/Windows/Fonts/seguiemj.ttf"

ICON = os.path.join(OUT_DIR, "store", "app_icon_512.png")

# ── DL の札 ────────────────────────────────────────────────
CTA = True
CTA_AT = 12.2
CTA_NAME = "TORIS COLLECTION"
CTA_SUB = "Free on Google Play"

INK = (31, 59, 36)
SUB = (108, 134, 106)


def card(im, box, radius, fill, a=255):
    """角丸の札。透かして重ねられるように、いったん別の面に描く。"""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle(box, radius,
                                         fill=tuple(fill) + (int(a),))
    im.alpha_composite(ov)


ON = (96, 150, 96)      # 押されている状態の色(アプリの FilledButton と同じ緑)


def mix(a, b, k):
    """色を混ぜる。**灰色を経由しない**(各成分を個別に寄せると濁る)。"""
    k = max(0.0, min(1.0, k))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def emo(im, xy, ch, size):
    """絵文字。色つきのまま焼く。"""
    ImageDraw.Draw(im).text(xy, ch, font=ImageFont.truetype(FE, max(8, size)),
                            embedded_color=True)


def text_a(im, xy, s, font, color, a):
    """透明度つきの文字。"""
    if a <= 0:
        return
    ImageDraw.Draw(im).text(xy, s, font=font,
                            fill=tuple(color) + (int(255 * min(1.0, a)),))


def dot(d, x, y, r, color, a=1.0):
    d.ellipse([x - r, y - r, x + r, y + r],
              fill=tuple(color) + (int(255 * min(1.0, a)),))


def sprite(im, bird_id, size, x, y, a=1.0, detail=False):
    """アプリのドット絵(または図鑑の詳細画)をそのまま置く。"""
    if size < 2 or a <= 0:
        return
    name = f"{bird_id}_detail.png" if detail else f"{bird_id}.png"
    sp = Image.open(os.path.join(SPRITES, name)).convert("RGBA")
    if detail:
        sp = sp.resize((size, int(size * sp.size[1] / sp.size[0])),
                       Image.LANCZOS)
    else:
        sp = sp.resize((size, size), Image.NEAREST)
    if a < 1.0:
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    im.alpha_composite(sp, (int(x), int(y)))


def draw_cta(im, t):
    """最後に出す札。**クレジットの行は隠さない**(BY-SA は表示が条件)。"""
    if not CTA or t < CTA_AT:
        return
    k = ease((t - CTA_AT) / 0.35)
    top = BTOP + int(BANDH * 0.06)
    bot = H - int(BANDH * 0.24)          # ここから下はクレジットの行
    m = int(W * 0.05)
    card(im, [m, top, W - m, bot], 34, PAPER, 255 * k)

    s = int((bot - top) * 0.68)
    ic = Image.open(ICON).convert("RGBA").resize((s, s), Image.LANCZOS)
    # アイコンは**丸**(2026-08-21 に丸で統一した本物と同じかたち)。
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, s - 1, s - 1], fill=int(255 * k))
    ic.putalpha(mask)
    iy = top + ((bot - top) - s) // 2
    im.alpha_composite(ic, (m + int(W * 0.035), iy))

    x = m + int(W * 0.035) + s + int(W * 0.045)
    d = ImageDraw.Draw(im)
    fn = fit(d, CTA_NAME, FT, int(W * 0.055), W - m - x - 30)
    text_a(im, (x, iy + int(s * 0.14)), CTA_NAME, fn, INK, k)
    text_a(im, (x, iy + int(s * 0.54)), CTA_SUB,
           ImageFont.truetype(FB, int(W * 0.034)), SUB, k)


# ══════════════════════════════════════════════════════════
# ① 目覚まし — 鳥が起こしてくれる
# ══════════════════════════════════════════════════════════
# 何が本当か(`alarm/alarm.dart` と `BirdAlarmService.java` を読んで確かめた):
#  - 画面の題は "Wake with the birds"、鳥を選ぶ欄は "First to sing"。
#  - 1羽目は**自分で選ぶ**。選べるのは会えた鳥＋最初から居る3種
#    (Blue Jay / Northern Cardinal / American Goldfinch = kStarterAlarmBirds)。
#  - 鳴り出しは音量8%(START_VOL)。RAMP_MS = **5分**かけて最大へ。
#    その 1/3 で2羽目、2/3 で3羽目が加わる(JOIN2_MS / JOIN3_MS)。
#  - 2羽目・3羽目は**出会った鳥から**その朝ごとに選ばれる。
#    だから決まった3種を「目覚ましの顔ぶれ」として名指ししない。
#  - 音は APK 同梱なので**通信が無くても鳴る**。
ALARM_L1 = "Wake with the birds."
ALARM_L2 = "One starts. The others join in."
ALARM_TIME = "6:30"
ALARM_PICK = [("american_goldfinch", "American Goldfinch"),
              ("blue_jay", "Blue Jay"),
              ("northern_cardinal", "Northern Cardinal")]
ALARM_CHOSEN = 2
# (種, 加わる時刻)。**音もこの時刻に重ねる**(STARTS が読む)。
ALARM_JOIN = [("northern_cardinal", 5.0),
              ("american_robin", 8.0),
              ("eastern_bluebird", 10.6)]
ALARM_CARD_OUT = 3.6


def render_alarm(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # 夜 → 夜明け。**起きる出来事はこれ1つ**(明るくなって鳴く鳥が増える)。
    night = 1.0 - ease((t - ALARM_CARD_OUT) / 8.4)
    veil(im, NIGHT, 205 * night)
    veil(im, DAWN, 66 * (1 - abs(night - 0.5) * 2))

    seats = [(BRANCH_X - 215, BRANCH_Y - 152),
             (BRANCH_X + 40, BRANCH_Y - 150),
             (BRANCH_X + 195, BRANCH_Y - 118)]
    for i, (bid, at) in enumerate(ALARM_JOIN):
        if t < at:
            continue
        k = ease((t - at) / 0.8)
        x, y = seats[i]
        sprite(im, bid, 170, x, y + int((1 - k) * -40))

    # 目覚ましの設定画面。**実物の文字列**をそのまま出す。
    ck = 1.0 - ease((t - ALARM_CARD_OUT) / 0.8)
    if ck > 0:
        x0, y0 = int(W * 0.07), int(H * 0.09)
        x1, y1 = int(W * 0.93), int(H * 0.56)
        card(im, [x0, y0, x1, y1], 40, PAPER, 250 * ck)
        pad = x0 + int(W * 0.055)
        text_a(im, (pad, y0 + int(H * 0.026)), "Wake with the birds",
               ImageFont.truetype(FT, int(W * 0.048)), INK, ck)
        # 時刻。**ゆっくり寄る**ので、止まった絵にならない。
        z = 1.0 + 0.06 * ease(t / 2.6)
        ft = ImageFont.truetype(FT, int(W * 0.150 * z))
        text_a(im, (pad, y0 + int(H * 0.072)), ALARM_TIME, ft, INK, ck)
        text_a(im, (pad, y0 + int(H * 0.212)), "First to sing",
               ImageFont.truetype(FB, int(W * 0.032)), SUB, ck)

        # 選ぶ欄。1.6秒で1羽に輪がつく = 「自分で選ぶ」が伝わる。
        fy = y0 + int(H * 0.252)
        fn = ImageFont.truetype(FB, int(W * 0.024))
        for i, (bid, name) in enumerate(ALARM_PICK):
            cx = pad + i * int(W * 0.262)
            picked = i == ALARM_CHOSEN and t >= 1.0
            if picked:
                r = int(84 * ease((t - 1.0) / 0.5))
                ImageDraw.Draw(im).ellipse(
                    [cx + 62 - r, fy + 62 - r, cx + 62 + r, fy + 62 + r],
                    outline=(96, 150, 96, int(255 * ck)), width=7)
            sprite(im, bid, 124, cx, fy, ck)
            text_a(im, (cx + 6, fy + 134), name.split()[-1], fn,
                   INK if picked else SUB, ck)

    head = ALARM_L1 if t < 7.6 else ALARM_L2
    ap = t / 0.6 if t < 7.6 else (t - 7.6) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def alarm_audio():
    # 目覚ましが実際に鳴らす同梱音源。画面で増える時刻に合わせて重ねる。
    return pick_app_songs([b for b, _ in ALARM_JOIN])


# ══════════════════════════════════════════════════════════
# ② 寝落ち — スリープタイマー
# ══════════════════════════════════════════════════════════
# `radio/sleep_mode.dart`:
#  - 選べる長さは kSleepMinutes = **15 / 30 / 60 / 90 分**。
#  - 画面は `RadioNative.setBrightness(0.0)` で**実際に暗くする**。
#  - 鳴らし続けるのはフォアグラウンドサービスなので、画面が消えても止まらない。
#  - 終わりは切らずに沈める(kFadeOut = **最後の1分**)。
# ⚠️ 庭が夜になるのではない。暗くなるのは**画面**。字幕もそう言う。
SLEEP_L1 = "Fall asleep to the garden."
SLEEP_L2 = "It keeps singing after the screen goes dark."
SLEEP_SPECIES = ["Downy Woodpecker", "Pileated Woodpecker",
                 "Ruby-throated Hummingbird"]
SLEEP_CHIPS = [15, 30, 60, 90]
SLEEP_PICK = 1          # 30 min
SLEEP_PICK_AT = 2.4
SLEEP_DIM_AT = 3.2


def _voices(im, t, x, y, a=1.0, gap=0.058):
    """鳴っている鳥。ラジオ画面と同じ並べ方(点が灯って名前が出る)。"""
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FB, int(W * 0.036))
    for i, name in enumerate(SLEEP_SPECIES):
        k = ease((t - 0.4 - i * 0.8) / 0.7)
        if k <= 0:
            continue
        cy = y + i * int(H * gap)
        pulse = 0.70 + 0.30 * (0.5 + 0.5 * math.sin(t * 2.8 + i * 1.3))
        dot(d, x, cy, int(11 * k), (int(104 * pulse), int(178 * pulse),
                                    int(110 * pulse)), k * a)
        text_a(im, (x + 34, cy - int(W * 0.022)), name, f, INK, k * a)


def render_sleep(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)
    # 庭と鳥を隠さない。**札は木より下**に置く(原則5「かわいさ最優先」)。
    sprite(im, "carolina_wren", 168, BRANCH_X - 84, BRANCH_Y - 190)

    x0, y0 = int(W * 0.06), int(H * 0.395)
    x1, y1 = int(W * 0.94), int(H * 0.735)
    card(im, [x0, y0, x1, y1], 36, PAPER, 242)
    pad = x0 + int(W * 0.05)
    text_a(im, (pad, y0 + int(H * 0.018)), "Garden radio",
           ImageFont.truetype(FT, int(W * 0.042)), INK, 1.0)
    vy = y0 + int(H * 0.080)
    _voices(im, t, pad + 12, vy, gap=0.043)

    # Sleep のチップ。押されたものが埋まる = 「選べる」が伝わる。
    text_a(im, (pad, y0 + int(H * 0.212)), "Sleep",
           ImageFont.truetype(FB, int(W * 0.028)), SUB, 1.0)
    cy = y0 + int(H * 0.248)
    fx = pad
    fc = ImageFont.truetype(FB, int(W * 0.029))
    for i, m in enumerate(SLEEP_CHIPS):
        lab = f"{m} min"
        wdt = int(ImageDraw.Draw(im).textlength(lab, font=fc)) + 42
        on = i == SLEEP_PICK and t >= SLEEP_PICK_AT
        k = ease((t - SLEEP_PICK_AT) / 0.4) if on else 0.0
        card(im, [fx, cy, fx + wdt, cy + 62], 31,
             mix((226, 240, 218), ON, k), 242)
        text_a(im, (fx + 21, cy + 16), lab, fc, PAPER if k > 0.5 else INK, 1.0)
        fx += wdt + 15

    # **画面が暗くなる。** 起きる出来事はこれ1つ。
    k = ease((t - SLEEP_DIM_AT) / 6.4)
    veil(im, NIGHT, 228 * k)

    # 暗くなっても声は続いている。点と名前だけ、薄く残す。
    if k > 0.30:
        _voices(im, t, pad + 12, vy, a=0.26 + 0.30 * (1 - k), gap=0.043)

    head = SLEEP_L1 if t < 7.2 else SLEEP_L2
    ap = t / 0.6 if t < 7.2 else (t - 7.2) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def sleep_audio():
    return pick_radio(SLEEP_SPECIES)


# ══════════════════════════════════════════════════════════
# ③ ラジオ — 実録音 + 環境音7層
# ══════════════════════════════════════════════════════════
# `radio/radio_engine.dart`:
#  - 環境音は kAmbienceKeys = **7つ**。表示は kAmbienceLabel の絵文字つき。
#  - 同時に鳴く種は kMaxBirds = **3**。
#  - **よく会った鳥ほど手前で鳴く**(観察回数 → 奥行き)。羽数は "×N" で出る。
#  - 鳴き声は xeno-canto の実録音、環境音は Freesound の CC0。合成音ではない。
RADIO_L1 = "A radio of real recordings."
RADIO_L2 = "Layer rain, wind or a stream behind them."
RADIO_AMB = [("🌧", "Rain"), ("🍃", "Wind"), ("💧", "Stream"), ("🌊", "Waves"),
             ("🏞", "Lake"), ("🔥", "Fire"), ("🕳", "Cave")]
RADIO_ON = {0: 4.6, 1: 5.6, 2: 6.6}      # 灯る時刻


def render_radio(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # 庭と鳥を隠さない。札は木より下に置く。
    sprite(im, "northern_cardinal", 168, BRANCH_X - 84, BRANCH_Y - 190)

    x0, y0 = int(W * 0.05), int(H * 0.355)
    x1, y1 = int(W * 0.95), int(H * 0.745)
    card(im, [x0, y0, x1, y1], 36, PAPER, 242)
    pad = x0 + int(W * 0.05)
    text_a(im, (pad, y0 + int(H * 0.016)), "Garden radio",
           ImageFont.truetype(FT, int(W * 0.042)), INK, 1.0)
    vy = y0 + int(H * 0.074)
    _voices(im, t, pad + 12, vy, gap=0.042)

    # 群れの厚み。**会った回数で増える**もので、勝手な数字ではない。
    if t > 7.4:
        text_a(im, (x1 - int(W * 0.15), vy - int(W * 0.022)), "×3",
               ImageFont.truetype(FB, int(W * 0.036)), SUB,
               ease((t - 7.4) / 0.5))

    # 環境音のタイル。**7つ全部出す**(重ねられることが売り)。
    ty = y0 + int(H * 0.205)
    fc = ImageFont.truetype(FB, int(W * 0.026))
    tw = int((x1 - x0 - int(W * 0.10) - 3 * 15) / 4)
    for i, (ch, lab) in enumerate(RADIO_AMB):
        col, row = i % 4, i // 4
        tx = pad + col * (tw + 15)
        ty2 = ty + row * 96
        at = RADIO_ON.get(i)
        k = ease((t - at) / 0.4) if at is not None and t >= at else 0.0
        card(im, [tx, ty2, tx + tw, ty2 + 80], 32,
             mix((238, 244, 232), ON, k), 246)
        emo(im, (tx + 14, ty2 + 18), ch, 42)
        text_a(im, (tx + 66, ty2 + 26), lab, fc,
               PAPER if k > 0.5 else INK, 1.0)

    head = RADIO_L1 if t < 7.8 else RADIO_L2
    ap = t / 0.6 if t < 7.8 else (t - 7.8) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def radio_audio():
    return pick_radio(SLEEP_SPECIES)


# ══════════════════════════════════════════════════════════
# ④ 出会いの儀式 — 捕まえない
# ══════════════════════════════════════════════════════════
# `garden/ritual.dart`:
#  - ボタンは "Listen closely"。押し続けさせない。
#  - 1歩 = **2.5秒**。前に行くとは限らず、**下がることもある**。
#  - 手前の枝に**2歩**とどまると出会い。ポップアップは "🪶 You met a bird"、
#    初対面なら "Newly added to your guide"。
#  - 鳥は Northern Cardinal。**鳴っている録音もこの種**にしてある。
#    最初は Downy Woodpecker にしたが、ドット絵が黒くて小さく写ると
#    ただの点に見えた(原則5「かわいさ最優先」)。赤は遠くても読める。
RITUAL_L1 = "You don't catch anything here."
RITUAL_L2 = "Listen closely. It comes to you."
RITUAL_BIRD = "northern_cardinal"
# 1歩目も**0.9秒**に前倒し(冒頭1秒で動く)。下がる回は残す。
RITUAL_PATH = [(0.9, 1), (2.6, 0), (4.2, 1), (5.8, 2), (7.1, 1), (8.3, 2)]
RITUAL_SETTLE = 9.3
RITUAL_MET = 10.4


def _seat(depth):
    """奥ほど小さく、高く、薄い。0=奥 b3 / 1=b2 / 2=手前 b1。"""
    return [(BRANCH_X - 255, BRANCH_Y - 232, 108, 0.55),
            (BRANCH_X - 60, BRANCH_Y - 194, 150, 0.78),
            (BRANCH_X + 70, BRANCH_Y - 244, 210, 1.0)][depth]


def render_ritual(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    depth = 0
    for at, br in RITUAL_PATH:
        if t >= at:
            depth = br
    if t >= RITUAL_SETTLE:
        depth = 2
    x, y, size, a = _seat(depth)

    hop = 0.0
    for at, _br in RITUAL_PATH + [(RITUAL_SETTLE, 2)]:
        if 0 <= t - at < 0.45:
            hop = math.sin((t - at) / 0.45 * math.pi) * 26
    sprite(im, RITUAL_BIRD, size, x, y - hop, a)

    # ボタン。**実物の文字列**。押しっぱなしにさせないので、出るのは最初だけ。
    bk = 1.0 - ease((t - 2.6) / 0.8)
    if bk > 0:
        bw = int(W * 0.54)
        bx = (W - bw) // 2
        by = int(H * 0.545)
        card(im, [bx, by, bx + bw, by + 94], 47, (96, 150, 96), 240 * bk)
        f = ImageFont.truetype(FB, int(W * 0.038))
        lab = "Listen closely"
        lw = ImageDraw.Draw(im).textlength(lab, font=f)
        text_a(im, (bx + (bw - lw) / 2, by + 25), lab, f, PAPER, bk)

    # 手前に留まったら、アプリと同じポップアップ。
    if t >= RITUAL_MET:
        k = ease((t - RITUAL_MET) / 0.6)
        px0, py0 = int(W * 0.08), int(H * 0.395)
        px1, py1 = int(W * 0.92), int(H * 0.540)
        card(im, [px0, py0, px1, py1], 34, PAPER, 244 * k)
        emo(im, (px0 + 40, py0 + 30), "🪶", 56)
        text_a(im, (px0 + 122, py0 + 38), "You met a bird",
               ImageFont.truetype(FT, int(W * 0.046)), INK, k)
        text_a(im, (px0 + 42, py0 + 132), "Newly added to your guide",
               ImageFont.truetype(FB, int(W * 0.030)), SUB, k)

    head = RITUAL_L1 if t < 6.4 else RITUAL_L2
    ap = t / 0.6 if t < 6.4 else (t - 6.4) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def ritual_audio():
    # 画面に居るのは Northern Cardinal。**その録音**を主に鳴らす。
    # 2羽目(Robin)は名前を出していない — 庭で他の鳥が鳴くのは嘘にならない。
    return pick_app_songs(["northern_cardinal", "american_robin"])


# ══════════════════════════════════════════════════════════
# ⑤ 図鑑 — 会うと絵が育つ
# ══════════════════════════════════════════════════════════
# `garden/guide_page.dart`:
#  - **全37種**(`data.py` の BIRDS が 37 件。実行して数えた)。
#  - 印は3段階 ❓ まだ来ていない / 🐦 来訪済み / 🪶 近くで出会った。
#    近くで出会うと図版が**アイコンから詳細画に入れ替わる**。
#  - 庭が痩せても図鑑の記録は減らない(交渉不能の原則2)。
GUIDE_L1 = "Meet a bird, it joins your guide."
GUIDE_L2 = "37 birds. Nothing is ever taken away."
# ⚠️ **1行目は 0.3 秒で出す。** 診断書(2026-08-08)の「冒頭1秒で動く」。
# 0.8 にしていたら、最初の1秒がただの ??? の一覧で止まって見えた。
GUIDE_ROWS = [
    ("carolina_wren", "Carolina Wren", 0.3),
    ("northern_cardinal", "Northern Cardinal", 1.5),
    ("blue_jay", "Blue Jay", 2.7),
    ("american_goldfinch", "American Goldfinch", 3.9),
    ("downy_woodpecker", "Downy Woodpecker", 5.1),
    ("eastern_bluebird", "Eastern Bluebird", 6.3),
]
GUIDE_UPGRADE = 8.0        # ここで1行が「近くで出会った」に変わる


def render_guide(t, credit):
    im = Image.new("RGBA", (W, H), (251, 250, 243, 255))

    shown = sum(1 for _b, _n, at in GUIDE_ROWS if t >= at)
    text_a(im, (int(W * 0.08), int(H * 0.070)), f"Guide  {shown}/37",
           ImageFont.truetype(FT, int(W * 0.052)), INK, 1.0)

    uk = ease((t - GUIDE_UPGRADE) / 0.7)
    y = int(H * 0.145)
    fn = ImageFont.truetype(FB, int(W * 0.038))
    for i, (bid, name, at) in enumerate(GUIDE_ROWS):
        k = ease((t - at) / 0.5)
        row_h = int(H * 0.083) + (int(120 * uk) if i == 0 else 0)
        if k <= 0:
            emo(im, (int(W * 0.075), y + 22), "❓", 52)
            text_a(im, (int(W * 0.23), y + 32), "???", fn, (150, 165, 145), 1.0)
        elif i == 0 and uk > 0:
            # 図版が詳細画に入れ替わる。**これが「会うと育つ」**。
            emo(im, (int(W * 0.075), y + 22), "🪶" if uk > 0.5 else "🐦", 52)
            sprite(im, bid, 100, int(W * 0.20), y + 12, 1.0 - uk)
            sprite(im, bid, int(214 * uk), int(W * 0.20), y + 12, uk, detail=True)
            text_a(im, (int(W * 0.20) + int(224 * uk) + 14, y + 32), name,
                   fn, INK, 1.0)
        else:
            emo(im, (int(W * 0.075), y + 22), "🐦", 52)
            sprite(im, bid, 100, int(W * 0.20), y + 12, k)
            text_a(im, (int(W * 0.33), y + 32), name, fn, INK, k)
        y += row_h
        ImageDraw.Draw(im).line([(int(W * 0.07), y - 12), (int(W * 0.93), y - 12)],
                                fill=(225, 230, 212))

    head = GUIDE_L1 if t < 8.6 else GUIDE_L2
    ap = t / 0.6 if t < 8.6 else (t - 8.6) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def guide_audio():
    # 一覧は「いま鳴いている鳥」ではないので、音と行の種が違っても嘘にならない
    # (s12_collect と同じ扱い)。**商用に使える録音だけ**。
    return pick_app_songs(["northern_cardinal", "american_robin",
                           "eastern_bluebird"])


# ══════════════════════════════════════════════════════════
# ⑥ ネットワーク — 植えたものが誰を養うか
# ══════════════════════════════════════════════════════════
# `garden/network_page.dart` は同心円(植物 → 虫 → 鳥)で描く。
# 中身は `data.py` から**実行して取る**(手で書かない)。
# 相互作用は GloBI(Global Biotic Interactions)を参照して作ったシード。
NET_L1 = "Plant something. See who it feeds."
NET_L2 = "The links come from real interaction records."
NET_PLANT = "dogwood"
NET_INSECT = "tent_caterpillar"
# ドット絵がある種だけを図に出す(絵の無い種を描き起こさない)。
NET_SPRITE_BIRDS = ["carolina_wren", "northern_cardinal", "blue_jay",
                    "american_robin", "eastern_bluebird", "tufted_titmouse",
                    "downy_woodpecker", "american_goldfinch"]


def _net_data():
    """`data.py` を読んで、実際の食物網の一部を取る。"""
    sys.path.insert(0, os.path.join(ROOT, "toris_collection"))
    import data  # noqa: E402
    plant = data.PLANTS[NET_PLANT]
    insect = data.INSECTS[NET_INSECT]
    if NET_PLANT not in insect["eats_plants"]:
        raise SystemExit(f"{NET_INSECT} は {NET_PLANT} を食べない")
    rows = []
    for bid in NET_SPRITE_BIRDS:
        b = data.BIRDS[bid]
        via_plant = NET_PLANT in (b.get("eats_plants") or [])
        via_bug = NET_INSECT in (b.get("eats_insects") or [])
        if via_plant or via_bug:
            rows.append((bid, b["english"], via_bug and not via_plant))
    if len(rows) < 6:
        raise SystemExit("図に出せる鳥が少なすぎる")
    return (plant.get("icon", "🌳"), plant["english"],
            insect["english"], rows[:6])


_NET = None

# 上から 植物 → 虫 → 鳥。同心円より、縦長の画面では層のほうが読める。
NET_PY = 0.150
NET_IY = 0.330
NET_BY = [0.500, 0.640]
NET_BX = [0.19, 0.50, 0.81]


def _net_seat(i):
    return int(W * NET_BX[i % 3]), int(H * NET_BY[i // 3])


def render_network(t, credit):
    global _NET
    if _NET is None:
        _NET = _net_data()
    plant_icon, plant_name, insect_name, rows = _NET

    im = Image.new("RGBA", (W, H), (251, 250, 243, 255))
    d = ImageDraw.Draw(im)
    px, py = W // 2, int(H * NET_PY)
    ix, iy = W // 2, int(H * NET_IY)

    # 線を先に引く。**食べる/食べられるの記録があるところだけ**。
    ik = ease((t - 2.6) / 0.6)
    if ik > 0:
        d.line([(px, py + 46), (ix, iy - 40)], fill=(198, 212, 188), width=7)
    for i, (_bid, _n, via_bug) in enumerate(rows):
        k = ease((t - (4.2 + i * 0.8)) / 0.5)
        if k <= 0:
            continue
        bx, by = _net_seat(i)
        sx, sy = (ix, iy + 40) if via_bug else (px, py + 46)
        d.line([(sx, sy), (bx, by - 56)], fill=(208, 220, 198), width=5)

    # いちばん上 = 植えたもの。絵文字は `data.py` の icon をそのまま使う。
    pk = ease(t / 0.7)
    if pk > 0:
        emo(im, (px - 48, py - 48), plant_icon, 96)
        f = ImageFont.truetype(FB, int(W * 0.034))
        text_a(im, (px - d.textlength(plant_name, font=f) / 2, py + 58),
               plant_name, f, INK, pk)

    # 虫。植えたものが**先に養うのはここ**。
    if ik > 0:
        emo(im, (ix - 36, iy - 40), "🐛", 72)
        f = ImageFont.truetype(FB, int(W * 0.028))
        tw = d.textlength(insect_name, font=f)
        # 線が名前を横切って読めなくなるので、下地を敷く。
        card(im, [ix - tw / 2 - 18, iy + 36, ix + tw / 2 + 18, iy + 84], 24,
             (251, 250, 243), int(236 * ik))
        text_a(im, (ix - tw / 2, iy + 44), insect_name, f, SUB, ik)

    # 鳥。3列×2段。名前がぶつからないように、幅で折り返す。
    f = ImageFont.truetype(FB, int(W * 0.024))
    for i, (bid, name, _via) in enumerate(rows):
        k = ease((t - (4.2 + i * 0.8)) / 0.5)
        if k <= 0:
            continue
        bx, by = _net_seat(i)
        sprite(im, bid, 116, bx - 58, by - 58, k)
        for j, part in enumerate(name.split(" ", 1) if
                                 d.textlength(name, font=f) > W * 0.28
                                 else [name]):
            text_a(im, (bx - d.textlength(part, font=f) / 2, by + 58 + j * 34),
                   part, f, INK, k)

    text_a(im, (int(W * 0.07), int(H * 0.715)),
           "Food web seeded from GloBI (Global Biotic Interactions)",
           ImageFont.truetype(FB, int(W * 0.024)), SUB, ease((t - 9.5) / 0.8))

    head = NET_L1 if t < 8.2 else NET_L2
    ap = t / 0.6 if t < 8.2 else (t - 8.2) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def network_audio():
    return pick_radio(SLEEP_SPECIES)


# ⑦ 餌台(かご型/開放型の駆け引き)は **CEO 2026-08-25「F7は要らない」**で外した。
# 連鎖そのものの説明は `toris_core/lib/src/feeder_chain.dart` にある。

# ══════════════════════════════════════════════════════════
FILMS = {
    "alarm":   (render_alarm,   "f01_alarm_15s_1080x1920.mp4",   alarm_audio),
    "sleep":   (render_sleep,   "f02_sleep_15s_1080x1920.mp4",   sleep_audio),
    "radio":   (render_radio,   "f03_radio_15s_1080x1920.mp4",   radio_audio),
    "ritual":  (render_ritual,  "f04_ritual_15s_1080x1920.mp4",  ritual_audio),
    "guide":   (render_guide,   "f05_guide_15s_1080x1920.mp4",   guide_audio),
    "network": (render_network, "f06_network_15s_1080x1920.mp4", network_audio),
}

# 音が増える時刻。**画面で鳥が増える時刻に合わせる**(ずれると鳴いていない
# 鳥が光って見える)。
STARTS = {
    "alarm": [at for _b, at in ALARM_JOIN],
    "sleep": [0.5, 1.4, 2.3],
    "radio": [0.6, 1.6, 2.6],
    "ritual": [0.8, 5.4],
    "guide": [1.0, 3.2, 5.4],
    "network": [0.8, 3.0, 5.2],
}


# TikTok は再生時に -14 LUFS あたりへ正規化する。素のまま混ぜると
# **平均 -40dB 前後**にしかならず(既存の s09〜s13 も同じ)、
# 端末の音量を上げないと鳴き声が聞こえない。**音がこの商品の主役**なので、
# ここで持ち上げる。-16 にしているのは、xeno-canto の録音の暗騒音まで
# 一緒に上げすぎないため。
LOUD_I, LOUD_TP, LOUD_LRA = -16.0, -1.5, 11.0

# ⚠️ **1パスの loudnorm では足りない。**
# 目覚ましは音が 5.0 秒から始まるので、頭に無音が5秒ある。1パスだと
# 出だしの無音を見たまま利得が上がりきらず、**-30.4 LUFS のまま**出た
# (他の6本は -16 前後になっていたので気づいた)。
# なので**測ってから当てる2パス**にする。`linear=true` で一定の利得になり、
# 静かに始まって育つという目覚ましの形も崩れない。
def _loudnorm(measured=None):
    # ⚠️ **後ろに aresample を必ず付ける。**
    # loudnorm は、測った LRA が目標より大きいと `linear=true` を諦めて
    # dynamic モードに落ち、そのとき**出力を 96k/192kHz に変える**。
    # すると後段の `afade=t=out:st=14.6` が実時間の 1/2〜1/4 の位置に落ちて、
    # **動画の途中から音が消える**。2026-08-25 に q02 がこれで
    # 「3秒以降まるごと無音」で書き出された(見た目には何も出ない)。
    tail = ",aresample=48000"
    base = (f"loudnorm=I={LOUD_I}:TP={LOUD_TP}:LRA={LOUD_LRA}")
    if measured is None:
        return base + ":print_format=json" + tail
    return (base + f":measured_I={measured['input_i']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true" + tail)


def _measure(ff, silent, ain, mix_core):
    """1パス目。混ぜたあとの実際の音量を測って返す。"""
    r = subprocess.run(
        [ff, "-y", "-i", silent] + ain +
        ["-filter_complex", mix_core + _loudnorm() + "[aout]",
         "-map", "[aout]", "-t", str(DUR), "-f", "null", "-"],
        capture_output=True, text=True, errors="replace")
    m = re.findall(r"\{[^{}]*input_i[^{}]*\}", r.stderr, re.S)
    if not m:
        print(r.stderr[-600:])
        raise SystemExit("音量の測定に失敗")
    return json.loads(m[-1])


def build(kind, remux=False):
    render, name, audio = FILMS[kind]
    used, credit = audio()
    out = os.path.join(OUT_DIR, name)
    tmp = os.path.join(os.path.dirname(__file__), f"_feat_{kind}")
    os.makedirs(tmp, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    silent = os.path.join(tmp, "silent.mp4")

    # [remux] は**音だけ作り直す**とき。絵は1本あたり75秒かかるので、
    # 音量や重ね方をいじるだけなら描き直さない。
    if not (remux and os.path.exists(silent)):
        n = int(DUR * FPS)
        for f in range(n):
            t = f / FPS
            im = render(t, credit)
            draw_cta(im, t)
            im.convert("RGB").save(os.path.join(tmp, f"f{f:04d}.png"))

        r = subprocess.run(
            [ff, "-y", "-framerate", str(FPS),
             "-i", os.path.join(tmp, "f%04d.png"),
             "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", silent],
            capture_output=True, text=True, errors="replace")
        if r.returncode:
            print(r.stderr[-800:])
            raise SystemExit(f"{kind}: 連番の書き出しに失敗")

    starts = STARTS[kind]
    ain, amix = [], []
    for i, aud in enumerate(used[:4]):
        ain += ["-i", aud]
        delay = int((starts[i] if i < len(starts) else 0) * 1000)
        amix.append(f"[{i+1}:a]atrim=0:{DUR},adelay={delay}|{delay},"
                    f"volume=0.55[a{i}]")
    core = "".join(x + ";" for x in amix)
    core += "".join(f"[a{i}]" for i in range(len(amix)))
    core += f"amix=inputs={len(amix)}:duration=first:dropout_transition=2,"

    measured = _measure(ff, silent, ain, core)
    mix = core + _loudnorm(measured) + ","
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
    print(f"  {credit}")


if __name__ == "__main__":
    args = sys.argv[1:]
    remux = "--remux" in args
    want = [a for a in args if not a.startswith("-")] or list(FILMS)
    for k in want:
        if k not in FILMS:
            raise SystemExit(f"知らない題目: {k} / 使えるのは {list(FILMS)}")
        print(f"[{k}]")
        build(k, remux=remux)
