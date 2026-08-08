"""predators.py - 図鑑「こわいもの」(天敵)の参照層。

データは `predator_data.py`(GloBI の preyedUponBy 実エッジから自動生成)。
このモジュールは、その生データを**表示できる形**にするだけで、
天敵を推測したり作ったりはしない(交渉不能の原則4=生態に誠実)。

設計メモ:
  - 種名ではなく分類カテゴリ(タカのなかま/フクロウ/ヘビ…)で持つ。GloBI の
    生の相手名は地域がバラバラで、庭の体験としては誠実さを損なうため
    (詳細は tools/build_predator_data.py の docstring)。
  - `level == "genus"` は同属の近縁種の記録から採ったもの。表示側で
    「近縁のなかまの記録」と断る。黙って種の事実にしない。
  - **罰しない(原則2)**: ここは図鑑の読み物であって、ゲーム内の脅威ではない。
    到来率・図鑑・会った日数には一切影響しない。
"""
from __future__ import annotations

from i18n import t

try:
    from predator_data import PREDATORS
except ImportError:  # 生成物が無くても本編は動く(図鑑の1行が出ないだけ)
    PREDATORS = {}

# カテゴリ → 表示ラベル(日本語原文)。英訳は i18n.TRANSLATIONS 側に持つ。
# トーンは「こわいもの」だが、煽らない静かな呼び方にする(原則5)。
CATEGORY_LABELS: dict[str, str] = {
    "raptor": "タカのなかま",
    "owl": "フクロウのなかま",
    "falcon": "ハヤブサのなかま",
    "snake": "ヘビ",
    "crow": "カラスのなかま",
    "shrike": "モズのなかま",
    "cat": "ネコ",
    "raccoon": "アライグマ",
    "weasel": "イタチのなかま",
    "fox": "キツネのなかま",
    "squirrel": "リスのなかま",
    "rodent": "ネズミのなかま",
}


def categories(bird_id: str) -> list[str]:
    """その鳥の天敵カテゴリのキー一覧(多い順・最大3)。無ければ空リスト。"""
    rec = PREDATORS.get(bird_id)
    if not rec:
        return []
    return [c for c in rec.get("categories", []) if c in CATEGORY_LABELS]


def is_genus_level(bird_id: str) -> bool:
    """天敵が「同属の近縁種の記録」由来なら True。"""
    rec = PREDATORS.get(bird_id)
    return bool(rec) and rec.get("level") == "genus"


def labels(bird_id: str) -> list[str]:
    """その鳥の天敵カテゴリを、現在の表示言語のラベルにして返す。"""
    return [t(CATEGORY_LABELS[k]) for k in categories(bird_id)]


def has_data(bird_id: str) -> bool:
    return bool(categories(bird_id))
