"""
eco_log.py - 生態ログ(「なぜ来たか」の蓄積・重複除去)

■ 位置づけ
  `absence_loop.build_reason_text()` が生成する「なぜ来たか」の一文は、
  従来は到来時に一度表示されて終わりだった(揮発性・バナー表示のみ)。
  本モジュールはそれを鳥ごとに蓄積し、重複を除いて図鑑に表示するための
  純粋関数群。新しい"なぜ来たか"の恣意ロジックは一切追加しない
  (`build_reason_text` が生成した文字列をそのまま保存するだけ)。

  「あなたが組んだ関係(食物網)が、実際に鳥を呼んだという証拠」という位置づけ
  (docs/team/proposals/2026-07-05_本物の生態系ビジョン深掘り.md §4 案2)。

■ 罰しない(HANDOFF §1-1-a と同じ思想)
  一度記録された来訪理由は、撹乱で植物が失われても図鑑から消さない
  (append のみ・削除する API を持たない)。

集計/判定ロジックは I/O から切り離した純粋関数。テスト可能。
"""
from __future__ import annotations


def append_events(log: list[dict] | None, events: list[dict] | None) -> list[dict]:
    """不在中ループ等の到来イベント(bird_id/reason_text/arrived_at を持つ dict の
    リスト)を、生態ログに重複除去して追記する。

    同じ鳥について同じ理由文がすでに記録されていれば追加しない
    (「これまでに記録された来訪理由」を種類ごとに1件だけ蓄積する)。
    既存のログを破壊的に変更せず、新しいリストを返す。

    Args:
        log: 既存の生態ログ({"bird_id", "text", "first_at"} のリスト)。
        events: evolve_state()["events"] 相当。各要素は
                {"bird_id": str, "reason_text": str, "arrived_at": datetime|str} を持つ。

    Returns:
        list[dict]: 追記後の生態ログ(順序は既存 + 新規追記分)。
    """
    result = list(log or [])
    seen = {(e.get("bird_id"), e.get("text")) for e in result}
    for ev in events or []:
        bird_id = ev.get("bird_id")
        text = ev.get("reason_text")
        if not bird_id or not text:
            continue
        key = (bird_id, text)
        if key in seen:
            continue
        seen.add(key)
        at = ev.get("arrived_at")
        at_iso = (
            at.isoformat(timespec="seconds") if hasattr(at, "isoformat")
            else str(at) if at else ""
        )
        result.append({"bird_id": bird_id, "text": text, "first_at": at_iso})
    return result


def entries_for_bird(log: list[dict] | None, bird_id: str) -> list[dict]:
    """その鳥について記録された生態ログを、記録された順(古い→新しい)で返す。"""
    return sorted(
        (e for e in (log or []) if e.get("bird_id") == bird_id),
        key=lambda e: e.get("first_at") or "",
    )


def is_founding_record(entry: dict, entries: list[dict],
                       observed_first: str | None) -> bool:
    """その関係が、この鳥について記録された最初のログ行であり、かつ
    既存の `observed[bird]["first"]`(近距離観察の初回記録)が既に存在する
    場合にのみ、小さな印を付ける対象と判定する。

    新しい判定ロジックを増やさず、`entries_for_bird` の並び(最古が先頭)と
    `observed[bird]["first"]` の有無だけで判定する(新規データは使わない)。
    """
    if not entries or not observed_first:
        return False
    return entry is entries[0]
