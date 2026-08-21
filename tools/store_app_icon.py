"""Google Play の「アプリアイコン」(512x512・掲載に必須)を作る。

ストアの一覧や DL 画面に出るのはこれ。**端末のランチャーアイコンとは別物**で、
Console で差し替えれば**アプリを更新しなくても反映される**。

⚠️ Play は **32bit PNG・512x512・透過なし**を求める。
   `toris_collection/static/icons/icon-512.png` は PWA 用で背景が透明なので、
   ランチャーと同じセージ地(#ecf1e3)に載せてから出す。

    py -3 tools/store_app_icon.py
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "toris_collection" / "static" / "icons" / "icon-512.png"
OUT = ROOT / "marketing" / "phase-1" / "SNS部" / "素材" / "store" / "app_icon_512.png"

# ランチャーアイコンの背景と同じ値(res/values/ic_launcher_background.xml)
SAGE = (0xEC, 0xF1, 0xE3)


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    if src.size != (512, 512):
        src = src.resize((512, 512), Image.NEAREST)  # ドット絵なので補間しない

    out = Image.new("RGB", (512, 512), SAGE)
    out.paste(src, (0, 0), src)                      # 透明部分がセージで埋まる

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT)
    print(f"{OUT}  {out.size}  {out.mode}  透過なし")


if __name__ == "__main__":
    main()
