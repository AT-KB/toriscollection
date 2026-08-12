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
ダウンロード時にも1件ずつライセンスを検証し、CC0 以外は落とさない。

## なぜ検索結果の1位を自動採用しないのか(2026-08-11)
Freesound のテキスト検索は語の AND 検索ではなく、関連度で並べるだけである。
実際 `rain loop` の1位は "30-Second Upbeat Background Loop"(音楽)、
`waves loop` の上位は Piano loops だった。**機械が選ぶと音楽が混ざる。**
そこで検索は候補出し(`--search`)に使い、採用は下の `PICKS` に ID で固定する。
差し替えるときも、ここの ID を書き換えれば同じ音が再現できる。

## 使い方
  1. https://freesound.org/apiv2/apply で無料登録し、API キーを取得
  2. toris_collection/freesound_api_key.txt にキーだけ1行で保存
  3. py -3 tools/freesound_ambience_pull.py            # PICKS の素性を表示
     py -3 tools/freesound_ambience_pull.py --download # 実際に取得
     py -3 tools/freesound_ambience_pull.py --search   # 差し替え候補を探す
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import freesound_client as fs   # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "..",
                       "toris_collection", "static", "ambience")

# ── 採用する音(Freesound の ID で固定)────────────────────────────────
# 2026-08-11(CEO): **自然音のみ**。動物・虫・楽器は入れない。
# 参考にした Bird Sounds は Cricket / Frog / Guitar 等も並べているが、本アプリは
# 鳥の声そのものが主役なので、環境音に生き物を混ぜると主役がぼやける。
# 同じ理由で、鳥や虫が入っている録音は候補から外している
# (例: 482255 "Wind_Tree_Forest_Summer" は説明に Bees, Birds とあるため不採用)。
PICKS = {
    # 雨: イギリスで録った小雨。「気を散らす雫を取り除き、継ぎ目なくループ化した」と
    #     作者が明記している。雷・その他の物音が入っていない。
    "rain":   595717,
    # 風: 木の葉が風に鳴る音(Point Pleasant Park)。★5.0/42件と評価が高く、
    #     鳥や虫が入らない。「強風」の録音は庭の穏やかさに合わないので採らない。
    "wind":   378725,
    # 小川: Nox_Sound のループ素材。小さな流れで、川というより庭先の水音に近い。
    "stream": 548373,
    # 波: 岸に寄せる穏やかな水音。作者がループ化済み。砕ける波(crashing)の録音は
    #     音が強すぎて鳥の声を潰すので採らない。
    "waves":  260263,
}

# `--search` で候補を出すときの検索語(採用そのものには使わない)
SEARCH_QUERIES = {
    "rain":   "rain",
    "wind":   "forest wind rustling leaves",
    "stream": "small stream water loop ambient",
    "waves":  "waves shore",
}

# 長すぎる素材はアプリが重くなるので、この範囲のものから選ぶ(秒)
DUR_MIN, DUR_MAX = 15, 150

CC0_URL = "creativecommons.org/publicdomain/zero"

# 取得後に必ず通す変換。理由は2つ。
#  1. **音量を揃える**。録音は機材も距離もばらばらで、そのまま並べると
#     「雨だけ大きい」等になる。オン/オフで実感できることがこのUIの目的なので、
#     -23 LUFS(放送基準)に揃えてから、層ごとの音量はアプリ側の係数で決める。
#  2. **軽くする**。4層で 3.2MB あった。ラジオは Render 経由で配信するため、
#     モノラル 96kbps に落として合計 1MB 台にする(スマホのスピーカーでは
#     環境音のステレオ感はほぼ効かない)。
# 揃える先。TP(真のピーク)を -3dB にしてあるのは、mp3 に再エンコードすると
# 波形が少し膨らんで 0dB に張り付くため(1パス版で実際に rain が 0.0dB に達した)。
FF_BITRATE = "96k"
FF_TARGET_I = -23.0
FF_TARGET_TP = -3.0
FF_TARGET_LRA = 11.0


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Token {fs._KEY}",
        "User-Agent": "TorisCollection/0.1",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _ffmpeg() -> str | None:
    """ffmpeg の実体を返す。動画ビルドと同じ imageio_ffmpeg 同梱版を使う。"""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# モノラル化は**音量を測る前**に済ませる。
# 2026-08-11: 当初は `-af loudnorm` のあとに `-ac 1` でモノラルにしていたが、
# 左右が似ていない録音(波・小川)は混ぜた時点で音が小さくなり、せっかく揃えた
# 音量が崩れていた(波は目標 -23 に対し **-27.9 LUFS** で仕上がっていた)。
# 先にモノラルにしてから測れば、実際に配信するものそのものを測ることになる。
FF_MONO = "aformat=channel_layouts=mono,aresample=44100"


def _loudnorm_filter(ff: str, src: str) -> str:
    """1パス目: 実測値を取り、それを渡す2パス目用のフィルタ文字列を作る。

    1パス(測定なし)の loudnorm は当てが外れる。実際、雨は真のピークが 0.0dB まで
    張り付き、平均音量は層ごとに 11dB もばらついた(=タイルごとに音量が違う)。
    ここが揃っていないと、アプリ側でいくら係数を調整しても意味がない。
    """
    base = (f"{FF_MONO},"
            f"loudnorm=I={FF_TARGET_I}:TP={FF_TARGET_TP}:LRA={FF_TARGET_LRA}")
    r = subprocess.run(
        [ff, "-hide_banner", "-i", src, "-af", base + ":print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    try:
        # ffmpeg は JSON を stderr の末尾に出す
        tail = r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1]
        m = json.loads(tail)
        return (f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                # linear=false(動的)にしている。全体を一律に上げる linear では、
                # 波のように波形の起伏が大きい素材が真のピークに先に当たり、
                # 目標より 4.5dB も小さいまま仕上がった(実測)。環境音は鳥の声の下で
                # **一定の高さで敷かれている**ほうが良いので、動的側を選ぶ。
                f":offset={m['target_offset']}:linear=false")
    except Exception:
        print("  (測定に失敗したので1パスで揃える)")
        return base


def normalize(src: str, dest: str) -> bool:
    """音量を揃えつつモノラル 96kbps に落とす。失敗したら元のまま使う。"""
    ff = _ffmpeg()
    if not ff:
        print("  (ffmpeg が無いので変換を飛ばす。音量差と容量はそのまま)")
        return False
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", src,
         "-ac", "1", "-ar", "44100", "-af", _loudnorm_filter(ff, src),
         "-b:a", FF_BITRATE, dest],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(dest):
        print(f"  変換失敗(元のまま使う): {r.stderr[-200:]}")
        return False
    return True


