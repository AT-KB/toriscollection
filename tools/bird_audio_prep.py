"""鳥の録音を、鳴らす前に**きれいにしておく**ための道具。

## なぜ作るか(2026-08-12)
現行の Web 版は、再生しながら毎フレーム RMS を測って
  - ノイズゲート: 鳴いていない間の暗騒音を絞る
  - AGC: 録音ごとの音量差を吸収する
をやっている(`radio.py` の gateTick)。これは**録音が汚いまま届くから**必要な処理で、
`radio.py` の中でいちばん複雑な部分でもある。Flutter 移行の最大のリスクとして
提案書が名指ししたのも、まさにここだった。

しかし、この2つは**鳴らす前に済ませられる**。しかも事前処理なら、実時間の制約が
無いぶん、ゲートよりずっと良い方法(FFT による暗騒音の除去)が使える。
つまり「移植が難しい処理」ではなく「そもそも持ち込む必要のない処理」だった。

  実時間でやること      → 事前にやること
  ノイズゲート          → afftdn(暗騒音そのものを消す)
  AGC(音量の追従)       → loudnorm(音量を測って揃える)

残るリバーブ(奥行き)は flutter_soloud に freeverb があるので、そのまま作れる。

## 使い方
    py -3 tools/bird_audio_prep.py <入力> [<入力> ...] -o <出力ディレクトリ>
    py -3 tools/bird_audio_prep.py --measure <ファイル>   # 状態を測るだけ
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

# 鳥の声は環境音(-23 LUFS)より前に出したいので、少し大きめに揃える。
TARGET_I = -19.0
TARGET_TP = -2.0
TARGET_LRA = 9.0
BITRATE = "112k"          # 環境音より少し良い。さえずりは高い帯域に情報がある。

# 低域を切る位置。さえずりの基音より下(風・交通・空調のゴロゴロ)を落とす。
# 現行 radio.py の buildNode() も 820Hz で切っている。同じ考え方。
HIGHPASS_HZ = 500

# afftdn の効き。強くしすぎると鳴き声の余韻まで削れて不自然になる。
DENOISE_NF = -28


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def pcm(path: str, ff: str | None = None) -> np.ndarray:
    """モノラル 44.1kHz の生波形として読む(-1.0〜1.0)。"""
    ff = ff or ffmpeg()
    r = subprocess.run(
        [ff, "-v", "error", "-i", path, "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", "1", "-ar", "44100", "-"],
        capture_output=True)
    return np.frombuffer(r.stdout, dtype="<i2").astype(np.float64) / 32768.0


def measure(path: str) -> dict:
    """録音の「静かなところ」と「鳴いているところ」の差を測る。

    ゲートが要るかどうかは、この差で決まる。差が大きい(=静かなところが本当に
    静か)なら、ゲートは要らない。
    """
    x = pcm(path)
    if x.size < 4410:
        return {}
    win = 2048
    n = (x.size // win) * win
    rms = np.sqrt((x[:n].reshape(-1, win) ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    floor = float(np.percentile(db, 10))    # 暗騒音の高さ
    peak = float(np.percentile(db, 95))     # さえずりの高さ
    return {
        "seconds": round(x.size / 44100, 1),
        "noise_floor_db": round(floor, 1),
        "song_db": round(peak, 1),
        "gap_db": round(peak - floor, 1),   # ここが大きいほど「きれい」
    }


def _loudnorm(ff: str, src: str) -> str:
    """2パス loudnorm(1パス目で実測してから当てる)。"""
    base = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}")
    r = subprocess.run(
        [ff, "-hide_banner", "-i", src, "-af", base + ":print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    try:
        m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
        return (f"{base}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
                f":offset={m['target_offset']}:linear=false")
    except Exception:
        return base


def prepare(src: str, dest: str, stereo: bool = True) -> bool:
    """暗騒音を消し、低域を切り、音量を揃えて mp3 にする。

    stereo=True で**2チャンネル**にする。モノラルの方が軽いが、SoLoud の
    freeverb は「2チャンネルの音にしか使えない」と明記されており、モノラルの音に
    かけると金属的な異音になる(2026-08-13 実機で発生。CEO「キーンって鳴る」)。
    残響はこの商品の奥行きそのものなので、容量より残響を採る。
    処理と測定はモノラルで行い、最後に複製して2チャンネルにする
    (左右に同じものを置く。定位は再生側の pan で作る)。
    """
    ff = ffmpeg()
    tmp = dest + ".clean.wav"
    chain = (f"aformat=channel_layouts=mono,aresample=44100,"
             f"highpass=f={HIGHPASS_HZ},"
             f"afftdn=nf={DENOISE_NF}:nt=w")
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", src,
                        "-af", chain, tmp], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  下ごしらえに失敗: {r.stderr[-200:]}")
        return False
    af = _loudnorm(ff, tmp)
    if stereo:
        af += ",aformat=channel_layouts=stereo"
    r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", tmp,
                        "-af", af, "-b:a", BITRATE, dest],
                       capture_output=True, text=True)
    if os.path.exists(tmp):
        os.remove(tmp)
    if r.returncode != 0:
        print(f"  仕上げに失敗: {r.stderr[-200:]}")
        return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default=None, help="出力ディレクトリ")
    ap.add_argument("--measure", action="store_true", help="測るだけ")
    a = ap.parse_args()

    if a.measure or not a.out:
        for p in a.inputs:
            print(f"{os.path.basename(p):<34} {measure(p)}")
        return

    os.makedirs(a.out, exist_ok=True)
    for p in a.inputs:
        name = os.path.splitext(os.path.basename(p))[0] + ".mp3"
        dest = os.path.join(a.out, name)
        before = measure(p)
        if not prepare(p, dest):
            continue
        after = measure(dest)
        print(f"{name:<34} 暗騒音 {before['noise_floor_db']:>6.1f} -> "
              f"{after['noise_floor_db']:>6.1f} dB   "
              f"声との差 {before['gap_db']:>5.1f} -> {after['gap_db']:>5.1f} dB   "
              f"{os.path.getsize(p)//1024}KB -> {os.path.getsize(dest)//1024}KB")


if __name__ == "__main__":
    main()
