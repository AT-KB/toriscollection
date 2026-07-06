"""
badges.py - 「会った日数」の節目バッジ(静かな演出)

■ 方針(交渉不能・原則1「受動的」/原則2「罰しない」に従う)
  「会った日数」(bird_days, 1日1カウント・非連続の累計。HANDOFF §4-4/§9)の節目
  (10/30/100日)に到達したとき、図鑑の該当鳥のカードに小さな一言+アイコンを
  添えるための純粋関数。連続ログイン条件・進捗バー・カウントダウンは一切持たない
  (「あと◯日で称号」のような煽りは作らない)。

  データは既存の bird_days のみを使う(新規のセッション状態・Sheets列は不要)。

集計/判定ロジックは I/O から切り離した純粋関数。テスト可能。
"""
from __future__ import annotations

# 到達日数が大きいものから順に判定し、最初に条件を満たした1件を採用する。
# (icon, label, message) — label は図鑑カードの見出しに使う短い呼び名、
# message はカードに添える一言。
TIERS = (
    (100, "🏅", "皆勤の友", "すっかり顔なじみです。"),
    (30, "🌿", "常連", "よく会う仲になりました。"),
    (10, "🌱", "おなじみ", "おなじみになってきました。"),
)


def badge_for_days(days: int) -> dict | None:
    """会った日数から、該当する節目バッジ(最高位1件)を返す。

    未到達(days が最小の節目にも届いていない)なら None。
    """
    if not days:
        return None
    for threshold, icon, label, message in TIERS:
        if days >= threshold:
            return {
                "threshold": threshold,
                "icon": icon,
                "label": label,
                "message": message,
            }
    return None


def badge_message(bird_name: str, days: int) -> str | None:
    """図鑑カードに添える一言(演出テキスト)。バッジ未到達なら None。

    数値・進捗(あと何回等)は含めない。かわいさ優先で短く1文に留める。
    """
    badge = badge_for_days(days)
    if not badge:
        return None
    return f"{badge['icon']} {bird_name}とは{badge['message']}"
