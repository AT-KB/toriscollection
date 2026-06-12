"""
disturbance.py - 撹乱(かくらん)の生態モデル

■ 方針(交渉不能・HANDOFF §1-1 の背骨に従う)
  撹乱は「世界の出来事」。プレイヤーのせいにしない。低頻度。
  倒れた植物は純減する——跡地に自動で別の植物を植え直すことはしない。
  撹乱は罰ではなく「庭が移ろう」体験だが、回復は自然まかせ(=ユーザー自身が
  また植える)に委ねる。

■ 生態学的根拠(誠実さ)
  - 種数–面積関係 S=cA^z: 植生の基盤が縮むと種数が減る。
    → 本モジュールは「植物を消す」だけを担う。
      鳥の確率・種数が下がるのは engine.py の既存の food_factor / 退去ロジックが
      自然に引き起こす(余計な係数を足さない = よりモデルに誠実)。

このモジュールは I/O にも UI にも依存しない純粋計算。
"""
from __future__ import annotations

# 撹乱タイプ
#   severity: 1イベントで植物が倒れる確率の係数(× 各植物の感受性)
DISTURBANCES = {
    "storm":     {"label": "嵐",   "icon": "🌀", "severity": 0.50},
    "lightning": {"label": "落雷", "icon": "⚡", "severity": 0.30},
    "logging":   {"label": "伐採", "icon": "🪓", "severity": 0.60},
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


def disturbance_story(event: dict, removed_names: list[str]) -> str:
    """撹乱を1文で語る。倒れた植物は純減し、自動では植え直さない。"""
    icon = event.get("icon", "🌪")
    label = event.get("label", "嵐")
    if removed_names:
        lost = "・".join(removed_names)
        return f"{icon} {label}が庭を通り過ぎ、{lost}が倒れた。"
    return f"{icon} {label}が庭を通り過ぎたが、植物は持ちこたえた。"
