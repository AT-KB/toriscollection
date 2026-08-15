"""鳥の鳴き声を**別の録音に取り替える**。

## なぜ要るか(2026-08-15 CEO)
自動で選んだ1件が、その種の「らしさ」を捉えていないことがある。環境音でも
同じことが起き(風がガサガサ・波が波打ち際でない)、ID を書き換えて直した。
鳥にも同じ手を用意する。

**詳細絵(ドット絵)がある種を対象にする。** その24種が図鑑で大きく出る＝
顔になる種で、声の当たり外れがいちばん効く。

## 使い方
    py -3 tools/bird_audio_swap.py                      # 対象の種と、いまの音を一覧
    py -3 tools/bird_audio_swap.py <bird_id>            # その種の候補を出す
    py -3 tools/bird_audio_swap.py <bird_id> <XC番号>    # その録音に取り替える

取り替えると `_credits.json` の出典も一緒に書き換わる(ライセンスの追跡は切らさない)。
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))
sys.path.insert(0, os.path.dirname(__file__))

import xc_client  # noqa: E402
import bird_audio_prep as prep  # noqa: E402

APP = os.path.join(os.path.dirname(__file__), "..", "toris_app")
BIRD_DIR = os.path.join(APP, "assets", "birds")
SPRITE_DIR = os.path.join(APP, "assets", "sprites")
CREDITS = os.path.join(BIRD_DIR, "_credits.json")


def detail_ids() -> set:
    """詳細絵がある種(＝図鑑の顔になる種)。"""
    if not os.path.isdir(SPRITE_DIR):
        return set()
    return {f[:-len("_detail.png")] for f in os.listdir(SPRITE_DIR)
            if f.endswith("_detail.png")}


def load_credits() -> list:
    return json.load(open(CREDITS, encoding="utf-8"))


def save_credits(rows: list) -> None:
    with open(CREDITS, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


def list_targets() -> None:
    rows = {r["id"]: r for r in load_credits()}
    ids = sorted(detail_ids() & set(rows))
    print(f"詳細絵がある種: {len(ids)}(取り替えの対象)\n")
    for bid in ids:
        r = rows[bid]
        mark = "商用可" if r.get("license_class") == "commercial" else "NC"
        print(f"  {bid:<26} {r.get('english', ''):<24} "
              f"XC{r.get('xc_id')} {r.get('type', '?')}/q{r.get('quality', '?')} "
              f"[{mark}] by {str(r.get('recordist'))[:18]}")
    print("\n候補を見る: py -3 tools/bird_audio_swap.py <bird_id>")


def show_candidates(bid: str) -> None:
    rows = {r["id"]: r for r in load_credits()}
    if bid not in rows:
        raise SystemExit(f"{bid} は音源一覧に無い")
    sci = rows[bid]["scientific"]
    cur = rows[bid].get("xc_id")
    print(f"{rows[bid].get('english')} ({sci})  いま: XC{cur}\n")
    seen = set()
    for stype in ("song", "call"):
        for q in ("A", "B"):
            for r in xc_client.search_recordings(sci, quality=q, sound_type=stype):
                if not r.get("file") or r["id"] in seen:
                    continue
                seen.add(r["id"])
                lic = xc_client.license_class(r.get("lic") or "")
                mark = "商用可" if lic == "commercial" else "NC"
                here = " ← いまこれ" if str(r["id"]) == str(cur) else ""
                print(f"  XC{r['id']:<9} {stype}/q{q} {r.get('length', '?'):>6} "
                      f"[{mark}] {str(r.get('rec'))[:20]:<20} {r.get('cnt', '')}{here}")
    print(f"\n取り替える: py -3 tools/bird_audio_swap.py {bid} <XC番号>")


def swap(bid: str, xc_id: str) -> None:
    rows = load_credits()
    idx = next((i for i, r in enumerate(rows) if r["id"] == bid), None)
    if idx is None:
        raise SystemExit(f"{bid} は音源一覧に無い")
    sci = rows[idx]["scientific"]

    rec = None
    for stype in ("song", "call"):
        for q in ("A", "B", "C"):
            for r in xc_client.search_recordings(sci, quality=q, sound_type=stype):
                if str(r.get("id")) == str(xc_id) and r.get("file"):
                    rec = (r, stype, q)
                    break
            if rec:
                break
        if rec:
            break
    if not rec:
        raise SystemExit(f"XC{xc_id} が {sci} の候補に見つからない"
                         "(ダウンロード不可の録音かもしれない)")

    r, stype, q = rec
    url = r["file"]
    url = ("https:" + url) if url.startswith("//") else url
    raw = os.path.join(BIRD_DIR, f"{bid}.raw.mp3")
    dest = os.path.join(BIRD_DIR, f"{bid}.mp3")
    print(f"取得中: XC{xc_id} ({stype}/q{q}) …")
    req = urllib.request.Request(url, headers={"User-Agent": "TorisCollection/0.1"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        open(raw, "wb").write(resp.read())

    # 他の音と同じ工程を通す(暗騒音の除去 → 音量を揃える → ステレオ)。
    # ここを飛ばすと1羽だけ音量や質が浮く。
    if not prep.prepare(raw, dest, stereo=True):
        os.remove(raw)
        raise SystemExit("加工に失敗した。取り替えていない。")
    os.remove(raw)
    after = prep.retarget(dest)

    lic = r.get("lic") or ""
    rows[idx].update({
        "xc_id": r.get("id"),
        "recordist": r.get("rec"),
        "license": ("https:" + lic) if str(lic).startswith("//") else lic,
        "license_class": xc_client.license_class(lic),
        "url": f"https://xeno-canto.org/{r.get('id')}",
        "type": stype,
        "quality": q,
        "bytes": os.path.getsize(dest),
    })
    save_credits(rows)
    print(f"取り替えた: {bid} → XC{xc_id}  ({after:.1f} LUFS, "
          f"{os.path.getsize(dest) // 1024}KB)")
    print("アプリに反映するには再ビルドが要る。")


def main() -> None:
    if not xc_client.is_enabled():
        raise SystemExit("xeno-canto の API キーが未設定")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        list_targets()
    elif len(args) == 1:
        show_candidates(args[0])
    else:
        swap(args[0], args[1])


if __name__ == "__main__":
    main()