def fetch_sound(sound_id: int) -> dict:
    """1件の素性を取る(ライセンス検証のため description まで取る)。"""
    fields = ("id,name,duration,license,username,tags,description,"
              "avg_rating,num_ratings,previews")
    url = f"{fs.FS_API_BASE}/sounds/{sound_id}/?fields={fields}"
    return json.loads(_get(url).decode("utf-8"))


def search(query: str) -> list[dict]:
    """CC0 に限定して検索する(候補出しのみ)。"""
    params = {
        "query": query,
        # ライセンスを CC0 に固定。ここを緩めると商用で使えない音が混ざる。
        "filter": f'license:"Creative Commons 0" duration:[{DUR_MIN} TO {DUR_MAX}]',
        "sort": "rating_desc",
        "fields": "id,name,duration,license,username,avg_rating,num_ratings,tags",
        "page_size": 8,
    }
    url = f"{fs.FS_API_BASE}/search/text/?{urllib.parse.urlencode(params)}"
    try:
        return json.loads(_get(url).decode("utf-8")).get("results", [])
    except Exception as e:
        print(f"  検索失敗 [{query}]: {type(e).__name__}: {e}")
        return []


def do_search() -> None:
    for key, query in SEARCH_QUERIES.items():
        print(f"\n=== {key} ({query}) ===")
        hits = search(query)
        if not hits:
            print("  CC0 の候補が見つからなかった")
            continue
        for h in hits[:6]:
            mark = "★採用中" if h["id"] == PICKS.get(key) else "       "
            print(f"  {mark} [{h['id']:>9}] {h.get('avg_rating', 0):.1f}"
                  f"({h.get('num_ratings', 0):>3})  {h['duration']:>5.1f}s  "
                  f"{h['name'][:46]}")
    print("\n採用する音を変えるときは、このファイルの PICKS を ID で書き換える。")


def main() -> None:
    if not fs.is_enabled():
        raise SystemExit(
            "Freesound の API キーが未設定。\n"
            "  1. https://freesound.org/apiv2/apply で登録(無料)\n"
            "  2. toris_collection/freesound_api_key.txt にキーだけ1行で保存\n"
            "  3. もう一度このコマンドを実行"
        )

    if "--search" in sys.argv:
        do_search()
        return

    download = "--download" in sys.argv
    if download:
        os.makedirs(OUT_DIR, exist_ok=True)
    credits = []

    for key, sound_id in PICKS.items():
        print(f"\n=== {key} (freesound #{sound_id}) ===")
        try:
            snd = fetch_sound(sound_id)
        except Exception as e:
            print(f"  取得失敗: {type(e).__name__}: {e}")
            continue

        lic = snd.get("license", "")
        print(f"  {snd['name'][:56]}  ({snd['duration']:.1f}s, by {snd.get('username')})")
        print(f"  {snd.get('avg_rating', 0):.1f} / {snd.get('num_ratings', 0)}件   {lic}")

        # ライセンスの再検証。PICKS は手で書くので、ここで必ず機械的に確かめる。
        if CC0_URL not in lic:
            print("  !! CC0 ではないので使えない。PICKS から外すこと。")
            continue
        if not (DUR_MIN <= snd["duration"] <= DUR_MAX):
            print(f"  !! 長さが範囲外({DUR_MIN}-{DUR_MAX}s)。アプリが重くなる。")
            continue
        if not download:
            continue

        # プレビュー(mp3)を取る。元ファイルはライセンス上は同じだが容量が大きい。
        url = (snd.get("previews") or {}).get("preview-hq-mp3")
        if not url:
            print("  プレビューURLが無いので飛ばす")
            continue
        dest = os.path.join(OUT_DIR, f"amb_{key}.mp3")
        raw = dest + ".raw.mp3"
        try:
            data = _get(url, timeout=90)
        except Exception as e:
            print(f"  DL失敗: {type(e).__name__}: {e}")
            continue
        with open(raw, "wb") as f:
            f.write(data)
        if normalize(raw, dest):
            os.remove(raw)
        else:
            os.replace(raw, dest)
        size = os.path.getsize(dest)
        print(f"  saved: {os.path.basename(dest)} "
              f"({len(data) // 1024}KB -> {size // 1024}KB)")
        credits.append({
            "layer": key, "freesound_id": snd["id"], "name": snd["name"],
            "user": snd.get("username"), "license": lic,
            "duration_s": round(snd["duration"], 1),
            "url": f"https://freesound.org/s/{snd['id']}/",
        })

    if download and credits:
        p = os.path.join(OUT_DIR, "_credits.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(credits, f, ensure_ascii=False, indent=1)
        print(f"\ncredits: {os.path.abspath(p)}")
    elif not download:
        print("\n(確認のみ。実際に取得するには --download を付ける)")


if __name__ == "__main__":
    main()
