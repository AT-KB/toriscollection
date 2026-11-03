"""X 投稿キット用の画像(4:5 = 1080x1350)を作る。実機のスクショとアプリのドット絵だけを使う。"""
import json, os
from PIL import Image, ImageDraw, ImageFont, ImageOps

SCR = r'C:\Users\kubok\AppData\Local\Temp\claude\C--Users-kubok-OneDrive-Desktop-Agent\9ee9d38c-e631-40df-b3ba-9079e14a1b4f\scratchpad'
APP = r'C:\Users\kubok\OneDrive\Desktop\Agent\toriscollection\toris_app'
OUT = r'C:\Users\kubok\OneDrive\Desktop\Agent\toriscollection\marketing\phase-1\SNS部\素材\x'
os.makedirs(OUT, exist_ok=True)

W, H = 1080, 1350
BG = (238, 243, 230)        # アプリの背景に寄せた淡い緑
INK = (35, 51, 31)
SUB = (93, 107, 87)
LEAF = (58, 107, 62)
BOLD = r'C:\Windows\Fonts\YuGothB.ttc'
MED = r'C:\Windows\Fonts\YuGothM.ttc'

def font(path, size):
    return ImageFont.truetype(path, size)

def canvas(title, sub=None):
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((W // 2, 92), title, font=font(BOLD, 58), fill=INK, anchor='mm')
    if sub:
        d.text((W // 2, 160), sub, font=font(MED, 32), fill=SUB, anchor='mm')
    return im, d

def rounded(img, r=36):
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), r, fill=255)
    out = Image.new('RGBA', img.size)
    out.paste(img, (0, 0), mask)
    return out

def place_shot(im, shot, box, top):
    """box = 元画像での切り抜き (x0,y0,x1,y1)。top から下の余白にぴったり収める。"""
    crop = Image.open(shot).convert('RGB').crop(box)
    max_w, max_h = W - 120, H - top - 50
    s = min(max_w / crop.width, max_h / crop.height)
    crop = crop.resize((int(crop.width * s), int(crop.height * s)), Image.LANCZOS)
    card = rounded(crop)
    # 薄い影
    shadow = Image.new('RGBA', (card.width + 24, card.height + 24), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((12, 16, card.width + 12, card.height + 16), 36, fill=(0, 0, 0, 38))
    x = (W - card.width) // 2
    im.paste(shadow, (x - 12, top - 12), shadow)
    im.paste(card, (x, top), card)
    return x, top, card.width, card.height

def sprite(bid, size):
    sp = Image.open(os.path.join(APP, 'assets', 'sprites', bid + '.png')).convert('RGBA')
    bb = sp.getbbox()
    sp = sp.crop(bb)
    s = size / max(sp.size)
    return sp.resize((max(1, int(sp.width * s)), max(1, int(sp.height * s))), Image.NEAREST)

birds = json.load(open(os.path.join(APP, 'assets', 'data', 'birds.json'), encoding='utf-8'))

# ① 固定ポスト: 日本語の庭(鳥が2羽いる回)
im, d = canvas('植える → 虫が来る → 鳥が来る', '小さな生態系を育てる、鳥の庭')
place_shot(im, os.path.join(SCR, 'x2.png'), (0, 110, 1080, 1620), 210)
im.save(os.path.join(OUT, '01_固定ポスト.png'))

# ② 鳴き声クイズ: シジュウカラのドット絵をシルエットにする
im, d = canvas('この声、だれでしょう?', '日本の庭でもよく聞く鳥です')
sp = sprite('shijukara', 520)
sil = Image.new('RGBA', sp.size, INK + (255,))
sil.putalpha(sp.getchannel('A').point(lambda a: 255 if a > 40 else 0))
im.paste(sil, ((W - sp.width) // 2, 330), sil)
d.text((W // 2, 1080), '?', font=font(BOLD, 200), fill=LEAF, anchor='mm')
d.text((W // 2, 1265), '答えは明日、リプ欄で', font=font(MED, 34), fill=SUB, anchor='mm')
im.save(os.path.join(OUT, '02_鳴き声クイズ.png'))
# 答え合わせ用(翌日のリプに)
im, d = canvas('答えは「シジュウカラ」', '京都の庭に来てくれます')
sp = sprite('shijukara', 520)
im.paste(sp, ((W - sp.width) // 2, 330), sp)
d.text((W // 2, 1150), 'Parus minor', font=font(MED, 40), fill=SUB, anchor='mm')
d.text((W // 2, 1265), '録音: Peter Boesman / xeno-canto XC285681', font=font(MED, 28), fill=SUB, anchor='mm')
im.save(os.path.join(OUT, '02b_鳴き声クイズ_答え.png'))

# ③ 寝落ち: 焚き火を選んだラジオ
im, d = canvas('焚き火と、ときどき鳥の声', '15〜90分で止まる「寝落ち」つき')
place_shot(im, os.path.join(SCR, 'shots', 'radio_fire.png'), (0, 1080, 1080, 2010), 230)
im.save(os.path.join(OUT, '03_寝落ち.png'))

# ④ 目覚まし(通知の警告より上だけ)
im, d = canvas('鳥のさえずりで起きる', '小さな音から、少しずつ大きく')
place_shot(im, os.path.join(SCR, 'shots', 'alarm.png'), (0, 110, 1080, 1420), 230)
im.save(os.path.join(OUT, '04_目覚まし.png'))

# ⑤ 京都の庭 / シャーロットの庭(アプリのドット絵)
im, d = canvas('来る鳥は、土地で変わる', 'アプリに出てくる鳥たち(ドット絵)')
groups = [
    ('京都の庭', ['mejiro', 'shijukara', 'enaga', 'kawasemi', 'kibitaki', 'uguisu']),
    ('シャーロットの庭', ['northern_cardinal', 'eastern_bluebird', 'blue_jay',
                     'american_goldfinch', 'tufted_titmouse', 'carolina_wren']),
]
y = 240
for label, ids in groups:
    d.rounded_rectangle((60, y, W - 60, y + 520), 32, fill=(255, 255, 255))
    d.text((100, y + 50), label, font=font(BOLD, 40), fill=LEAF, anchor='lm')
    for i, bid in enumerate(ids):
        cx = 60 + (W - 120) * (i % 3 * 2 + 1) // 6
        cy = y + 175 + (i // 3) * 190
        sp = sprite(bid, 112)
        im.paste(sp, (cx - sp.width // 2, cy - sp.height // 2 - 10), sp)
        d.text((cx, cy + 72), birds[bid]['name'], font=font(MED, 26), fill=INK, anchor='mm')
    y += 560
im.save(os.path.join(OUT, '05_京都の庭.png'))

# ⑥ つながり
im, d = canvas('植物・虫・鳥のつながり', '実際の観察記録(GloBI)から')
place_shot(im, os.path.join(SCR, 'shots', 'network.png'), (0, 480, 1080, 1720), 230)
im.save(os.path.join(OUT, '06_つながり.png'))

# ⑦ 開発ログ: 1羽ずつ動く4コマ
im, d = canvas('1羽ずつ、それぞれのテンポで', '「耳を澄ます」の鳥の動き(実機)')
frames = [('f01', '0.0秒'), ('f02', '0.4秒 青い鳥'), ('f05', '1.5秒 赤い鳥'), ('f08', '2.7秒 青い鳥')]
cw, ch = 470, 470
for i, (f, lab) in enumerate(frames):
    fr = Image.open(os.path.join(SCR, 'frames', f + '.png')).convert('RGB').crop((40, 300, 1040, 1010))
    fr = ImageOps.fit(fr, (cw, ch - 60), Image.LANCZOS)
    x = 60 + (i % 2) * (cw + 20)
    yy = 230 + (i // 2) * (ch + 30)
    im.paste(rounded(fr, 24), (x, yy), rounded(fr, 24))
    d.text((x + cw // 2, yy + ch - 25), lab, font=font(MED, 30), fill=INK, anchor='mm')
im.save(os.path.join(OUT, '07_開発ログ.png'))

# ⑧ 日本語に対応: 英語と日本語を並べる
im, d = canvas('日本語に対応しました', '鳥・虫・植物の名前も和名で')
for i, (shot, lab) in enumerate([('x1.png', 'English'), ('x2.png', '日本語')]):
    crop = Image.open(os.path.join(SCR, shot)).convert('RGB').crop((0, 110, 1080, 1620))
    s = 470 / crop.width
    crop = crop.resize((470, int(crop.height * s)), Image.LANCZOS)
    x = 60 + i * 490
    im.paste(rounded(crop, 24), (x, 250), rounded(crop, 24))
    d.text((x + 235, 250 + crop.height + 45), lab, font=font(BOLD, 36), fill=LEAF, anchor='mm')
im.save(os.path.join(OUT, '08_日本語に対応.png'))

print('\n'.join(sorted(os.listdir(OUT))))
