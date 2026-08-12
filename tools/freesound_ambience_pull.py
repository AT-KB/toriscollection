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
import re
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
# 2026-08-11 差し替え(CEO の試聴): 「波はもう少しザーッとした波打ち際感がいい」
# 「Wind はガサガサしていて気持ち悪い」「1つ1つが短い、特に Wind。継ぎ目が
# 分かりやすすぎる」。短い素材は繰り返しが早く来るぶん継ぎ目が目立つので、
# **長いものに入れ替え**、さらに継ぎ目そのものを畳んで消す(loopify)。
# trim は長すぎる素材を切る秒数(通信量のため)。None なら切らない。
PICKS = {
    # 雨: 作者がループ用に録った雨。前の素材(595717)は 22.5秒しかなく、
    #     繰り返しが早かった。
    "rain":   {"id": 584945, "trim": None},   # 73s "Rain Loop 1"
    # 風: 松林を渡る light wind。前の素材(378725)は落ち葉が転がる音で
    #     「ガサガサして気持ち悪い」。松は葉が細く、擦れる音が滑らかになる。
    #     予備案: 181801 "breeze.wav"(65s・★4.9/160件と評価数が桁違い)。
    #     こちらが合わなければ差し替える。
    "wind":   {"id": 715696, "trim": 120},    # 216s -> 120s
    # 小川: 岩を回る小さな流れ。前の素材(548373)は 30秒。
    "stream": {"id": 819768, "trim": None},   # 87s
    # 波: 小石の浜に打ち寄せ、引き波で小石が転がる音。作者いわく
    #     "more articulation of the pebbles rolling in the backwash"。
    #     これが「ザーッとした波打ち際感」に当たる。前の素材(260263)は
    #     船着き場に water がぴちゃぴちゃ当たる音で、波打ち際ではなかった。
    "waves":  {"id": 277480, "trim": 120},    # 187s -> 120s
}

# 継ぎ目を消すためのクロスフェード秒数。詳しくは loopify() を参照。
LOOP_XFADE = 4.0

# `--search` で候補を出すときの検索語(採用そのものには使わない)
SEARCH_QUERIES = {
    "rain":   "rain",
    "wind":   "forest wind rustling leaves",
    "stream": "small stream water loop ambient",
    "waves":  "waves shore",
}

# 長すぎる素材はアプリが重くなるので、この範囲のものから選ぶ(秒)
DUR_MIN, DUR_MAX = 60, 240

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


def duration_of(ff: str, path: str) -> float:
    """秒数を返す(ffmpeg の出力から読む。ffprobe は同梱されていない)。"""
    r = subprocess.run([ff, "-hide_banner", "-i", path, "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def loopify(ff: str, src: str, dest: str, xfade: float) -> bool:
    """**継ぎ目の無いループ**にする。

    CEO 指摘「つなぎ目が分かりやすすぎる」への対応。素材を長くするだけでは、
    一周したところで波形が飛ぶ事実は変わらない。そこで音そのものを畳む。

    長さ D の録音を、頭 A=[0, D-X] と尻尾 B=[D-X, D] に分け、
    **A の頭 X 秒に、B をクロスフェードで重ねたもの**(長さ D-X)を出力する。
      - 重なる X 秒は、A がフェードイン・B がフェードアウトして滑らかに混ざる
      - 出力の終わり(=A の終わり、元の D-X 地点)と、出力の頭(=B の頭、これも
        元の D-X 地点)は、元の録音では**まさに同じ場所**なので、繰り返しても
        段差が出ない
    結果、どこにも継ぎ目の無い輪になる。

    `acrossfade` フィルタでも同じことができるはずだが、この ffmpeg では
    出力が空になった(asplit を挟んでも同じ)。ので afade + amix で自分で組む。
    """
    dur = duration_of(ff, src)
    if dur < xfade * 3:
        print(f"  (短すぎるので継ぎ目の処理を飛ばす: {dur:.1f}s)")
        return False
    head_end = dur - xfade
    fc = (f"[0:a]asplit=2[s0][s1];"
          f"[s0]atrim=0:{head_end:.3f},asetpts=N/SR/TB,"
          f"afade=t=in:st=0:d={xfade}[a];"
          f"[s1]atrim={head_end:.3f}:{dur:.3f},asetpts=N/SR/TB,"
          f"afade=t=out:st=0:d={xfade}[b];"
          f"[a][b]amix=inputs=2:duration=first:normalize=0[out]")
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", src,
         "-filter_complex", fc, "-map", "[out]", dest],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(dest):
        print(f"  継ぎ目の処理に失敗(そのまま使う): {r.stderr[-200:]}")
        return False
    return True


def normalize(src: str, dest: str, trim: int | None) -> bool:
    """継ぎ目を消し、音量を揃え、モノラル 96kbps に落とす。

    失敗したら元のまま使う(音が出ないより、粗くても出るほうがよい)。
    """
    ff = _ffmpeg()
    if not ff:
        print("  (ffmpeg が無いので変換を飛ばす。音量差と容量はそのまま)")
        return False

    work = dest + ".work.wav"
    # ① 長さを切り、先にモノラルにする(音量を測る前にやることが重要。理由は FF_MONO)
    cut = ["-t", str(trim)] if trim else []
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", src] + cut +
        ["-af", FF_MONO, work], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  切り出しに失敗: {r.stderr[-200:]}")
        return False

    # ② 継ぎ目を畳む
    looped = dest + ".loop.wav"
    src2 = looped if loopify(ff, work, looped, LOOP_XFADE) else work

    # ③ 音量を揃えて mp3 に
    r = subprocess.run(
        [ff, "-y", "-loglevel", "error", "-i", src2,
         "-af", _loudnorm_filter(ff, src2), "-b:a", FF_BITRATE, dest],
        capture_output=True, text=True,
    )
    for p in (work, looped):
        if os.path.exists(p):
            os.remove(p)
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
            cur = (PICKS.get(key) or {}).get("id")
            mark = "★採用中" if h["id"] == cur else "       "
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

    for key, pick in PICKS.items():
        sound_id, trim = pick["id"], pick["trim"]
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
        if normalize(raw, dest, trim):
            os.remove(raw)
        else:
            os.replace(raw, dest)
        size = os.path.getsize(dest)
        out_dur = duration_of(_ffmpeg(), dest) if _ffmpeg() else 0.0
        print(f"  saved: {os.path.basename(dest)} "
              f"({len(data) // 1024}KB -> {size // 1024}KB, "
              f"{snd['duration']:.0f}s -> {out_dur:.0f}s)")
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
