"""投稿の数字を読む。**再生数ではなく比率を、誤差つきで**比べる。

CEO 2026-08-25「少しずつ投稿と再生数がたまってきたけどどうしようか、分析とか」。

## この道具が守っている考え方(2026-08-08 診断書 §測り方)

 - **再生数(カウント)は少数だと読めない。完全視聴率(比率)は読める。**
 - 見るのは2つ: **完全視聴率(目標 40%以上)** と
   **平均視聴時間 ÷ 尺(目標 60%以上)**。
 - 撤退の目安: バッチ4回(計12本)回して完全視聴率が20%を超えないなら。

## この道具が足していること — **誤差を出す**

比率が読めるのは事実だが、**「読める」には限度がある。**
再生100で完全視聴率40%と30%は、**同じ動画でも普通に起きる差**。
そこを目で見て「こっちが勝った」と判断すると、雑音に方針を振り回される
(`02_SNS部.md`「n=100 で方針を変えない」)。

なので完全視聴率には **Wilson の95%信頼区間**を付けて出し、
2本を比べるときは**区間が重なっていれば「まだ差は読めない」と言い切る**。
「何再生あれば読めるか」も出す。

依存は標準ライブラリだけ。

実行:
    py -3 tools/sns_analytics.py
    py -3 tools/sns_analytics.py --csv <別のCSV>
"""
import argparse
import csv
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CSV = os.path.join(ROOT, "marketing", "phase-1", "SNS部",
                           "analytics", "posts.csv")

# 診断書の目標値。**ここを変えるときは診断書も直す。**
TARGET_FULL = 40.0        # 完全視聴率(%)
TARGET_WATCH = 60.0       # 平均視聴時間 ÷ 尺(%)
RETREAT_FULL = 20.0       # これを12本超えられなければ撤退を検討
RETREAT_N = 12

Z = 1.96                  # 95%


