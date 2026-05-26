"""
observation_log.py - 儀式での近距離観察記録の保存・読み出し

儀式UI(ritual.py)で鳥が「近距離」まで来た瞬間が観察記録になる(仕様§3-8)。
記録は Finch 型の罰なし蓄積。各鳥について累計観察回数・初回観察日・直近観察日を持つ。

JS(iframe)→ top window のクエリパラメータ → app.py → ここ → Sheets の流れで保存される。
保存は sheets_client に委譲し、本モジュールは儀式ドメインの薄い窓口に徹する。
"""
from __future__ import annotations

import sheets_client as sc


def record_observation(tester_id: str, bird_id: str, biome_id: str = "") -> None:
    """近距離まで来た鳥1羽を観察記録として追加する(append-only)。"""
    sc.add_observation(tester_id, bird_id, biome_id)


def load_observation_counts(tester_id: str) -> dict:
    """{bird_id: {"count": int, "first": iso, "last": iso}} を返す。

    図鑑タブで「近距離観察 N回」のように表示するためのもの(表示側の実装は次段階)。
    """
    return sc.load_observation_counts(tester_id)
