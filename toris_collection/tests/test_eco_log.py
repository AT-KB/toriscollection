"""
test_eco_log.py - 生態ログ(eco_log.py)の蓄積・重複除去ロジック単体テスト

実行: python3 toris_collection/tests/test_eco_log.py
依存なし(pytest 不要、stdlib のみ)。append_events / entries_for_bird /
is_founding_record は Streamlit にも依存しない純粋関数。
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import eco_log  # noqa: E402


def test_append_events_from_empty_log():
    events = [{"bird_id": "shijukara", "reason_text": "サクラの虫を求めて来た", "arrived_at": "2026-07-01T08:00:00"}]
    result = eco_log.append_events([], events)
    assert len(result) == 1
    assert result[0]["bird_id"] == "shijukara"
    assert result[0]["text"] == "サクラの虫を求めて来た"
    assert result[0]["first_at"] == "2026-07-01T08:00:00"


def test_append_events_none_log_treated_as_empty():
    events = [{"bird_id": "shijukara", "reason_text": "サクラの虫を求めて来た", "arrived_at": "2026-07-01T08:00:00"}]
    result = eco_log.append_events(None, events)
    assert len(result) == 1


def test_append_events_dedupes_same_bird_and_text():
    log = [{"bird_id": "shijukara", "text": "サクラの虫を求めて来た", "first_at": "2026-07-01T08:00:00"}]
    events = [{"bird_id": "shijukara", "reason_text": "サクラの虫を求めて来た", "arrived_at": "2026-07-05T09:00:00"}]
    result = eco_log.append_events(log, events)
    assert len(result) == 1  # 重複は追加されない
    assert result[0]["first_at"] == "2026-07-01T08:00:00"  # 最初の記録のまま


def test_append_events_keeps_different_text_for_same_bird():
    log = [{"bird_id": "shijukara", "text": "サクラの虫を求めて来た", "first_at": "2026-07-01T08:00:00"}]
    events = [{"bird_id": "shijukara", "reason_text": "カエデの実を求めて来た", "arrived_at": "2026-07-05T09:00:00"}]
    result = eco_log.append_events(log, events)
    assert len(result) == 2
    texts = {e["text"] for e in result}
    assert texts == {"サクラの虫を求めて来た", "カエデの実を求めて来た"}


def test_append_events_skips_missing_bird_id_or_text():
    events = [
        {"bird_id": "", "reason_text": "テキスト", "arrived_at": "2026-07-01T08:00:00"},
        {"bird_id": "shijukara", "reason_text": "", "arrived_at": "2026-07-01T08:00:00"},
        {"bird_id": "shijukara", "reason_text": None, "arrived_at": "2026-07-01T08:00:00"},
    ]
    result = eco_log.append_events([], events)
    assert result == []


def test_append_events_handles_datetime_arrived_at():
    events = [{"bird_id": "mejiro", "reason_text": "花の蜜を求めて来た", "arrived_at": datetime(2026, 7, 3, 10, 30, 0)}]
    result = eco_log.append_events([], events)
    assert result[0]["first_at"] == "2026-07-03T10:30:00"


def test_append_events_does_not_mutate_original_log():
    log = [{"bird_id": "shijukara", "text": "既存の記録", "first_at": "2026-07-01T08:00:00"}]
    original_len = len(log)
    events = [{"bird_id": "mejiro", "reason_text": "新しい記録", "arrived_at": "2026-07-05T09:00:00"}]
    result = eco_log.append_events(log, events)
    assert len(log) == original_len  # 元のログは変更されない(新しいリストを返す)
    assert len(result) == 2


def test_append_events_no_events_returns_log_copy():
    log = [{"bird_id": "shijukara", "text": "既存の記録", "first_at": "2026-07-01T08:00:00"}]
    result = eco_log.append_events(log, [])
    assert result == log
    result_none = eco_log.append_events(log, None)
    assert result_none == log


def test_entries_for_bird_filters_and_sorts():
    log = [
        {"bird_id": "shijukara", "text": "2番目に記録", "first_at": "2026-07-05T09:00:00"},
        {"bird_id": "mejiro", "text": "別の鳥の記録", "first_at": "2026-07-02T09:00:00"},
        {"bird_id": "shijukara", "text": "1番目に記録", "first_at": "2026-07-01T08:00:00"},
    ]
    entries = eco_log.entries_for_bird(log, "shijukara")
    assert len(entries) == 2
    assert entries[0]["text"] == "1番目に記録"
    assert entries[1]["text"] == "2番目に記録"


def test_entries_for_bird_empty_when_no_match():
    assert eco_log.entries_for_bird([], "shijukara") == []
    assert eco_log.entries_for_bird(None, "shijukara") == []
    log = [{"bird_id": "mejiro", "text": "x", "first_at": "2026-07-01"}]
    assert eco_log.entries_for_bird(log, "shijukara") == []


def test_is_founding_record_true_for_first_entry_when_observed():
    entries = [
        {"bird_id": "shijukara", "text": "1番目", "first_at": "2026-07-01T08:00:00"},
        {"bird_id": "shijukara", "text": "2番目", "first_at": "2026-07-05T09:00:00"},
    ]
    assert eco_log.is_founding_record(entries[0], entries, "2026-07-01T08:00:00") is True
    assert eco_log.is_founding_record(entries[1], entries, "2026-07-01T08:00:00") is False


def test_is_founding_record_false_without_observed_first():
    entries = [{"bird_id": "shijukara", "text": "1番目", "first_at": "2026-07-01T08:00:00"}]
    assert eco_log.is_founding_record(entries[0], entries, None) is False
    assert eco_log.is_founding_record(entries[0], entries, "") is False


def test_is_founding_record_false_for_empty_entries():
    entry = {"bird_id": "shijukara", "text": "1番目", "first_at": "2026-07-01T08:00:00"}
    assert eco_log.is_founding_record(entry, [], "2026-07-01T08:00:00") is False


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