def wilson(k, n, z=Z):
    """Wilson の信頼区間。**正規近似は使わない。**

    比率が0や1に寄ったとき、正規近似は区間が画面の外に出る
    (-5%〜35% のような読めない値になる)。Wilson は端でも壊れない。
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def needed_n(p1, p2, z=Z, power_z=0.84):
    """p1 と p2 を見分けるのに要るおおよその再生数(片群あたり)。

    ふつうの2標本比率の式(検出力80%)。**桁を掴むためのもの**で、
    小数点以下を信じる数字ではない。
    """
    p1, p2 = min(max(p1, 1e-6), 1 - 1e-6), min(max(p2, 1e-6), 1 - 1e-6)
    if abs(p1 - p2) < 1e-9:
        return None
    pbar = (p1 + p2) / 2
    num = (z * math.sqrt(2 * pbar * (1 - pbar))
           + power_z * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p1 - p2) ** 2))


def num(row, key):
    v = (row.get(key) or "").strip().replace(",", "").replace("%", "")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load(path):
    if not os.path.exists(path):
        raise SystemExit(f"台帳が無い: {path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        views = num(r, "views")
        full = num(r, "full_rate")
        if views is None or full is None:
            continue          # まだ数字を入れていない行は黙って飛ばす
        r["_views"] = int(views)
        r["_full"] = full
        r["_avg"] = num(r, "avg_watch")
        sec = num(r, "seconds") or 15.0
        r["_watch_pct"] = (r["_avg"] / sec * 100.0) if r["_avg"] else None
        out.append(r)
    return rows, out


def fmt_pct(x):
    return "  -  " if x is None else f"{x:5.1f}%"


def per_post(posted):
    print("── 1本ずつ ──────────────────────────────────────────────")
    print(f"{'file':<16}{'再生':>7}{'完全視聴':>9}{'95%区間':>16}"
          f"{'視聴/尺':>9}  判定")
    for r in sorted(posted, key=lambda x: (x.get("posted_at") or "")):
        n, p = r["_views"], r["_full"] / 100.0
        lo, hi = wilson(round(p * n), n)
        # 目標に届いているか。**区間の下端**で言う(点推定で言わない)。
        if lo * 100 >= TARGET_FULL:
            v = "目標クリア"
        elif hi * 100 < TARGET_FULL:
            v = "目標に届かない"
        else:
            v = "まだ読めない"
        print(f"{r['file']:<16}{n:>7}{fmt_pct(r['_full']):>9}"
              f"{f'{lo*100:.0f}–{hi*100:.0f}%':>16}"
              f"{fmt_pct(r['_watch_pct']):>9}  {v}")
    print()


def by_group(posted, key, label):
    """まとめて比べる。**再生数で重み付けした比率**にする。

    本ごとの率を単純平均すると、再生10の1本が再生300の1本と同じ重さになる。
    """
    groups = {}
    for r in posted:
        g = (r.get(key) or "?").strip() or "?"
        k, n = groups.get(g, (0.0, 0))
        groups[g] = (k + r["_full"] / 100.0 * r["_views"], n + r["_views"])
    if len(groups) < 2:
        return
    print(f"── {label}ごと ──────────────────────────────────────────")
    rows = []
    for g, (k, n) in sorted(groups.items()):
        lo, hi = wilson(k, n)
        rows.append((g, k / n if n else 0.0, lo, hi, n))
        print(f"{g:<14}{n:>7}再生  完全視聴 {k/n*100 if n else 0:5.1f}%"
              f"   95%区間 {lo*100:.0f}–{hi*100:.0f}%")
    # 一番上と一番下が見分けられるか。
    rows.sort(key=lambda x: -x[1])
    top, bot = rows[0], rows[-1]
    if top[2] > bot[3]:
        print(f"→ **{top[0]} が {bot[0]} より上**と言える"
              f"(区間が重なっていない)")
    else:
        need = needed_n(top[1], bot[1])
        tail = (f"見分けるには片方あたり約 {need} 再生要る" if need
                else "そもそも差がほぼ無い")
        print(f"→ **まだ差は読めない**({top[0]} と {bot[0]} の区間が重なる)。"
              f"{tail}")
    print()


def overall(posted):
    n = sum(r["_views"] for r in posted)
    k = sum(r["_full"] / 100.0 * r["_views"] for r in posted)
    if not n:
        return
    lo, hi = wilson(k, n)
    print("── 全体 ────────────────────────────────────────────────")
    print(f"投稿 {len(posted)} 本 / 合計 {n} 再生 / "
          f"完全視聴 {k/n*100:.1f}%(95%区間 {lo*100:.0f}–{hi*100:.0f}%)")
    if len(posted) >= RETREAT_N and hi * 100 < RETREAT_FULL:
        print(f"→ {RETREAT_N}本回して完全視聴率が {RETREAT_FULL:.0f}% に"
              f"届いていない。**撤退の検討に入る**(診断書 §撤退判断)")
    elif len(posted) < RETREAT_N:
        print(f"→ 撤退判断は {RETREAT_N} 本から。あと {RETREAT_N - len(posted)} 本")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=DEFAULT_CSV)
    a = ap.parse_args()
    rows, posted = load(a.csv)

    print(f"台帳: {os.path.relpath(a.csv, ROOT)}")
    print(f"行 {len(rows)} / うち数字が入っているもの {len(posted)}\n")
    if not posted:
        print("まだ1行も数字が入っていない。")
        print("TikTok の各動画 → アナリティクスから、次の5つを写す:")
        print("  views(再生数) / full_rate(視聴完了率 %) /")
        print("  avg_watch(平均再生時間 秒) / likes / follows")
        print("posted_at(YYYY-MM-DD)も入れると並びが正しくなる。")
        return

    per_post(posted)
    overall(posted)
    by_group(posted, "batch", "バッチ")
    by_group(posted, "topic", "題材")
    by_group(posted, "style", "見せ方")
    by_group(posted, "cta", "CTA")

    # 同じ字幕で見せ方だけ違う組。**変数が1つの比較はここだけ。**
    pairs = [("f01_alarm", "g05_wake_close"), ("f02_sleep", "g06_sleep_sink")]
    by_file = {r["file"]: r for r in posted}
    shown = False
    for a_, b_ in pairs:
        ra, rb = by_file.get(a_), by_file.get(b_)
        if not ra or not rb:
            continue
        if not shown:
            print("── 字幕が同じで見せ方だけ違う組(唯一、変数が1つの比較)──")
            shown = True
        la, ha = wilson(ra["_full"] / 100.0 * ra["_views"], ra["_views"])
        lb, hb = wilson(rb["_full"] / 100.0 * rb["_views"], rb["_views"])
        print(f"{a_} {ra['_full']:.1f}% ({la*100:.0f}–{ha*100:.0f}%)  vs  "
              f"{b_} {rb['_full']:.1f}% ({lb*100:.0f}–{hb*100:.0f}%)")
        if la > hb or lb > ha:
            win = a_ if la > hb else b_
            print(f"  → **{win} が上**と言える")
        else:
            need = needed_n(ra["_full"] / 100.0, rb["_full"] / 100.0)
            tail = (f"見分けるには片方あたり約 {need} 再生要る" if need
                    else "そもそも差がほぼ無い")
            print(f"  → まだ差は読めない。{tail}")
    if shown:
        print()


if __name__ == "__main__":
    sys.exit(main())
