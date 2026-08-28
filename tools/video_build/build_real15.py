"""実機の画面録画に音を後乗せする15秒(バッチ6)。**組み立てではない。**

CEO 2026-08-25「後乗せとかもやっておいて」。

## これまでとの違い

`build_feature15` / `build_variants15` / `build_quiz15` は**絵を組み立てて**いた。
こちらは **`.dev` の実機録画をそのまま使う**。組み立てでは作れない画
(目覚ましが鳴る瞬間・儀式で鳥が近づく)を、本物の画面のまま出す。

素材は `tools/video_build/_showcase_src/*_dev.mp4`(git 管理外)。
撮り方と、撮って分かった不具合は
`marketing/phase-1/SNS部/2026-08-25_実機素材_撮れたものと分かったこと.md`。

## 決めごと

**(1) 上端 100px を必ず落とす。** `.dev` は DEBUG の赤帯が出るが、
ステータスバーごと切れば消える(720x1600 の録画なら 100px)。
`build_showcase.py` の `STATUS = 64` は release 用で、**ここでは足りない**。

**(2) 音は「その画面で実際に鳴るもの」だけ。**
 - 目覚まし → 画面の "Your morning callers" に出ている種の録音だけ。
   **画面に Northern Cardinal と出ているので、鳴るのも Northern Cardinal だけ。**
   目覚ましは環境音を鳴らさないので、環境音も**敷かない**。
 - 環境音の重ね → **タイルを押した順に、その環境音を重ねる。**
   音源はアプリ同梱の CC0(`assets/ambience/_credits.json` で全7層とも CC0)。

⚠️ **儀式(`ritual_dev.mp4`)はまだ作れない。** 画面に "House Finch" と出るが、
同梱の House Finch の録音は **license_class が noncommercial**。
宣伝物には使えない(`pick_app_songs` と同じ判断)。
商用に使える種で儀式を撮り直せたら作る。

**(3) CTA は帯の中の1行。** クイズと同じ。最後に札を出して尺を食わない。

## 踏んだ罠(3つとも、エラーが出ないまま間違ったものが書き出された)

1. **実機録画は可変フレームレート。** そのまま重ねたら 22.21fps / 16.93秒に
   なった(15秒にならない)。→ 重ねる前に `fps=30` を挟む。
2. **同じ音源を何度も鳴らすのに `asplit` は使えない。**
   `[2:a]asplit=4` で枝分かれさせたら、鳴ったのは最初の1回だけで
   **4秒以降が丸ごと無音**。ffmpeg はエラーを返さない。
   → **同じファイルを `-i` で回数ぶん渡す**(`build_quiz15` と同じ形)。
3. **押したつもりのタイルが点いていなかった。** 環境音を6層鳴らしていたが、
   書き出した絵では ✓ が3つしか付いていなかった。
   **画面に無い音を鳴らしていた。** → 鳴らす層を画面に合わせ、字幕も直した。

**どれも「書き出してから音と絵を測る」までは気づけなかった。**
出したら必ず、区間ごとの `volumedetect` と 1コマずつの絵を見ること。

実行:
    py -3 tools/video_build/build_real15.py            # 2本
    py -3 tools/video_build/build_real15.py alarm      # 1本だけ
"""
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_concept15 import FPS, H, ROOT, W, draw_band  # noqa: E402
from build_sleep_wake15 import pick_app_songs  # noqa: E402
import build_feature15 as F  # noqa: E402
from build_quiz15 import BRAND, _segment  # noqa: E402

DUR = 15.0
OUT_DIR = F.OUT_DIR
SRC_DIR = os.path.join(ROOT, "tools", "video_build", "_showcase_src")
AMB_DIR = os.path.join(ROOT, "toris_app", "assets", "ambience")

# 実機録画の上端。DEBUG の帯 + ステータスバー。
CROP_TOP = 100
# 帯より上に置ける高さ(1080x1920 のうち字幕の帯を除いた分)。
VIDEO_H = H - int(H * 0.245)


def _amb_credit(layers):
    """環境音の出典。**全部 CC0 だが、それでも書く**(アプリ内でもそうしている)。

    ⚠️ **実際に鳴らした層の録音者だけ**を書く。最初は7層ぶん全部並べていて、
    使っていない waves の録音者まで載っていた。
    """
    rows = json.load(open(os.path.join(AMB_DIR, "_credits.json"),
                          encoding="utf-8"))
    bad = [r for r in rows if "publicdomain/zero" not in (r.get("license") or "")]
    if bad:
        raise SystemExit(f"CC0 でない環境音がある: {[r['layer'] for r in bad]}")
    by = {r["layer"]: r for r in rows}
    who = []
    for layer in layers:
        u = (by.get(layer) or {}).get("user")
        if u and u not in who:
            who.append(u)
    return "Ambience: Freesound CC0 — " + ", ".join(who)


