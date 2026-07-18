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

from species_loader import BIRDS, PLANTS, INSECTS
from engine import calculate_arrival_probability, run_turn
import mementos as mem
import disturbance as dist
import garden_items
from i18n import t, get_lang


def _bird_name(bird):
    """表示用の鳥名。英語表示では english、無ければ日本語名。"""
    if get_lang() == "en" and bird.get("english"):
        return bird["english"]
    return bird.get("name", "")


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


def build_reason_text(bird_id: str, info: dict, item_hint: str | None = None):
    """なぜ来たか の一文を生成する。
    Returns: (reason_text, related_plant_id, related_insect_id)

    item_hint: 食物網由来の理由が薄い(incoming_pathsが空)場合にだけ使う、
      「今日の庭アイテム」の名前(例: "ハチドリ用ネクター給餌器")。
      GloBI由来の食物網経路が実在する場合はここを一切参照しない
      = 生態ログ(GloBI由来の理由文)にアイテム効果を混ぜないことを保証する。
      食物網の裏付けが無いのに正体不明のまま「立ち寄りました」と誤魔化す
      よりも、正直に「アイテムに誘われた」と言う(捏造しない・原則4)。
    """
    bird = BIRDS[bird_id]
    bird_name = _bird_name(bird)
    paths = info.get("incoming_paths") or []
    if not paths:
        if item_hint:
            return (t("{bird_name}が、{item_hint}に誘われて立ち寄りました。",
                      bird_name=bird_name, item_hint=item_hint), "", "")
        return (t("{bird_name}が立ち寄りました。", bird_name=bird_name), "", "")

    # 一番重みの大きい食物経路を採用
    paths_sorted = sorted(paths, key=lambda x: x[2], reverse=True)
    kind, pred_id, _w = paths_sorted[0]

    if kind == "plant" and pred_id in PLANTS:
        plant = PLANTS[pred_id]
        return (
            t("{bird_name}が来ました。{plant}に惹かれて立ち寄ったようです。",
              bird_name=bird_name, plant=plant['name']),
            pred_id, "",
        )
    if kind == "insect" and pred_id in INSECTS:
        insect = INSECTS[pred_id]
        return (
            t("{bird_name}が来ました。{insect}を狙って立ち寄ったようです。",
              bird_name=bird_name, insect=insect['name']),
            "", pred_id,
        )
    return (t("{bird_name}が立ち寄りました。", bird_name=bird_name), "", "")


def evolve_state(planted, biome, month, last_access_at, current_time,
                 current_residents, rng, item_placement=None):
    """
    last_access_at から current_time までの間、生態系を時間進化させる。

    item_placement: 広告リワード「今日の庭アイテム」(garden_items.py)の配置情報
      ({item_id, placed_at, expires_at} または None)。既定は None で、その場合は
      既存の挙動(アイテム効果ゼロ)から一切変わらない。tick ごとの時刻で
      有効期限を判定するので、不在中にアイテムが切れるケースも正しく扱う。

    Returns:
      {
        "residents": set[bird_id]      # 進化後の最終的な滞在鳥
        "events": list[dict]           # 到着イベント一覧(時系列順)
        "departures": list[bird_id]    # 不在中に去った鳥(重複あり)
        "n_ticks": int                 # 実行したサイクル数
        "disturbances": list[dict]     # 不在中の撹乱(植物の純減)の出来事
        "planted_final": list[str]     # 撹乱・遷移を反映した最終的な植生
      }
    """
    result = {
        "residents": set(current_residents),
        "events": [],
        "departures": [],
        "n_ticks": 0,
        "disturbances": [],
        "planted_final": list(planted),
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
    planted_work = list(planted)  # 撹乱・遷移で移ろう作業用の植生

    for i in range(n_ticks):
        # tickの時刻を不在期間内に配置(古い→新しい順に均等に)
        tick_progress = (i + 1) / n_ticks
        tick_time = last_access_at + timedelta(
            seconds=delta.total_seconds() * tick_progress
        )

        # ── 撹乱(世界の出来事。低頻度。倒れた植物は純減し、自動では植え直さない) ──
        event = dist.roll_disturbance(rng)
        if event:
            removed = dist.apply_disturbance(planted_work, event, PLANTS, rng)
            for pid in removed:
                if pid in planted_work:
                    planted_work.remove(pid)
            if removed:
                removed_names = [PLANTS.get(p, {}).get("name", p) for p in removed]
                result["disturbances"].append({
                    "type": event["type"],
                    "label": event["label"],
                    "icon": event["icon"],
                    "at": tick_time,
                    "removed": removed,
                    "story": dist.disturbance_story(event, removed_names),
                })

        # 「今日の庭アイテム」の効果(未配置・期限切れなら常に無効=既存挙動のまま)
        _arrival_bonus_fn = garden_items.make_arrival_bonus_fn(
            item_placement, biome, BIRDS, at_time=tick_time
        )
        _departure_bonus = garden_items.departure_bonus(item_placement, at_time=tick_time)

        tick_result = run_turn(
            planted_work, biome, month, residents, rng,
            arrival_bonus_fn=_arrival_bonus_fn, departure_bonus=_departure_bonus,
        )
        residents = tick_result["residents"]

        # このサイクルで起きた到着について「なぜ来たか」を計算
        if tick_result["arrivals"]:
            G = tick_result["graph"]
            for b in tick_result["arrivals"]:
                info = calculate_arrival_probability(b, G, biome, month)
                _item_hint = None
                if garden_items.is_item_boosted_arrival(
                    b, item_placement, biome, BIRDS, at_time=tick_time
                ):
                    _item = garden_items.ITEMS.get(
                        (item_placement or {}).get("item_id"), {}
                    )
                    _item_hint = _item.get("name")
                reason, plant_id, insect_id = build_reason_text(b, info, item_hint=_item_hint)

                # 落とし物の判定(現在の植生で)
                memento_id = mem.roll_drop(
                    b, biome, BIRDS[b], planted_work, rng
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
    result["planted_final"] = planted_work
    result["events"].sort(key=lambda e: e["arrived_at"])
    return result


def humanize_delta(arrived: datetime, now: datetime) -> str:
    """ '8時間前' のような相対時間文字列を返す"""
    if arrived is None or now is None:
        return ""
    seconds = (now - arrived).total_seconds()
    if seconds < 0:
        return t("まもなく")
    if seconds < 60:
        return t("今しがた")
    if seconds < 3600:
        return t("{n}分前", n=int(seconds // 60))
    if seconds < 86400:
        return t("{n}時間前", n=int(seconds // 3600))
    return t("{n}日前", n=int(seconds // 86400))


def summarize_events(events):
    """件数と種数のサマリ文字列を返す"""
    if not events:
        return ""
    n = len(events)
    species = {e["bird_id"] for e in events}
    if len(species) == 1:
        bid = next(iter(species))
        name = _bird_name(BIRDS.get(bid, {})) or bid
        return t("{name}が{n}回立ち寄りました", name=name, n=n)
    return t("{n}件の立ち寄り({s}種)", n=n, s=len(species))
