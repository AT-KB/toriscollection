"""同じことを、別の見せ方で言う15秒 × 7本(バッチ4)。

CEO 2026-08-25「もっと幅を増やしてほしい。**メッセージは同じで見せ方の
バリエーション**」。挙がった題材:
  コンセプト(植生で鳥を呼ぶ / 鳥で起きる / 鳥と寝る / アメリカの庭をおうちに)
  鳴き声が鳴いてる感 / 植物を植えたら寄ってくるところ / 図鑑と詳細

`build_feature15.py`(バッチ3)は**機能を説明する**作りだった。
こちらは**同じ言い分を、絵の作り方だけ変えて**出す。
道具(札・字幕帯・CTA・音量)はバッチ3から丸ごと借りる。

| | 題材 | 見せ方 |
|---|---|---|
| g01 | 植えたら寄ってくる | **時間経過**。植える→咲く→虫が湧く→鳥が来る |
| g02 | アメリカの庭をおうちに | **土地の切替**。Charlotte ⇄ Kyoto で顔ぶれが入れ替わる |
| g03 | 鳴き声が鳴いてる感 | **音を絵にする**。鳴くたびに波紋。近い鳥ほど輪が大きい |
| g04 | 図鑑と詳細 | **図鑑の1ページを実物どおり**に組む |
| g05 | 鳥で起きる(g05 = f01 と同じ言い分) | **寄り**。時計は隅。1羽ずつ手前に大きく |
| g06 | 鳥と寝る(g06 = f02 と同じ言い分) | **沈む**。札を出さず、庭ごと暗くして声の点だけ残す |
| g07 | 一日 | 朝(起きる)→ 昼(庭)→ 夜(寝る)を通しで |

## 守っていること(バッチ3と同じ)
 - 絵は `toris_app/assets/sprites/` の**アプリ本物**。描き起こさない。
 - 画面の文言は**アプリの実物の文字列**("Your land" / "Plant 1/4" /
   "Insects" / "WHY IT CAME" / "Likes" / "Home" / "Fears")。
 - **図鑑の中身は `data.py` から実行して取る。**手で書かない。
 - 音は配布可の録音だけ。**画面に名前を出した鳥は、その録音を鳴らす。**

実行:
    py -3 tools/video_build/build_variants15.py           # 7本
    py -3 tools/video_build/build_variants15.py plant     # 1本だけ
    py -3 tools/video_build/build_variants15.py --remux   # 音だけ作り直す
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import (  # noqa: E402
    BRANCH_X, BRANCH_Y, FB, FT, GROUND, H, PAPER, ROOT, W,
    draw_band, draw_garden, ease,
)
from build_sleep_wake15 import DAWN, NIGHT, pick_app_songs, pick_radio, veil  # noqa: E402
import build_feature15 as F  # noqa: E402
from build_feature15 import INK, ON, SUB, card, dot, emo, mix, sprite, text_a  # noqa: E402

DUR = F.DUR
OUT_DIR = F.OUT_DIR


def _data():
    """`data.py` を読む。図鑑の中身を手で書かないため。"""
    sys.path.insert(0, os.path.join(ROOT, "toris_collection"))
    import data  # noqa: E402
    return data


# ══════════════════════════════════════════════════════════
# g01 植えたら寄ってくる — 時間経過で見せる
# ══════════════════════════════════════════════════════════
# 何が本当か:
#  - 植えられるのは**その土地の植物だけ**(`data.PLANTS[x]['biome']` で絞る。
#    `garden_page.dart` の `availablePlants`)。Charlotte は `max_plants = 4`。
#  - 植物 → 虫(`INSECTS[x]['eats_plants']`)→ 鳥(`BIRDS[x]['eats_insects']`)。
#    これが到来確率の元(`engine.build_network`)。
#  - **鳥は押しても来ない。**留守のあいだに確率で来る(原則1)。
#    だから字幕も「待つ」としか言わない。
PLANT_L1 = "Plant what actually grows there."
PLANT_L2 = "The insects come. Then the birds."
PLANT_ID = "dogwood"
PLANT_GROW = (1.4, 4.2)           # せり上がる区間
PLANT_BUGS = 5.0                  # 虫が湧く
# (種, 来る時刻)。**dogwood を実際に食べる鳥**から選んだ(下で確かめる)。
PLANT_BIRDS = [("northern_cardinal", 7.2),
               ("american_robin", 9.4),
               ("eastern_bluebird", 11.4)]


def _check_plant_chain():
    """字幕どおりの経路が本当にあるか、data.py で確かめる。"""
    d = _data()
    bugs = [i for i, v in d.INSECTS.items()
            if PLANT_ID in (v.get("eats_plants") or [])]
    if not bugs:
        raise SystemExit(f"{PLANT_ID} を食べる虫がいない")
    # ⚠️ **絵と名前を合わせる。** 庭に出しているのは 🐛(いも虫)なので、
    # 名前も芋虫のものにする。最初は先頭の Monarch Butterfly が出て、
    # 🐛 の絵に「チョウ」の名前が付いていた。
    bugs.sort(key=lambda i: 0 if "caterpillar" in
              d.INSECTS[i]["english"].lower() else 1)
    for bid, _at in PLANT_BIRDS:
        b = d.BIRDS[bid]
        if PLANT_ID not in (b.get("eats_plants") or []) and \
                not set(bugs) & set(b.get("eats_insects") or []):
            raise SystemExit(f"{bid} は {PLANT_ID} の経路につながっていない")
    return (d.PLANTS[PLANT_ID].get("icon", "🌱"),
            d.PLANTS[PLANT_ID]["english"],
            d.INSECTS[bugs[0]]["english"],
            d.BIOMES["charlotte"]["max_plants"])


_PLANT = None


def render_plant(t, credit):
    global _PLANT
    if _PLANT is None:
        _PLANT = _check_plant_chain()
    icon, pname, bugname, maxp = _PLANT

    grow = ease((t - PLANT_GROW[0]) / (PLANT_GROW[1] - PLANT_GROW[0]))
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, grow)

    # 虫。アプリの庭にも "Insects" の欄で出るので、庭にも湧かせる。
    if t >= PLANT_BUGS:
        k = ease((t - PLANT_BUGS) / 0.8)
        for i, bx in enumerate([0.28, 0.42, 0.64, 0.76]):
            if k * 4 < i:
                continue
            wob = math.sin(t * 2.4 + i * 1.7) * 10
            emo(im, (int(W * bx) - 22 + wob, GROUND - 96 - i % 2 * 26),
                "🐛", 44)

    # 鳥。右の外から入ってきて、枝にとまる。**押して呼んだのではない。**
    seats = [(BRANCH_X - 210, BRANCH_Y - 176),
             (BRANCH_X + 40, BRANCH_Y - 172),
             (BRANCH_X + 200, BRANCH_Y - 140)]
    for i, (bid, at) in enumerate(PLANT_BIRDS):
        if t < at:
            continue
        k = ease((t - at) / 1.0)
        sx, sy = int(W * 1.10), int(H * 0.12)
        tx, ty = seats[i]
        x = sx + (tx - sx) * k
        y = sy + (ty - sy) * k
        if k < 1.0:
            y += math.sin(t * 8.5) * 16 * (1 - k)
        sprite(im, bid, 168, x, y)

    # 「Plant 1/4」。**実物の見出しと同じ形**。
    # 庭には4株がいっしょにせり上がるので、**数もせり上がりに合わせる**
    # (1株だけ育つのに 1/4 のまま、では絵と数が食い違う)。
    n = min(maxp, math.ceil(grow * maxp))
    lab = f"Plant  {n}/{maxp}"
    fl = ImageFont.truetype(FB, int(W * 0.030))
    lw = ImageDraw.Draw(im).textlength(lab, font=fl)
    card(im, [int(W * 0.06), int(H * 0.072), int(W * 0.06) + lw + 190,
              int(H * 0.072) + 78], 34, PAPER, 236)
    text_a(im, (int(W * 0.06) + 26, int(H * 0.072) + 22), lab, fl, SUB, 1.0)
    if n:
        emo(im, (int(W * 0.06) + 34 + lw + 24, int(H * 0.072) + 16), icon, 44)

    # 何を植えたか / 何が湧いたか。**名前は data.py から**。
    fn = ImageFont.truetype(FB, int(W * 0.032))
    if t >= PLANT_GROW[0]:
        text_a(im, (int(W * 0.07), int(H * 0.168)), pname, fn, INK,
               ease((t - PLANT_GROW[0]) / 0.6))
    if t >= PLANT_BUGS:
        text_a(im, (int(W * 0.07), int(H * 0.218)), f"Insects: {bugname}",
               ImageFont.truetype(FB, int(W * 0.028)), SUB,
               ease((t - PLANT_BUGS) / 0.6))

    head = PLANT_L1 if t < 7.0 else PLANT_L2
    ap = t / 0.6 if t < 7.0 else (t - 7.0) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def plant_audio():
    return pick_app_songs([b for b, _ in PLANT_BIRDS])


# ══════════════════════════════════════════════════════════
# g02 アメリカの庭をおうちに — 土地の切替で見せる
# ══════════════════════════════════════════════════════════
# 何が本当か:
#  - 土地は **Charlotte と Kyoto の2つだけ**(`data.BIOMES`)。画面の見出しは
#    "Your land"、名前は `name_en`(Charlotte / Kyoto)。
#  - 鳥は `biome_pref` で土地ごとに顔ぶれが変わる。**庭の絵は同じ**
#    (`tree_scene.dart` は biome を受け取らない)ので、絵も同じにする。
#    ここで京都だけ別の庭を描いたら、それは嘘になる。
LAND_L1 = "An American backyard, on your phone."
LAND_L2 = "Or a Kyoto garden. Different land, different birds."
LAND_SWAP = 7.6
# ⚠️ **鳴らせる録音がある種を選ぶ。** 最初は Cardinal / Blue Jay / Wren を
# 出そうとしたが、配布可プールにその3種の録音が無く、**画面の鳥と鳴っている
# 録音が別**になるところだった。Kyoto 側は 1羽目(メジロ)が鳴る。
LAND_US = ["downy_woodpecker", "pileated_woodpecker",
           "ruby_throated_hummingbird"]
LAND_JP = ["mejiro", "shijukara", "enaga"]


def _check_lands():
    d = _data()
    for bid in LAND_US:
        if "charlotte" not in (d.BIRDS[bid].get("biome_pref") or []):
            raise SystemExit(f"{bid} は Charlotte の鳥ではない")
    for bid in LAND_JP:
        if "kyoto" not in (d.BIRDS[bid].get("biome_pref") or []):
            raise SystemExit(f"{bid} は Kyoto の鳥ではない")
    return [d.BIOMES["charlotte"]["name_en"], d.BIOMES["kyoto"]["name_en"]]


_LANDS = None


def render_land(t, credit):
    global _LANDS
    if _LANDS is None:
        _LANDS = _check_lands()
    names = _LANDS

    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    seats = [(BRANCH_X - 210, BRANCH_Y - 176),
             (BRANCH_X + 40, BRANCH_Y - 172),
             (BRANCH_X + 200, BRANCH_Y - 140)]
    # 切り替わる瞬間だけ、入れ替わりを見せる(消えて、現れる)。
    k = ease((t - LAND_SWAP) / 0.9)
    for i, (a, b) in enumerate(zip(LAND_US, LAND_JP)):
        x, y = seats[i]
        show = ease((t - 1.0 - i * 0.9) / 0.7)
        sprite(im, a, 168, x, y, show * (1 - k))
        sprite(im, b, 168, x, y, k * ease((t - LAND_SWAP - i * 0.35) / 0.7))

    # "Your land" の切替。**実物の見出しと同じ形**。
    text_a(im, (int(W * 0.07), int(H * 0.075)), "Your land",
           ImageFont.truetype(FB, int(W * 0.030)), SUB, 1.0)
    fc = ImageFont.truetype(FB, int(W * 0.032))
    fx = int(W * 0.07)
    for i, nm in enumerate(names):
        wdt = int(ImageDraw.Draw(im).textlength(nm, font=fc)) + 56
        sel = (i == 1) if t >= LAND_SWAP else (i == 0)
        kk = 1.0 if sel else 0.0
        card(im, [fx, int(H * 0.112), fx + wdt, int(H * 0.112) + 74], 37,
             mix((235, 242, 228), ON, kk), 240)
        text_a(im, (fx + 28, int(H * 0.112) + 20), nm, fc,
               PAPER if sel else INK, 1.0)
        fx += wdt + 18

    head = LAND_L1 if t < LAND_SWAP else LAND_L2
    ap = t / 0.6 if t < LAND_SWAP else (t - LAND_SWAP) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def land_audio():
    # 前半 = Charlotte の鳥、後半 = Kyoto の鳥。**土地をまたいで鳴かせない。**
    # 配布可プールにある京都の種は Japanese White-eye(メジロ)。
    # プールでの名は "Warbling White-eye"(Zosterops japonicus の現行の英名)。
    # アプリの表示名は "Japanese White-eye" だが、**この動画は鳥の名前を
    # 画面に出さない**ので、表示の食い違いは起きない。
    return pick_radio(["Downy Woodpecker", "Pileated Woodpecker",
                       "Warbling White-eye"])


# ══════════════════════════════════════════════════════════
# g03 鳴き声が鳴いてる感 — 音を絵にする
# ══════════════════════════════════════════════════════════
# 何が本当か(`radio_engine.dart`):
#  - 鳴く/休むは音量だけで表す。1羽 2.5〜5.5秒 鳴いて、2.5〜20秒 休む。
#  - **奥行きで音量と残響が変わる**(kDepthGain / kDepthWet / kDepthFreq)。
#  - 奥行きは**観察回数**で決まる(`_obs_to_depth`)= よく会った鳥ほど手前。
#  - 録音は xeno-canto の実録音。合成音ではない。
SONG_L1 = "Real recordings. Nothing generated."
SONG_L2 = "The ones you've met sing closest."
# (種, 表示名, 鳴き始め, 奥行き 0=手前). **音の重なりと同じ時刻**にする。
SONG_CAST = [("downy_woodpecker", "Downy Woodpecker", 0.8, 0),
             ("pileated_woodpecker", "Pileated Woodpecker", 3.4, 1),
             ("ruby_throated_hummingbird", "Ruby-throated Hummingbird", 6.0, 2)]
SONG_SEATS = [(BRANCH_X + 40, BRANCH_Y - 196, 210),
              (BRANCH_X - 250, BRANCH_Y - 172, 156),
              (BRANCH_X + 250, BRANCH_Y - 250, 112)]


def _ripple(im, cx, cy, t, since, depth):
    """鳴っているあいだ広がる輪。**手前の鳥ほど大きく・濃く**。

    ⚠️ 白い輪だけだと、**葉の緑の上で消える**。外側に濃い輪を1本添えて、
    空でも葉でも読めるようにする。
    """
    if since < 0:
        return
    scale = [1.0, 0.72, 0.5][depth]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for n in range(3):
        ph = (since * 0.62 - n * 0.34) % 1.0
        if since * 0.62 < n * 0.34:
            continue
        r = int((60 + 250 * ph) * scale)
        a = int(225 * (1 - ph) * scale)
        if a <= 3:
            continue
        w = max(3, int(9 * scale))
        od.ellipse([cx - r - w, cy - int(r * 0.72) - w,
                    cx + r + w, cy + int(r * 0.72) + w],
                   outline=(46, 74, 48, int(a * 0.45)), width=max(2, w // 2))
        od.ellipse([cx - r, cy - int(r * 0.72), cx + r, cy + int(r * 0.72)],
                   outline=(255, 255, 255, a), width=w)
    im.alpha_composite(ov)


def render_song(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    for i, (bid, _n, at, depth) in enumerate(SONG_CAST):
        x, y, size = SONG_SEATS[i]
        if t < at - 0.4:
            continue
        _ripple(im, x + size // 2, y + size // 2, t, t - at, depth)
        sprite(im, bid, size, x, y, ease((t - at + 0.4) / 0.5))

    # 誰が鳴っているか。ラジオ画面と同じ「点 + 名前」。
    # ⚠️ **鳴っていない鳥の名前は光らせない**(2026-08-19 に踏んだ穴)。
    px, py = int(W * 0.07), int(H * 0.545)
    card(im, [px - 26, py - 34, int(W * 0.93), py + int(H * 0.126)], 34,
         PAPER, 248)
    f = ImageFont.truetype(FB, int(W * 0.034))
    for i, (_b, name, at, depth) in enumerate(SONG_CAST):
        k = ease((t - at) / 0.5)
        cy = py + i * int(H * 0.048)
        pulse = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(t * 3.2 + i * 1.4))
        dot(d, px, cy, int(11 * k), (int(104 * pulse), int(178 * pulse),
                                     int(110 * pulse)), k)
        text_a(im, (px + 34, cy - int(W * 0.021)), name, f, INK, k)
        if k > 0.5 and depth == 0:
            text_a(im, (int(W * 0.80), cy - int(W * 0.021)), "×3",
                   ImageFont.truetype(FB, int(W * 0.030)), SUB, k)

    head = SONG_L1 if t < 8.0 else SONG_L2
    ap = t / 0.6 if t < 8.0 else (t - 8.0) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def song_audio():
    return pick_radio([n for _b, n, _a, _d in SONG_CAST])


# ══════════════════════════════════════════════════════════
# g04 図鑑と詳細 — 1ページを実物どおりに組む
# ══════════════════════════════════════════════════════════
# `guide_page.dart` の版面をそのまま:
#   図版(近くで会うと詳細画)+ 英名 + 学名(斜体)+ ★ + 会った日数
#   ── Likes / Home / Fears ── WHY IT CAME ── description_en
# 中身は **`data.py` と `bird_profile.py` を実行して取る**。手で書かない。
PLATE_L1 = "Meet it up close."
PLATE_L2 = "The guide keeps the reason it came."
PLATE_BIRD = "northern_cardinal"


def _plate_data():
    d = _data()
    sys.path.insert(0, os.path.join(ROOT, "toris_collection"))
    import bird_profile as bp  # noqa: E402
    b = d.BIRDS[PLATE_BIRD]
    prof = bp.build(PLATE_BIRD, b, d.PLANTS, d.INSECTS, d.BIOMES)
    # ⚠️ **絵文字と文字は別のフォントで焼く。** ひとつの文字列にして
    # Segoe UI で描いたら、🌸🌳🐛 が全部 豆腐(□)になった。(絵文字, 名前) で持つ。
    likes = []
    for l in prof["likes"]:
        e = l["entity"]
        likes.append((e.get("icon", "🌱") if l["kind"] == "plant" else "🐛",
                      e["english"]))
    home = [("", h["entity"]["name_en"]) for h in prof["home"]]
    labels = {"raptor": "Hawks", "owl": "Owls", "falcon": "Falcons",
              "snake": "Snakes", "crow": "Crows and jays", "shrike": "Shrikes",
              "cat": "Cats", "raccoon": "Raccoons", "weasel": "Weasels",
              "fox": "Foxes", "squirrel": "Squirrels", "rodent": "Mice and rats"}
    fears = [("", labels[c]) for c in prof["fears"]["categories"] if c in labels]
    stars = "★" * (1 + int(float(b.get("rarity", 0.5)) * 5))
    # 「なぜ来たか」の一文は i18n.py の出荷済みの英語そのまま。
    plant = d.PLANTS[(b.get("eats_plants") or ["dogwood"])[0]]["english"]
    why = (f"{b['english']} came. It seems to have stopped by, "
           f"drawn to {plant}.")
    return (b["english"], b.get("scientific", ""), stars, likes, home, fears,
            why, b.get("description_en", ""))


_PLATE = None


def _rows(im, x, y, label, items, k, w):
    """図鑑の1行。左に見出し、右に中身。

    [items] は (絵文字, 名前) の並び。**絵文字は絵文字のフォントで**別に描く
    (同じ文字列に混ぜると豆腐になる)。入りきらなければ折り返す。
    """
    if k <= 0 or not items:
        return y
    fl = ImageFont.truetype(FB, int(W * 0.026))
    fv = ImageFont.truetype(FB, int(W * 0.030))
    text_a(im, (x, y + 4), label, fl, SUB, k)
    vx = x + int(W * 0.19)
    right = x + w
    d = ImageDraw.Draw(im)
    cx, cy = vx, y
    for icon, name in items:
        need = (44 if icon else 0) + d.textlength(name, font=fv) + 30
        if cx > vx and cx + need > right:
            cx, cy = vx, cy + 46
        if icon:
            emo(im, (cx, cy - 4), icon, 34)
            cx += 44
        text_a(im, (cx, cy), name, fv, INK, k)
        cx += d.textlength(name, font=fv) + 30
    return cy + 56


def render_plate(t, credit):
    global _PLATE
    if _PLATE is None:
        _PLATE = _plate_data()
    name, sci, stars, likes, home, fears, why, desc = _PLATE

    im = Image.new("RGBA", (W, H), (251, 250, 243, 255))
    x0, x1 = int(W * 0.06), int(W * 0.94)
    card(im, [x0, int(H * 0.055), x1, int(H * 0.640)], 26, (255, 254, 248), 255)
    ImageDraw.Draw(im).rounded_rectangle(
        [x0, int(H * 0.055), x1, int(H * 0.640)], 26,
        outline=(225, 230, 212), width=3)

    pad = x0 + int(W * 0.045)
    # 図版。**アイコン → 詳細画に入れ替わる**(近くで会うと絵が育つ)。
    up = ease((t - 2.6) / 1.0)
    py = int(H * 0.085)
    sprite(im, PLATE_BIRD, 150, pad, py + 20, 1.0 - up)
    sprite(im, PLATE_BIRD, int(232 * up), pad, py, up, detail=True)

    hx = pad + int(W * 0.24)
    text_a(im, (hx, py + 6), name, ImageFont.truetype(FT, int(W * 0.048)),
           INK, ease(t / 0.6))
    text_a(im, (hx, py + 74), sci,
           ImageFont.truetype("C:/Windows/Fonts/georgiai.ttf", int(W * 0.030)),
           SUB, ease((t - 0.5) / 0.6))
    # ★ は Segoe UI に無く豆腐になる。**記号のフォント**で描く。
    # 会った日数のバッジは `guide_page.dart` の `_badge` と同じ形
    # (10日以上 = 🌱 N days together)。12日は**見本の数**で、人によって違う。
    kk = ease((t - 1.0) / 0.6)
    text_a(im, (hx, py + 128), stars,
           ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", int(W * 0.026)),
           SUB, kk)
    if kk > 0:
        emo(im, (hx + 90, py + 122), "🌱", 30)
        text_a(im, (hx + 128, py + 128), "12 days together",
               ImageFont.truetype(FB, int(W * 0.026)), SUB, kk)

    y = int(H * 0.275)
    ImageDraw.Draw(im).line([(pad, y - 22), (x1 - int(W * 0.045), y - 22)],
                            fill=(225, 230, 212), width=3)
    w = x1 - int(W * 0.045) - pad
    y = _rows(im, pad, y, "Likes", likes, ease((t - 4.0) / 0.6), w)
    y = _rows(im, pad, y, "Home", home, ease((t - 5.0) / 0.6), w)
    y = _rows(im, pad, y, "Fears", fears, ease((t - 6.0) / 0.6), w)

    k = ease((t - 7.6) / 0.7)
    if k > 0:
        ImageDraw.Draw(im).line([(pad, y - 10), (x1 - int(W * 0.045), y - 10)],
                                fill=(225, 230, 212), width=3)
        text_a(im, (pad, y + 12), "WHY IT CAME",
               ImageFont.truetype(FB, int(W * 0.023)), SUB, k)
        # 最初の1件には 🌱(その関係が出会いのきっかけだった、の印)。
        emo(im, (pad, y + 58), "🌱", 40)
        fw = ImageFont.truetype(FB, int(W * 0.029))
        line, yy = "", y + 62
        for word in why.split():
            cand = (line + " " + word).strip()
            if ImageDraw.Draw(im).textlength(cand, font=fw) > w - 64:
                text_a(im, (pad + 56, yy), line, fw, INK, k)
                yy += 44
                line = word
            else:
                line = cand
        text_a(im, (pad + 56, yy), line, fw, INK, k)

        # 最後に説明文(`description_en`)。版面の下が空いてしまうので、
        # **アプリの図鑑と同じ順**でここに置く。
        dk = ease((t - 9.4) / 0.8)
        if dk > 0 and desc:
            yy += 74
            ImageDraw.Draw(im).line(
                [(pad, yy - 26), (x1 - int(W * 0.045), yy - 26)],
                fill=(225, 230, 212), width=3)
            line = ""
            for word in desc.split():
                cand = (line + " " + word).strip()
                if ImageDraw.Draw(im).textlength(cand, font=fw) > w - 10:
                    text_a(im, (pad, yy), line, fw, INK, dk)
                    yy += 46
                    line = word
                else:
                    line = cand
            text_a(im, (pad, yy), line, fw, INK, dk)

    head = PLATE_L1 if t < 7.4 else PLATE_L2
    ap = t / 0.6 if t < 7.4 else (t - 7.4) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def plate_audio():
    # 図鑑の1ページは「いま鳴いている鳥」ではないが、**主役は1種**なので
    # その種の録音を鳴らす(同梱の商用可プールに Northern Cardinal がある)。
    return pick_app_songs([PLATE_BIRD, "american_robin"])


# ══════════════════════════════════════════════════════════
# g05 鳥で起きる — f01 と同じ言い分を、寄りで
# ══════════════════════════════════════════════════════════
# 言い分は `build_feature15.ALARM_L1 / L2` と**同じ文**を使い回す。
# 変えるのは絵だけ(設定画面を出さず、暗い画面から鳥が1羽ずつ手前に来る)。
WAKE_JOIN = F.ALARM_JOIN
# ⚠️ **枝か地面に置く。** 最初は空の高いところに並べていて、
# 何にもとまっていない鳥が浮いて見えた。ドット絵は
# `y = BRANCH_Y - (size + 8)` で枝に足がそろう(既存の並べ方と同じ)。
# 2羽目は芝の上 — Robin が芝で餌を探すのは実際の姿。
WAKE_SEATS = [(int(W * 0.29), BRANCH_Y - 338, 330),
              (int(W * 0.60), GROUND + 20, 190),
              (int(W * 0.575), BRANCH_Y - 158, 150)]


def render_wake(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # 夜 → 夜明け。**起きる出来事はこれ1つ。**
    night = 1.0 - ease((t - 1.0) / 10.0)
    veil(im, NIGHT, 212 * night)
    veil(im, DAWN, 70 * (1 - abs(night - 0.5) * 2))

    for i, (bid, at) in enumerate(WAKE_JOIN):
        if t < at - 0.6:
            continue
        k = ease((t - at + 0.6) / 1.0)
        x, y, size = WAKE_SEATS[i]
        # 手前へ寄ってくる感じ。**大きくなりながら現れる。**
        # 足元は動かさないので、縮んだぶんは下へ寄せる。
        sz = int(size * (0.72 + 0.28 * k))
        sprite(im, bid, sz, x + (size - sz) // 2, y + (size - sz), k)

    # 時刻は隅に小さく。設定画面は出さない(それは f01 の役)。
    text_a(im, (int(W * 0.07), int(H * 0.072)), F.ALARM_TIME,
           ImageFont.truetype(FT, int(W * 0.062)),
           (236, 244, 232) if night > 0.4 else INK, 1.0)
    text_a(im, (int(W * 0.07), int(H * 0.118)), "Wake with the birds",
           ImageFont.truetype(FB, int(W * 0.026)),
           (196, 214, 196) if night > 0.4 else SUB, 1.0)

    head = F.ALARM_L1 if t < 7.6 else F.ALARM_L2
    ap = t / 0.6 if t < 7.6 else (t - 7.6) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def wake_audio():
    return pick_app_songs([b for b, _ in WAKE_JOIN])


# ══════════════════════════════════════════════════════════
# g06 鳥と寝る — f02 と同じ言い分を、札を出さずに
# ══════════════════════════════════════════════════════════
# 変えるのは絵だけ。ラジオの札もチップも出さず、**庭ごと沈める**。
# 残すのは「点と名前」だけ = 画面が暗くなっても鳴っている、という一点。
SLEEP_CAST = F.SLEEP_SPECIES


def render_sleep2(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)
    sprite(im, "carolina_wren", 190, BRANCH_X - 96, BRANCH_Y - 206)
    sprite(im, "downy_woodpecker", 150, BRANCH_X + 156, BRANCH_Y - 172)

    # **沈む。**最後まで真っ黒にはしない(止まって見える瞬間を作らない)。
    k = ease((t - 1.8) / 8.4)
    veil(im, NIGHT, 236 * k)

    # 声だけが残る。暗くなるほど点がよく見える。
    px, py = int(W * 0.10), int(H * 0.60)
    f = ImageFont.truetype(FB, int(W * 0.036))
    d = ImageDraw.Draw(im)
    for i, name in enumerate(SLEEP_CAST):
        kk = ease((t - 0.4 - i * 0.9) / 0.7)
        if kk <= 0:
            continue
        cy = py + i * int(H * 0.052)
        pulse = 0.66 + 0.34 * (0.5 + 0.5 * math.sin(t * 2.6 + i * 1.3))
        a = kk * (0.42 + 0.58 * k)
        dot(d, px, cy, int(11 * kk), (int(120 * pulse), int(198 * pulse),
                                      int(128 * pulse)), a)
        text_a(im, (px + 34, cy - int(W * 0.022)), name, f,
               (214, 232, 206) if k > 0.45 else INK, a)

    # 終わる時刻。**画面に本当に出るのはこれ**(README 2026-08-18)。
    if t > 4.4:
        # ⚠️ 画面に本当に出るのは**終わる時刻**。スリープは最長90分なので、
        # 朝までの時刻を書くと嘘になる(30分を 10:00 PM に始めた例)。
        text_a(im, (px, int(H * 0.522)), "× Until 10:30 PM",
               ImageFont.truetype(FB, int(W * 0.030)),
               (176, 200, 176), ease((t - 4.4) / 0.8))

    head = F.SLEEP_L1 if t < 7.2 else F.SLEEP_L2
    ap = t / 0.6 if t < 7.2 else (t - 7.2) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def sleep2_audio():
    return pick_radio(SLEEP_CAST)


# ══════════════════════════════════════════════════════════
# g07 一日 — 朝・昼・夜を通しで
# ══════════════════════════════════════════════════════════
# コンセプトそのもの。**3つの機能を並べるのではなく、1日の流れとして見せる。**
DAY_L1 = "Wake with them. Watch them."
DAY_L2 = "Then fall asleep to them."
DAY_DAWN, DAY_NOON, DAY_DUSK = 1.0, 5.6, 10.0


def render_day(t, credit):
    im = Image.new("RGBA", (W, H), (226, 238, 243, 255))
    d = ImageDraw.Draw(im)
    draw_garden(d, 1.0)

    # 朝 → 昼 → 夜。ひと続きの明るさで表す。
    if t < DAY_NOON:
        night = 1.0 - ease((t - DAY_DAWN) / (DAY_NOON - DAY_DAWN))
    elif t < DAY_DUSK:
        night = 0.0
    else:
        night = ease((t - DAY_DUSK) / 4.2)
    veil(im, NIGHT, 214 * night)
    veil(im, DAWN, 66 * (1 - abs(night - 0.5) * 2))

    seats = [(BRANCH_X - 214, BRANCH_Y - 178),
             (BRANCH_X + 40, BRANCH_Y - 174),
             (BRANCH_X + 202, BRANCH_Y - 142)]
    for i, (bid, at) in enumerate([("northern_cardinal", 1.6),
                                   ("american_robin", 3.0),
                                   ("eastern_bluebird", 4.4)]):
        if t < at:
            continue
        sprite(im, bid, 168, *seats[i], ease((t - at) / 0.8))

    # いま何をしているか。**アプリの実物の見出し**を、時間帯ごとに1つだけ。
    if t < DAY_NOON:
        lab, sub = "Wake with the birds", "6:30"
    elif t < DAY_DUSK:
        lab, sub = "Garden radio", "Listen"
    else:
        lab, sub = "Sleep", "30 min"
    on_dark = night > 0.4
    text_a(im, (int(W * 0.07), int(H * 0.072)), lab,
           ImageFont.truetype(FT, int(W * 0.044)),
           (236, 244, 232) if on_dark else INK, 1.0)
    text_a(im, (int(W * 0.07), int(H * 0.118)), sub,
           ImageFont.truetype(FB, int(W * 0.030)),
           (196, 214, 196) if on_dark else SUB, 1.0)

    head = DAY_L1 if t < 9.0 else DAY_L2
    ap = t / 0.6 if t < 9.0 else (t - 9.0) / 0.6
    draw_band(im, ImageDraw.Draw(im), head, None, credit, ap)
    return im


def day_audio():
    return pick_app_songs(["northern_cardinal", "american_robin",
                           "eastern_bluebird"])


# ══════════════════════════════════════════════════════════
FILMS = {
    "plant": (render_plant,  "g01_plant_15s_1080x1920.mp4",    plant_audio),
    "land":  (render_land,   "g02_land_15s_1080x1920.mp4",     land_audio),
    "song":  (render_song,   "g03_song_15s_1080x1920.mp4",     song_audio),
    "plate": (render_plate,  "g04_plate_15s_1080x1920.mp4",    plate_audio),
    "wake_close":  (render_wake,   "g05_wake_close_15s_1080x1920.mp4", wake_audio),
    "sleep_sink": (render_sleep2, "g06_sleep_sink_15s_1080x1920.mp4", sleep2_audio),
    "day":   (render_day,    "g07_day_15s_1080x1920.mp4",      day_audio),
}

# 音が増える時刻。**画面で鳥が増える/鳴き始める時刻に合わせる。**
STARTS = {
    "plant": [at for _b, at in PLANT_BIRDS],
    "land":  [1.0, 3.0, LAND_SWAP],          # 3本目 = 京都の鳥。切替と同時
    "song":  [at for _b, _n, at, _d in SONG_CAST],
    "plate": [0.8, 6.0],
    "wake_close":  [at for _b, at in WAKE_JOIN],
    "sleep_sink": [0.5, 1.5, 2.5],
    "day":   [1.6, 3.0, 4.4],
}

# バッチ3の道具をそのまま使う(札・字幕帯・CTA・2パスの音量合わせ)。
F.FILMS.update(FILMS)
F.STARTS.update(STARTS)


if __name__ == "__main__":
    args = sys.argv[1:]
    remux = "--remux" in args
    want = [a for a in args if not a.startswith("-")] or list(FILMS)
    for k in want:
        if k not in FILMS:
            raise SystemExit(f"知らない題目: {k} / 使えるのは {list(FILMS)}")
        print(f"[{k}]")
        F.build(k, remux=remux)