# ══════════════════════════════════════════════════════════
# r01 目覚ましが鳴る
# ══════════════════════════════════════════════════════════
# 画面に出ているのは "Your morning callers ● Northern Cardinal" の1羽だけ。
# **だから鳴るのも Northern Cardinal だけ。**
# 実装は 8%(START_VOL)から始めて 5分(RAMP_MS)かけて上げる。
# 15秒でそれは見せられないので、**始まりの静かさ**だけを写す
# — 冒頭からゆっくり上がる。無音では始めない。
ALARM_L1 = "Wake up to a real bird."
ALARM_L2 = "It starts almost too quiet to hear."


_ALARM_PLAN = None


def _alarm_plan():
    """ひと節を、いつ・何回鳴らすか。**音源と時刻を1か所で決める。**"""
    global _ALARM_PLAN
    if _ALARM_PLAN is None:
        used, credit = pick_app_songs(["northern_cardinal"])
        onset, seg = _segment(used[0])
        times, at = [], 0.2
        while at + seg <= DUR:
            times.append(at)
            at += seg + 0.55
        _ALARM_PLAN = (used[0], credit, onset, seg, times or [0.2])
    return _ALARM_PLAN


def alarm_audio():
    # ⚠️ **同じ音源を、鳴らす回数ぶん `-i` で渡す。**
    # `asplit` で枝分かれさせたら、鳴ったのは最初の1回だけで
    # **4秒以降が無音**になった(ffmpeg はエラーを出さない)。
    # `build_quiz15` は同じファイルを複数回渡す形で動いているので、そちらに合わせる。
    src, credit, _o, _s, times = _alarm_plan()
    return [src] * len(times), credit + "   ·   (real screen)"


def alarm_filters(ain_index, used):
    """**ひと節を繰り返して、ゆっくり大きくする。**環境音は敷かない。

    ⚠️ 録音をそのまま 0 から 15秒流したら、**末尾3秒が無音**になった
    (-83dB)。Cardinal の録音は頭に間があり、途中も休む。クイズで踏んだのと
    同じ穴なので、同じ道具(`_segment`)で頭出しとひと節を測る。
    繰り返しながら音量を上げるのは、実装の
    「8% から 5分かけて上げる / 1羽が鳴き続ける」に沿っている。
    """
    _src, _c, onset, seg, times = _alarm_plan()
    parts, tags = [], []
    for i, t0 in enumerate(times):
        # 後の回ほど大きく(0.35 → 1.0)。**静かに始まって育つ。**
        vol = 0.35 + 0.65 * min(1.0, t0 / (DUR - 2.0))
        parts.append(
            f"[{ain_index + i}:a]atrim=start={onset:.3f}:end={onset + seg:.3f},"
            f"asetpts=PTS-STARTPTS,volume={vol:.2f},"
            f"adelay={int(t0 * 1000)}|{int(t0 * 1000)}[m{i}]")
        tags.append(f"[m{i}]")
    return (";".join(parts) + ";" + "".join(tags)
            + f"amix=inputs={len(times)}:duration=longest:normalize=0,")


# ══════════════════════════════════════════════════════════
# r02 環境音を重ねる
# ══════════════════════════════════════════════════════════
# 録画で押した順にタイルが灯る。**その順に、その環境音を重ねる。**
# Wind は最初から入っていた(録画開始時点で ✓)。
AMB_L1 = "Seven sounds you can layer."
AMB_L2 = "Rain, wind, a stream — no music."

# (層, 入る時刻, 音量)。**時刻は録画でタイルに ✓ が点く瞬間**に合わせてある。
#
# ⚠️ **画面で点いていない層は鳴らさない。**
# 最初は録画で「押したつもり」の6層(waves / fire / drips 込み)を鳴らしていたが、
# 書き出した絵を見たら**タップが外れていて ✓ が付いていなかった**。
# 画面に無い音が鳴るのは、鳴っていない鳥の名前を光らせるのと同じ誤り。
# 字幕からも fire を外した。
AMB_LAYERS = [("wind", 0.0, 0.50), ("rain", 0.3, 0.46), ("stream", 3.5, 0.44)]


def amb_audio():
    files = []
    for layer, _at, _v in AMB_LAYERS:
        p = os.path.join(AMB_DIR, f"{layer}.mp3")
        if not os.path.exists(p):
            raise SystemExit(f"環境音が無い: {p}")
        files.append(p)
    return files, _amb_credit([l for l, _a, _v in AMB_LAYERS]) + "   ·   (real screen)"


def amb_filters(first_index, used):
    parts, tags = [], []
    for i, (_layer, at, vol) in enumerate(AMB_LAYERS):
        k = first_index + i
        parts.append(
            f"[{k}:a]atrim=0:{DUR - at},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=1.4,volume={vol},"
            f"adelay={int(at * 1000)}|{int(at * 1000)}[m{i}]")
        tags.append(f"[m{i}]")
    return (";".join(parts) + ";" + "".join(tags)
            + f"amix=inputs={len(AMB_LAYERS)}:duration=longest:normalize=0,")


