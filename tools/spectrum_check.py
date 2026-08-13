"""環境音の**スペクトルの傾き**を測り、どの「ノイズの色」に近いかを見る。

## なぜ測るのか(2026-08-13)
ホワイト/ピンク/ブラウンといった「ノイズの色」は、感覚的な呼び名ではなく
**1オクターブあたり何dB下がるか**で決まっている:

    ホワイト  0 dB/oct     … 全帯域が同じ強さ。シャーッとして耳につく
    ピンク   -3 dB/oct     … 自然界の音の多くがこの近く。1/f
    ブラウン  -6 dB/oct     … 低音寄り。ゴーッと重い

一方で「グリーンノイズ」「ブルーノイズ」は、睡眠の文脈では**工学的な定義を持たない
宣伝上の呼び名**である(グリーンは 500Hz〜2kHz あたりを持ち上げた"自然っぽい"音、
という程度の意味で使われる)。だから「グリーンノイズを入れる」という作り方はしない。

代わりに、この指標を**素材選びの物差し**として使う。合成音を足すのではなく、
「手持ちの録音がピンクからどれだけ離れているか」を測り、離れすぎたもの
(=耳につく/こもる)を避ける。研究が支持しているのは"色"そのものではなく
**自然音であること**なので(docs の提案書を参照)、録音は録音のまま使い、
選ぶときにだけ数字を見る。

    py -3 tools/spectrum_check.py <ファイル...>
"""
import subprocess
import sys

import numpy as np


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def pcm(path: str) -> np.ndarray:
    r = subprocess.run(
        [ffmpeg(), "-v", "error", "-i", path, "-f", "s16le", "-acodec",
         "pcm_s16le", "-ac", "1", "-ar", "44100", "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype="<i2").astype(np.float64) / 32768.0


# 測る帯域。低すぎる所は録音機材のゴロゴロ、高すぎる所は mp3 が切っているので外す。
F_LO, F_HI = 100.0, 8000.0
SR = 44100
WIN = 8192


def slope_db_per_octave(x: np.ndarray) -> tuple[float, float]:
    """log 周波数に対する log パワーの傾き(dB/oct)と、当てはまりの良さ(R^2)。"""
    n = (x.size // WIN) * WIN
    if n < WIN * 4:
        return float("nan"), 0.0
    frames = x[:n].reshape(-1, WIN) * np.hanning(WIN)
    power = (np.abs(np.fft.rfft(frames, axis=1)) ** 2).mean(axis=0) + 1e-20
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    m = (freqs >= F_LO) & (freqs <= F_HI)
    f, p = freqs[m], power[m]

    # オクターブごとにまとめる(そのまま回帰すると高域の点数が多く、引っ張られる)
    edges = 2.0 ** np.arange(np.log2(F_LO), np.log2(F_HI) + 1e-9, 1 / 3)
    xs, ys = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (f >= lo) & (f < hi)
        if sel.sum() < 2:
            continue
        xs.append(np.log2(np.sqrt(lo * hi)))
        ys.append(10 * np.log10(p[sel].mean()))
    if len(xs) < 5:
        return float("nan"), 0.0
    xs, ys = np.array(xs), np.array(ys)
    a, b = np.polyfit(xs, ys, 1)
    resid = ys - (a * xs + b)
    r2 = 1 - resid.var() / ys.var() if ys.var() > 0 else 0.0
    return float(a), float(r2)


def color_of(slope: float) -> str:
    """一番近い色の名前。境目はそれぞれの定義値の中間で切る。"""
    if np.isnan(slope):
        return "?"
    for name, ref in (("ブラウン", -6.0), ("ピンク", -3.0), ("ホワイト", 0.0),
                      ("ブルー", 3.0)):
        if abs(slope - ref) <= 1.5:
            return name
    if slope < -7.5:
        return "ブラウンより低音寄り"
    if slope > 4.5:
        return "ブルーより高音寄り"
    return "中間"


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        raise SystemExit(__doc__)
    print(f"{'ファイル':<28}{'傾き':>10}{'当てはまり':>10}  近い色")
    for p in paths:
        s, r2 = slope_db_per_octave(pcm(p))
        name = p.replace("\\", "/").split("/")[-1]
        print(f"{name:<28}{s:>7.1f}dB/oct{r2:>9.2f}  {color_of(s)}")
    print("\n参考: ピンク -3.0 / ホワイト 0.0 / ブラウン -6.0 dB/oct")
    print("当てはまりが低い(0.5未満)ものは、そもそも一直線では表せない音"
          "(音程のある音・断続音が混ざっている)。")


if __name__ == "__main__":
    main()
