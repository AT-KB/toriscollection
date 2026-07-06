"""
test_badges.py - 節目バッジ(badges.py)の判定ロジック単体テスト

実行: python3 toris_collection/tests/test_badges.py
依存なし(pytest 不要、stdlib のみ)。badge_for_days / badge_message は
Streamlit にも依存しない純粋関数。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import badges  # noqa: E402


def test_no_badge_below_first_tier():
    assert badges.badge_for_days(0) is None
    assert badges.badge_for_days(1) is None
    assert badges.badge_for_days(9) is None


def test_first_tier_at_10_days():
    badge = badges.badge_for_days(10)
    assert badge is not None
    assert badge["threshold"] == 10
    assert badge["icon"] == "🌱"


def test_first_tier_holds_until_next_threshold():
    badge = badges.badge_for_days(29)
    assert badge["threshold"] == 10


def test_second_tier_at_30_days():
    badge = badges.badge_for_days(30)
    assert badge["threshold"] == 30
    assert badge["icon"] == "🌿"


def test_top_tier_at_100_days():
    badge = badges.badge_for_days(100)
    assert badge["threshold"] == 100
    assert badge["icon"] == "🏅"


def test_top_tier_holds_beyond_100():
    # 100日を超えても最高位のまま(称号が下がったり進捗が減ったりしない=罰しない)
    badge = badges.badge_for_days(365)
    assert badge["threshold"] == 100


def test_badge_for_days_never_regresses_with_more_days():
    # 日数が増えるほど到達する tier は単調に上がる(または同じ)
    prev_threshold = -1
    for days in range(0, 120, 3):
        badge = badges.badge_for_days(days)
        threshold = badge["threshold"] if badge else 0
        assert threshold >= prev_threshold
        prev_threshold = threshold


def test_badge_message_none_when_no_badge():
    assert badges.badge_message("シジュウカラ", 0) is None
    assert badges.badge_message("シジュウカラ", 5) is None


def test_badge_message_contains_bird_name_no_numbers():
    msg = badges.badge_message("シジュウカラ", 10)
    assert msg is not None
    assert "シジュウカラ" in msg
    # 進捗・カウントダウンの煽りを持たない(数字を出さない)方針の確認
    assert not any(ch.isdigit() for ch in msg)


def test_badge_message_uses_top_tier_icon():
    msg = badges.badge_message("メジロ", 100)
    assert msg.startswith("🏅")


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    _run()
