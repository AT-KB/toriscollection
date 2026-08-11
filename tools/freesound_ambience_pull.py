"""環境音タイル用の素材を Freesound から取ってくる(CC0 のみ)。

## なぜ必要か
環境音タイル(雨・風・小川…)は当初ブラウザ内で合成していたが、参考にした
Bird Sounds が**実際の録音**を使っているのに対し、合成音は情報量が乏しく
「オン/オフで実感できない」という指摘を受けた(CEO 2026-08-11)。音量では埋まらない
質の差なので、本物の録音に置き換える。

## ライセンスの条件(妥協しない)
アプリは広告つき = 商用。**CC0 のものだけ**を取る。
Freesound には CC BY / CC BY-NC も多いが:
  - BY-NC は商用不可なので**使えない**
  - BY は使えるが、環境音は差し替えが頻繁で帰属表示の管理が煩雑になる
そこで CC0 に限定する。取得した音の出典は `_credits.json` に残す
(CC0 は表示義務が無いが、どこから来た音かを追えるようにしておく)。

## 使い方
  1. https://freesound.org/apiv2/apply で無料登録し、API キーを取得
  2. toris_collection/freesound_api_key.txt にキーだけ1行で保存
  3. py -3 tools/freesound_ambience_pull.py          # 候補を表示するだけ
     py -3 tools/freesound_ambience_pull.py --download
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import freesound_client as fs   # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "..",
                       "toris_collection", "static", "ambience")

# タイルのキー -> 検索語。ループしやすく、耳につかないものを狙う。
LAYERS = {
    "rain":   "rain on leaves loop ambient",
    "wind":   "gentle wind trees loop ambient",
    "stream": "small stream water loop ambient",
    "chime":  "wind chimes gentle",
}

# 長すぎる素材はアプリが重くなるので、この範囲のものから選ぶ(秒)
DUR_MIN, DUR_MAX = 20, 120


def search(query: str) -> list[dict]:
    """CC0 に限定して検索する。"""
    params = {
        "query": query,
        # ライセンスを CC0 に固定。ここを緩めると商用で使えない音が混ざる。
        "filter": f'license:"Creative Commons 0" duration:[{DUR_MIN} TO {DUR_MAX}]',
        "sort": "rating_desc",
        "fields": "id,name,duration,license,username,previews,avg_rating,num_ratings",
        "page_size": 8,
    }
    url = f"{fs.FS_API_BASE}/search/text/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Token {fs._KEY}",
        "User-Agent": "TorisCollection/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("results", [])
    except Exception as e:
        print(f"  検索失敗 [{query}]: {type(e).__name__}: {e}")
        return []


def main():
    if not fs.is_enabled():
        raise SystemExit(
            "Freesound の API キーが未設定。\n"
            "  1. https://freesound.org/apiv2/apply で登録(無料)\n"
            "  2. toris_collection/freesound_api_key.txt にキーだけ1行で保存\n"
            "  3. もう一度このコマンドを実行"
        )

    download = "--download" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    credits = []

    for key, query in LAYERS.items():
        print(f"\n=== {key} ({query}) ===")
        hits = search(query)
        if not hits:
            print("  CC0 の候補が見つからなかった")
            continue
        for h in hits[:5]:
            print(f"  [{h['id']:>9}] ★{h.get('avg_rating', 0):.1f}"
                  f"({h.get('num_ratings', 0):>3})  {h['duration']:>5.1f}s  "
                  f"{h['name'][:48]}")
        best = hits[0]
        if not download:
            continue

        # プレビュー(mp3)を取る。元ファイルはライセンス上は同じだが容量が大きい。
        url = (best.get("previews") or {}).get("preview-hq-mp3")
        if not url:
            print("  プレビューURLが無いので飛ばす")
            continue
        dest = os.path.join(OUT_DIR, f"amb_{key}.mp3")
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Token {fs._KEY}",
                "User-Agent": "TorisCollection/0.1",
            })
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"  DL失敗: {type(e).__name__}: {e}")
            continue
        print(f"  saved: {os.path.basename(dest)} ({len(data)//1024}KB)")
        credits.append({
            "layer": key, "freesound_id": best["id"], "name": best["name"],
            "user": best.get("username"), "license": best.get("license"),
            "url": f"https://freesound.org/s/{best['id']}/",
        })

    if download and credits:
        p = os.path.join(OUT_DIR, "_credits.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=1)
        print(f"\ncredits: {os.path.abspath(p)}")
    elif not download:
        print("\n(表示のみ。実際に取得するには --download を付ける)")


if __name__ == "__main__":
    main()
