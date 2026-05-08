"""
Toris Collection - 不在中ループ(時間進化エンジン)

設計思想:
  時間軸を「ターン進める」操作から、「現実時間の経過に応じた自動進行」に
  完全に切り替える。プレイヤーがアプリを離れている間にも生態系が動いている、
  という体験を作る。

主な責務:
  1. 経過時間に応じて生態系を N サイクル進化させる
  2. その過程で発生した到着・退去イベントを記録
  3. 各到着の「なぜ来たか」一文を生成
"""
from datetime import datetime, timedelta

from data import BIRDS, PLANTS, INSECTS
from engine import calculate_arrival_probability, run_turn
import mementos as mem


def parse_iso(s):
    """ISO形式の文字列を datetime に変換。失敗時は None"""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s))
    except (ValueError, TypeError):
        return None


def estimate_tick_count(hours_passed: float) -> int:
    """経過時間から進化サイクル数を決定する

    < 5分      : 0サイクル (実質ゼロ秒の再アクセスでは何も起きない)
    5-30分     : 1サイクル (コーヒー休憩レベル)
    30分-2時間 : 2サイクル (ちょっと外出)
    2-6時間    : 3サイクル (半日)
    6-12時間   : 4サイクル (典型的な仕事前→仕事後)
    12-24時間  : 5サイクル (1日)
    24時間以上 : 6サイクル (上限)
    """
    minutes = hours_passed * 60
    if minutes < 5:
        return 0
    if minutes < 30:
        return 1
    if hours_passed < 2:
        return 2
    if hours_passed < 6:
        return 3
    if hours_passed < 12:
        return 4
    if hours_passed < 24:
        return 5
    return 6


def build_reason_text(bird_id: str, info: dict):
    """なぜ来たか の一文を生成する。
    Returns: (reason_text, related_plant_id, related_insect_id)
    """
    bird = BIRDS[bird_id]
    bird_name = bird["name"]
    paths = info.get("incoming_paths") or []
    if not paths:
        return (f"{bird_name}が立ち寄りました。", "", "")

    # 一番重みの大きい食物経路を採用
    paths_sorted = sorted(paths, key=lambda x: x[2], reverse=True)
    kind, pred_id, _w = paths_sorted[0]

    if kind == "plant" and pred_id in PLANTS:
        plant = PLANTS[pred_id]
        return (
            f"{bird_name}が来ました。{plant['name']}に惹かれて立ち寄ったようです。",
            pred_id, "",
        )
    if kind == "insect" and pred_id in INSECTS:
        insect = INSECTS[pred_id]
        return (
            f"{bird_name}が来ました。{insect['name']}を狙って立ち寄ったようです。",
            "", pred_id,
        )
    return (f"{bird_name}が立ち寄りました。", "", "")


def evolve_state(planted, biome, month, last_access_at, current_time,
                 current_residents, rng):
    """
    last_access_at から current_time までの間、生態系を時間進化させる。

    Returns:
      {
        "residents": set[bird_id]      # 進化後の最終的な滞在鳥
        "events": list[dict]           # 到着イベント一覧(時系列順)
        "departures": list[bird_id]    # 不在中に去った鳥(重複あり)
        "n_ticks": int                 # 実行したサイクル数
      }
    """
    result = {
        "residents": set(current_residents),
        "events": [],
        "departures": [],
        "n_ticks": 0,
    }

    if not planted or last_access_at is None or current_time is None:
        return result

    delta = current_time - last_access_at
    if delta.total_seconds() <= 0:
        return result

    hours = delta.total_seconds() / 3600
    n_ticks = estimate_tick_count(hours)
    if n_ticks == 0:
        return result
    result["n_ticks"] = n_ticks

    residents = set(current_residents)

    for i in range(n_ticks):
        tick_result = run_turn(planted, biome, month, residents, rng)
        residents = tick_result["residents"]

        # このサイクルで起きた到着について「なぜ来たか」を計算
        if tick_result["arrivals"]:
            G = tick_result["graph"]
            # tickの時刻を不在期間内に配置(古い→新しい順に均等に)
            tick_progress = (i + 1) / n_ticks
            tick_time = last_access_at + timedelta(
                seconds=delta.total_seconds() * tick_progress
            )
            for b in tick_result["arrivals"]:
                info = calculate_arrival_probability(b, G, biome, month)
                reason, plant_id, insect_id = build_reason_text(b, info)

                # 落とし物の判定
                memento_id = mem.roll_drop(
                    b, biome, BIRDS[b], planted, rng
                )

                result["events"].append({
                    "arrived_at": tick_time,
                    "bird_id": b,
                    "reason_text": reason,
                    "related_plant_id": plant_id,
                    "related_insect_id": insect_id,
                    "memento_id": memento_id,
                })

        result["departures"].extend(tick_result["departures"])

    result["residents"] = residents
    result["events"].sort(key=lambda e: e["arrived_at"])
    return result


def humanize_delta(arrived: datetime, now: datetime) -> str:
    """ '8時間前' のような相対時間文字列を返す"""
    if arrived is None or now is None:
        return ""
    seconds = (now - arrived).total_seconds()
    if seconds < 0:
        return "まもなく"
    if seconds < 60:
        return "今しがた"
    if seconds < 3600:
        return f"{int(seconds // 60)}分前"
    if seconds < 86400:
        return f"{int(seconds // 3600)}時間前"
    return f"{int(seconds // 86400)}日前"


def summarize_events(events):
    """件数と種数のサマリ文字列を返す"""
    if not events:
        return ""
    n = len(events)
    species = {e["bird_id"] for e in events}
    if len(species) == 1:
        bid = next(iter(species))
        name = BIRDS.get(bid, {}).get("name", bid)
        return f"{name}が{n}回立ち寄りました"
    return f"{n}件の立ち寄り({len(species)}種)"
