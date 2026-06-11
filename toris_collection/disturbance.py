"""
disturbance.py - 撹乱(かくらん)と遷移(succession)の生態モデル

■ 方針(交渉不能・HANDOFF §1-1 の背骨に従う)
  撹乱は「世界の出来事」。プレイヤーのせいにしない。低頻度。
  そして損失の次に必ず再生(遷移)を置く——倒れた跡地に違う植物が芽吹き、
  違う鳥が来る = ラジオに新しい顔ぶれ。罰ではなく「庭が移ろう」体験にする。
  これは retention にも効く(新顔=また会いに行く)。

■ 生態学的根拠(誠実さ)
  - 撹乱生態学 / 中規模撹乱仮説: 嵐はキャノピーに隙間を作り、遷移が起きる。
    群集は"減る"のではなく"入れ替わる"。
  - 自然撹乱(嵐・落雷)は patchy で回復が早い。人為撹乱(伐採)は
    carrying capacity を下げ、回復が遅い。
  - 種数–面積関係 S=cA^z: 植生の基盤が縮むと種数が減る。
    → 本モジュールは「植物を消す/芽吹かせる」だけを担う。
      鳥の確率・種数が下がるのは engine.py の既存の food_factor / 退去ロジックが
      自然に引き起こす(余計な係数を足さない = よりモデルに誠実)。

このモジュールは I/O にも UI にも依存しない純粋計算。
"""
from __future__ import annotations

# 撹乱タイプ
#   severity: 1イベントで植物が倒れる確率の係数(× 各植物の感受性)
#   recovery: 撹乱跡地にパイオニア種が芽吹く確率(自然撹乱ほど高い)
DISTURBANCES = {
    "storm":     {"label": "嵐",   "icon": "🌀", "severity": 0.50, "recovery": 0.80},
    "lightning": {"label": "落雷", "icon": "⚡", "severity": 0.30, "recovery": 0.70},
    "logging":   {"label": "伐採", "icon": "🪓", "severity": 0.60, "recovery": 0.30},
}

# 1サイクルあたり撹乱が起きる基礎確率(低頻度: 日常を壊さない)
BASE_DISTURBANCE_P = 0.10
# タイプの相対頻度(自然撹乱が主、人為=伐採はまれ)
TYPE_WEIGHTS = {"storm": 0.55, "lightning": 0.30, "logging": 0.15}

# 植物がデータに形質を持たないときの既定値(シードはこれ、Sheets列で上書き可)
DEFAULT_SENSITIVITY = 0.5


def plant_sensitivity(plant_id: str, plants_data: dict) -> float:
    """その植物の撹乱への弱さ(0..1)。data に無ければ既定値。"""
    v = plants_data.get(plant_id, {}).get("disturbance_sensitivity")
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return DEFAULT_SENSITIVITY


def is_pioneer(plant_id: str, plants_data: dict) -> bool:
    """撹乱跡地に入るパイオニア種か。未設定は True(=芽吹き候補)とみなす。

    succession_role に 'late'(極相種)が入っている植物だけを候補から外す。
    こうすることで、シードデータ(役割未設定)でも遷移が動く。
    """
    role = str(plants_data.get(plant_id, {}).get("successional_role", "")).strip().lower()
    return role != "late"


def roll_disturbance(rng) -> dict | None:
    """このサイクルで撹乱が起きるか1回抽選する。

    Returns: {"type", "label", "icon", "severity", "recovery"} または None。
    """
    if rng.random() >= BASE_DISTURBANCE_P:
        return None
    types = list(TYPE_WEIGHTS.keys())
    weights = [TYPE_WEIGHTS[t] for t in types]
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    chosen = types[-1]
    for t, w in zip(types, weights):
        acc += w
        if r <= acc:
            chosen = t
            break
    return {"type": chosen, **DISTURBANCES[chosen]}


def apply_disturbance(planted: list[str], event: dict, plants_data: dict, rng) -> list[str]:
    """撹乱で倒れる植物IDのリスト(planted の部分集合)を返す。

    各植物が倒れる確率 = severity × その植物の感受性。
    ただし庭が完全に消えるのは避ける(罰しない/庭は残る): 全滅しそうなら1本残す。
    """
    if not planted:
        return []
    sev = float(event.get("severity", 0.5))
    removed = []
    for pid in planted:
        if rng.random() < sev * plant_sensitivity(pid, plants_data):
            removed.append(pid)
    if removed and len(removed) >= len(planted):
        # 1本は必ず残す(最後の緑は失わせない)
        keep = rng.choice(list(planted))
        removed = [r for r in removed if r != keep]
    return removed


def roll_succession(planted: list[str], biome_id: str, plants_data: dict,
                    event: dict, rng, exclude=None) -> str | None:
    """撹乱跡地に芽吹くパイオニア植物を1つ返す(無ければ None)。

    recovery 確率で、そのバイオームのまだ植わっていないパイオニア種から選ぶ。
    遷移は「違う植物」を呼び込み、結果として「違う鳥」をラジオに連れてくる。

    exclude: この撹乱で倒れたばかりの植物。同じ種がその場で生え直すと
             「移ろい」にならないので候補から外す(succession=群集の入れ替え)。
    """
    if rng.random() >= float(event.get("recovery", 0.0)):
        return None
    blocked = set(planted) | set(exclude or [])
    candidates = [
        pid for pid, p in plants_data.items()
        if biome_id in p.get("biome", [])
        and pid not in blocked
        and is_pioneer(pid, plants_data)
    ]
    if not candidates:
        return None
    return rng.choice(candidates)


def disturbance_story(event: dict, removed_names: list[str],
                      sprout_name: str | None) -> str:
    """撹乱→再生を1文で語る(罰でなく「移ろい」として)。"""
    icon = event.get("icon", "🌪")
    label = event.get("label", "嵐")
    if removed_names:
        lost = "・".join(removed_names)
        if sprout_name:
            return (f"{icon} {label}が庭を通り過ぎた。{lost}が倒れたが、"
                    f"跡地に{sprout_name}が芽吹き始めた。")
        return (f"{icon} {label}が庭を通り過ぎた。{lost}が倒れた。"
                "じきに新しい芽が出てくるだろう。")
    if sprout_name:
        return f"{icon} {label}のあと、跡地に{sprout_name}が芽吹いた。"
    return f"{icon} {label}が庭を通り過ぎたが、植物は持ちこたえた。"
