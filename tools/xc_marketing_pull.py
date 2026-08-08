"""SNS動画に使える(=商用利用できる)鳥の声を xeno-canto から集める。

**なぜ専用ツールが要るか**: アプリ内で鳴らしているキャッシュ
(`toris_collection/.xeno_canto_cache/`)の録音は **NC(非商用)/ND(改変禁止)が大半**で、
マーケティング動画には使えない。`landing/media/radio_src/` は CC0 / CC BY / CC BY-SA
だけを手で選んだ「配布して良い音源プール」であり、動画はここからだけ音を取る。

このツールは xc_client.license_class() の判定(= commercial のみ)を使って、
図鑑の詳細ドット絵がある種の中から使える録音を探し、radio_src に追加して
クレジット(all_credit.json)を更新する。

実行: py -3 tools/xc_marketing_pull.py            # 候補を表示するだけ(取得しない)
      py -3 tools/xc_marketing_pull.py --download # 実際に取得して credit を更新
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import xc_client as xc          # noqa: E402
import species_loader as sl     # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "toris_collection", "designbird")
POOL = os.path.join(ROOT, "landing", "media", "radio_src")
CREDIT = os.path.join(POOL, "all_credit.json")

# 動画は「その鳥だと分かる声」が要る。song を優先し、無ければ call。
TYPE_ORDER = ["song", "call"]
QUALITY_ORDER = ["A", "B", "C"]


def sprite_birds():
    """詳細ドット絵がある鳥だけが動画の主役になれる。"""
    have = {f[: -len("_detail.png")] for f in os.listdir(DB)
            if f.endswith("_detail.png")}
    return {bid: b for bid, b in sl.BIRDS.items() if bid in have}


def best_usable(sci: str):
    """商用利用できる録音のうち、いちばん良いものを1件返す。無ければ None。"""
    for q in QUALITY_ORDER:
        for stype in TYPE_ORDER:
            for r in xc.search_recordings(sci, quality=q, sound_type=stype) or []:
                if xc.license_class(r.get("lic") or "") == "commercial":
                    return {**r, "_q": q, "_type": stype}
    return None


def load_credits():
    if not os.path.exists(CREDIT):
        return []
    with open(CREDIT, encoding="utf-8") as f:
        return json.load(f)


def main():
    download = "--download" in sys.argv
    credits = load_credits()
    have_sci = {c.get("sci") for c in credits}

    birds = sprite_birds()
    print(f"詳細ドット絵のある鳥: {len(birds)} 種 / うち音源プール既存: "
          f"{len([b for b in birds.values() if b.get('scientific') in have_sci])} 種\n")

    added = 0
    for bid, b in sorted(birds.items()):
        sci = (b.get("scientific") or "").strip()
        if not sci:
            continue
        if sci in have_sci:
            print(f"{bid:26s} skip(既にプールにある)")
            continue
        rec = best_usable(sci)
        if not rec:
            print(f"{bid:26s} -- 商用利用できる録音なし")
            continue

        lic = rec.get("lic") or ""
        name = (b.get("english") or bid).replace(" ", "_").replace("-", "_")
        dest = os.path.join(POOL, f"{name}.mp3")
        print(f"{bid:26s} OK q={rec['_q']} {rec['_type']:5s} {rec.get('rec')} "
              f"[{lic.split('creativecommons.org')[-1]}]")

        if not download:
            continue
        url = rec.get("file")
        if not url:
            print("      file URL が無いので飛ばす")
            continue
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "TorisCollection/0.1"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if len(data) < 2000:
                print("      ダウンロードが小さすぎる(壊れている?)ので飛ばす")
                continue
            with open(dest, "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"      DL失敗: {type(e).__name__}: {e}")
            continue

        credits.append({
            "file": dest,
            "en": rec.get("en") or b.get("english"),
            "sci": sci,
            "xc_id": rec.get("id"),
            "rec": rec.get("rec"),
            "lic": lic if lic.startswith("http") else "https:" + lic,
            "url": rec.get("url"),
        })
        added += 1
        print(f"      saved: {os.path.basename(dest)}")

    if download and added:
        with open(CREDIT, "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=1)
        print(f"\ncredit 更新: +{added} 件 -> {CREDIT}")
    elif not download:
        print("\n(表示のみ。実際に取得するには --download を付ける)")


if __name__ == "__main__":
    main()
