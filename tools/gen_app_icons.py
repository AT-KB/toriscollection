"""アプリのアイコンを `素材/ヘッダー.png`(9羽のドット絵)から作る。

CEO 2026-08-21「素材のところに入れたアイコンにしてほしい、ヘッダーってやつ」。

## **丸で統一する**(CEO 2026-08-21「まとめて丸にして」)
端末のアダプティブアイコンはどのみち丸や角丸に切り抜かれる。保証されるのは
中央 66% だけで、元絵をそのまま敷くと**四隅の3羽が欠ける**。
そこで**どの出力でも、白い円の中に9羽を収める**形に揃える。
ストア用も同じ見た目にして、端末と食い違わないようにする。

地色は**白**にする。元絵の背景が白で、縮めたときに継ぎ目が出ないため
(セージ地に置くと、白い四角が浮いて見える)。3行目に白い鳥が居るので、
白を透過に抜く手は使えない。

    py -3 tools/gen_app_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "marketing" / "phase-1" / "SNS部" / "素材" / "ヘッダー.png"
RES = ROOT / "toris_app" / "android" / "app" / "src" / "main" / "res"
STORE = ROOT / "marketing" / "phase-1" / "SNS部" / "素材" / "store" / "app_icon_512.png"

WHITE = (255, 255, 255)

# 端末密度ごとの一辺(px)。legacy=48dp / adaptive foreground=108dp。
LEGACY = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
FOREGROUND = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324,
              "xxxhdpi": 432}

# アダプティブアイコンで**必ず残る**中央の割合(72dp / 108dp)。
SAFE = 72 / 108

# 円の外の地色(ストア用。Play は透過を弾く)。ランチャーの背景と同じセージ。
SAGE = (0xEC, 0xF1, 0xE3)


def _disc(src: Image.Image, size: int, outside=None) -> Image.Image:
    """白い円の中に元絵を収めた画像。円の外は `outside`(既定は透過)。"""
    inner = max(1, round(size * SAFE))
    disc = Image.new("RGB", (size, size), WHITE)
    off = (size - inner) // 2
    disc.paste(src.resize((inner, inner), Image.NEAREST), (off, off))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)

    base = (0, 0, 0, 0) if outside is None else outside + (255,)
    out = Image.new("RGBA", (size, size), base)
    out.paste(disc, (0, 0), mask)
    return out


def main() -> None:
    src = Image.open(SRC).convert("RGB")

    # ── ストア用 ──
    # Play は**透過を弾く**ので、円の外はセージ地(ランチャーの地色と同じ)。
    STORE.parent.mkdir(parents=True, exist_ok=True)
    store = _disc(src, 512, outside=SAGE).convert("RGB")
    store.save(STORE)
    print(f"store  {STORE.name} 512x512 (丸・透過なし)")

    for dens, size in LEGACY.items():
        d = RES / f"mipmap-{dens}"
        d.mkdir(parents=True, exist_ok=True)
        # 旧式のアイコンも**丸**にする。円の外は透過。
        disc = _disc(src, size)
        disc.save(d / "ic_launcher.png")
        disc.save(d / "ic_launcher_round.png")

    for dens, size in FOREGROUND.items():
        d = RES / f"mipmap-{dens}"
        inner = max(1, round(size * SAFE))
        fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        off = (size - inner) // 2
        fg.paste(src.resize((inner, inner), Image.NEAREST), (off, off))
        fg.save(d / "ic_launcher_foreground.png")
    print("launcher: legacy / round / foreground を 5 密度ぶん更新した")


if __name__ == "__main__":
    main()