FILMS = {
    "alarm": {
        "src": "alarm_dev.mp4", "ss": 3.4,
        "out": "r01_alarm_real_15s_1080x1920.mp4",
        "l1": ALARM_L1, "l2": ALARM_L2, "switch": 7.4,
        "audio": alarm_audio, "filters": alarm_filters,
    },
    "ambience": {
        "src": "ambience_dev.mp4", "ss": 0.8,
        "out": "r02_ambience_real_15s_1080x1920.mp4",
        "l1": AMB_L1, "l2": AMB_L2, "switch": 8.0,
        "audio": amb_audio, "filters": amb_filters,
    },
}


def band_frames(film, credit, tmp):
    """字幕の帯だけを透明な板に描いて、動画に重ねる。

    絵は実機のものをそのまま使うので、**こちらで描くのは帯だけ**。
    """
    n = int(DUR * FPS)
    for f in range(n):
        t = f / FPS
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        head = film["l1"] if t < film["switch"] else film["l2"]
        ap = t / 0.6 if t < film["switch"] else (t - film["switch"]) / 0.6
        draw_band(im, ImageDraw.Draw(im), head, None, credit, ap, brand=BRAND)
        im.save(os.path.join(tmp, f"b{f:04d}.png"))
    return n


def _measure(ff, inputs, core):
    """1パス目。混ぜたあとの音量を測る。**音だけ**なので絵は流さない。

    `build_feature15._measure` と同じ考え方だが、あちらは入力の組み方が
    違う(無音の mp4 + 音源)ので、こちらで組み直している。
    """
    import re
    r = subprocess.run(
        [ff, "-y"] + inputs +
        ["-filter_complex", core + F._loudnorm() + "[aout]",
         "-map", "[aout]", "-t", str(DUR), "-f", "null", "-"],
        capture_output=True, text=True, errors="replace")
    m = re.findall(r"\{[^{}]*input_i[^{}]*\}", r.stderr, re.S)
    if not m:
        print(r.stderr[-700:])
        raise SystemExit("音量の測定に失敗")
    return json.loads(m[-1])


def build(key):
    film = FILMS[key]
    src = os.path.join(SRC_DIR, film["src"])
    if not os.path.exists(src):
        raise SystemExit(f"実機の素材が無い: {src}\n"
                         f"撮り方は 2026-08-25_実機素材_… を見る")
    used, credit = film["audio"]()
    out = os.path.join(OUT_DIR, film["out"])
    tmp = os.path.join(os.path.dirname(__file__), f"_real_{key}")
    os.makedirs(tmp, exist_ok=True)
    band_frames(film, credit, tmp)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    # 実機録画 → 上端を落として 1080 幅に伸ばし、帯のぶんを残して切る。
    # ⚠️ **`fps=30` を必ず挟む。** `screenrecord` の出力は可変フレームレートで、
    # そのまま重ねると出来上がりが 22.21fps / 16.93秒 になった(15秒にならない)。
    vf = (f"[0:v]crop=in_w:in_h-{CROP_TOP}:0:{CROP_TOP},"
          f"scale={W}:-2,crop={W}:{VIDEO_H}:0:0,"
          f"pad={W}:{H}:0:0:color=0x182216,fps={FPS}[bg];"
          f"[bg][1:v]overlay=0:0[v]")
    inputs = ["-ss", str(film["ss"]), "-t", str(DUR), "-i", src,
              "-framerate", str(FPS), "-i", os.path.join(tmp, "b%04d.png")]
    for a in used:
        inputs += ["-i", a]

    core = film["filters"](2, used)
    measured = _measure(ff, inputs, core)
    af = core + F._loudnorm(measured) + ","
    af += f"afade=t=in:st=0:d=0.3,afade=t=out:st={DUR-0.5}:d=0.5[aout]"

    r = subprocess.run(
        [ff, "-y"] + inputs +
        ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[aout]",
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", str(FPS),
         "-c:a", "aac", "-b:a", "128k", "-t", str(DUR),
         "-movflags", "+faststart", out],
        capture_output=True, text=True, errors="replace")
    if r.returncode:
        print(r.stderr[-900:])
        raise SystemExit(f"{key}: 書き出しに失敗")
    print(f"  {os.path.relpath(out, ROOT)}  "
          f"{os.path.getsize(out)//1024} KB  {DUR}秒  {W}x{H}")
    print(f"  {credit}")


if __name__ == "__main__":
    want = sys.argv[1:] or list(FILMS)
    for k in want:
        if k not in FILMS:
            raise SystemExit(f"知らない題目: {k} / 使えるのは {list(FILMS)}")
        print(f"[{k}]")
        build(k)
