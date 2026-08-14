"""37種ぶんの鳴き声を xeno-canto から集め、アプリに同梱できる形にする。

## なぜ必要か
現行版は再生のたびに xeno-canto から取ってくる(`xc_client.py`)。Flutter 版は
**端末内で完結させたい**(サーバーを無くすのが移行の狙いのひとつ。現行は Render の
コールドスタート実測22.7秒)。そのため、事前に集めて APK に同梱する。

集めた音は `tools/bird_audio_prep.py` と同じ処理を通す:
  暗騒音の除去(afftdn) → 音量を -19 LUFS に統一(loudnorm) → ステレオ化
これで**実時間のノイズゲートと AGC が要らなくなる**(移行の最大の壁だった処理)。
ステレオにするのは、残響(SoLoud の freeverb)がモノラルに使えないため。

## ライセンスの扱い(2026-08-13 CEO 判断)
**NC(非商用)の録音も使う。** いまは広告を入れておらず商用ではないため。
ただし将来広告を入れる時に困らないよう、次の2つを必ず守る:
  1. **1件ずつライセンスと出典を `_credits.json` に残す**(後から差し替える対象が
     一覧で分かるようにする)
  2. **同じ品質なら配布可(CC0/BY/BY-SA)のものを優先して選ぶ**
     — 追加コストはゼロで、将来の差し替え量が減る

    py -3 tools/bird_audio_collect.py            # 何が取れるか調べるだけ
    py -3 tools/bird_audio_collect.py --download # 実際に取得して加工する
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))
sys.path.insert(0, os.path.dirname(__file__))

import xc_client  # noqa: E402
import bird_audio_prep as prep  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "..",
                       "toris_app", "assets", "birds")

# 探す順番。さえずり優先(目覚ましと同じ理由で、耳障りな地鳴きは後回し)。
# 品質は xeno-canto の評価。A が最良。
SEARCH_ORDER = [("song", "A"), ("song", "B"), ("call", "A"), ("call", "B")]

# 学名が変わった種の別名。シードデータ(data.py)の学名で引けなかったときに使う。
# 分類は改訂されるので、録音が0件のときは**まず学名を疑う**。
# 2026-08-14: コゲラが 0件だったが、`Yungipicus kizuki` では31件あった。
SYNONYMS = {
    "Dendrocopos kizuki": "Yungipicus kizuki",
}


def species_list() -> list[tuple[str, str, str]]:
    """(id, 英名, 学名) の一覧をシードデータから作る。"""
    import data
    birds = getattr(data, "BIRDS")
    if isinstance(birds, dict):
        return [(k, v.get("english") or v.get("name"), v.get("scientific"))
                for k, v in birds.items()]
    return [(b.get("id"), b.get("english") or b.get("name"), b.get("scientific"))
            for b in birds]


def pick(recs: list[dict]) -> dict | None:
    """使う1件を選ぶ。**同じ条件なら配布可のものを優先**する。

    `file` が空の録音は飛ばす。xeno-canto には録音者がダウンロードを
    許可していないものがあり、そういう録音の `url` は**音声ではなく
    録音ページ(HTML)**を指す。気づかずに落とすと「音声として読めない mp3」が
    出来上がる(2026-08-14 にイカルで実際に発生)。
    """
    recs = [r for r in (recs or []) if r.get("file")]
    if not recs:
        return None
    def score(r):
        lic = xc_client.license_class(r.get("lic") or "")
        # 配布可を先に、次に長さが手ごろなもの(短すぎる録音はループが不自然)
        try:
            sec = float(str(r.get("length", "0:00")).split(":")[-1]) + \
                  60 * float(str(r.get("length", "0:00")).split(":")[0])
        except Exception:
            sec = 0
        return (0 if lic == "commercial" else 1, abs(sec - 25))
    return sorted(recs, key=score)[0]


def find_for(sci: str) -> tuple[dict | None, str, str]:
    for name in (sci, SYNONYMS.get(sci)):
        if not name:
            continue
        for sound_type, q in SEARCH_ORDER:
            recs = xc_client.search_recordings(name, quality=q, sound_type=sound_type)
            best = pick(recs)
            if best:
                return best, sound_type, q
    return None, "", ""


def audio_url(rec: dict) -> str | None:
    """音声そのものの URL。`url` は録音ページ(HTML)なので**使わない**。"""
    v = rec.get("file")
    if not v:
        return None
    return ("https:" + v) if str(v).startswith("//") else str(v)


def main() -> None:
    if not xc_client.is_enabled():
        raise SystemExit("xeno-canto の API キーが未設定"
                         "(toris_collection/xc_api_key.txt)")
    download = "--download" in sys.argv
    if download:
        os.makedirs(OUT_DIR, exist_ok=True)

    credits, missing, nc_count = [], [], 0
    for bid, en, sci in species_list():
        rec, stype, q = find_for(sci)
        if not rec:
            missing.append(f"{en} ({sci})")
            print(f"  [--] {en:<28} 録音が見つからない")
            continue
        lic = rec.get("lic") or ""
        klass = xc_client.license_class(lic)
        if klass == "noncommercial":
            nc_count += 1
        mark = "商用可" if klass == "commercial" else ("NC" if klass == "noncommercial" else "?")
        print(f"  [{mark:<4}] {en:<28} {stype}/q{q}  {rec.get('length','?')}  "
              f"XC{rec.get('id')} by {rec.get('rec','?')[:18]}")

        entry = {
            "id": bid, "english": en, "scientific": sci,
            "xc_id": rec.get("id"), "recordist": rec.get("rec"),
            "license": ("https:" + lic) if str(lic).startswith("//") else lic,
            "license_class": klass,
            "url": f"https://xeno-canto.org/{rec.get('id')}",
            "type": stype, "quality": q,
        }
        if not download:
            credits.append(entry)
            continue

        url = audio_url(rec)
        if not url:
            missing.append(f"{en}(音声URLなし)")
            continue
        raw = os.path.join(OUT_DIR, f"{bid}.raw.mp3")
        dest = os.path.join(OUT_DIR, f"{bid}.mp3")
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "TorisCollection/0.1"})
            with urllib.request.urlopen(req, timeout=90) as r:
                open(raw, "wb").write(r.read())
        except Exception as e:
            print(f"        DL失敗: {type(e).__name__}: {e}")
            missing.append(f"{en}(DL失敗)")
            continue
        # 加工に失敗したものを黙って通さない。xeno-canto がエラーページを
        # 返すことがあり、そのまま置くと「音声として読めない mp3」が残る
        # (2026-08-14 に実際に1種で発生)。
        if not prep.prepare(raw, dest, stereo=True):
            print("        加工できなかったので採用しない")
            for x in (raw, dest):
                if os.path.exists(x):
                    os.remove(x)
            missing.append(f"{en}(加工失敗)")
            continue
        os.remove(raw)
        entry["bytes"] = os.path.getsize(dest)
        credits.append(entry)

    print(f"\n見つかった: {len(credits)}種 / 見つからない: {len(missing)}種")
    print(f"うち NC(非商用): {nc_count}種  ← 広告を入れる時に差し替える対象")
    for m in missing:
        print(f"   欠け: {m}")

    if credits:
        p = os.path.join(OUT_DIR if download else os.path.dirname(__file__),
                         "_credits.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=1)
        print(f"\ncredits: {os.path.abspath(p)}")
    if not download:
        print("(調べただけ。取得するには --download を付ける)")


if __name__ == "__main__":
    main()
