"""
test_community.py - 集合アトラス集計の単体テスト(純粋ロジック・I/O なし)

実行: python3 toris_collection/tests/test_community.py
依存なし(pytest 不要)。aggregate_atlas は stdlib のみに依存する。
streamlit を import で引かないよう、community からロジック関数だけを取り出す。
"""
import os
import sys
import types
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# community.py は streamlit を import するため、テストでは軽量スタブを挿す
if "streamlit" not in sys.modules:
    _st = types.ModuleType("streamlit")
    _st.cache_data = lambda *a, **k: (lambda f: f)  # デコレータを素通し
    sys.modules["streamlit"] = _st

import community as com  # noqa: E402


BIRDS = {
    "shijukara": {"name": "シジュウカラ", "biome_pref": ["kyoto"]},
    "mejiro":    {"name": "メジロ", "biome_pref": ["kyoto", "charlotte"]},
    "kookaburra": {"name": "ワライカワセミ", "biome_pref": ["sydney"]},
}

TODAY = date(2026, 6, 11)
RECENT = (TODAY - timedelta(days=3)).isoformat() + "T08:00:00"
OLD = (TODAY - timedelta(days=60)).isoformat() + "T08:00:00"


def _row(tid, bid, count, last):
    # 列名が揺れても拾えることを確認するため、あえて一般的でない列名を混ぜる
    return {"tester_id": tid, "bird_id": bid,
            "first_seen_at": OLD, "last_seen_at": last, "visit_count": count}


def test_gardens_counts_distinct_testers():
    rows = [
        _row("a", "shijukara", 3, RECENT),
        _row("b", "shijukara", 1, RECENT),
        _row("a", "mejiro", 2, RECENT),  # 同じ tester a の別種
    ]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    assert out["gardens"] == 2  # a, b の2庭(重複しない)


def test_species_grouped_by_biome():
    rows = [_row("a", "mejiro", 1, RECENT)]  # mejiro は kyoto と charlotte
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    assert "mejiro" in [e["bird_id"] for e in out["biomes"]["kyoto"]]
    assert "mejiro" in [e["bird_id"] for e in out["biomes"]["charlotte"]]
    assert "sydney" not in out["biomes"]


def test_garden_count_and_sightings_aggregate():
    rows = [
        _row("a", "shijukara", 3, RECENT),
        _row("b", "shijukara", 4, RECENT),
    ]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    entry = out["biomes"]["kyoto"][0]
    assert entry["bird_id"] == "shijukara"
    assert entry["gardens"] == 2       # 2庭が迎えた
    assert entry["sightings"] == 7     # 3 + 4


def test_sorted_by_garden_count_desc():
    rows = [
        _row("a", "shijukara", 1, RECENT),
        _row("b", "shijukara", 1, RECENT),  # shijukara: 2庭
        _row("a", "mejiro", 1, RECENT),     # mejiro: 1庭
    ]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    kyoto = out["biomes"]["kyoto"]
    assert kyoto[0]["bird_id"] == "shijukara"  # 多い順
    assert kyoto[1]["bird_id"] == "mejiro"


def test_recent_flag():
    rows = [
        _row("a", "shijukara", 1, RECENT),
        _row("b", "mejiro", 1, OLD),
    ]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    by_id = {e["bird_id"]: e for e in out["biomes"]["kyoto"]}
    assert by_id["shijukara"]["recent"] is True
    assert by_id["mejiro"]["recent"] is False


def test_unknown_bird_and_blank_rows_ignored():
    rows = [
        _row("a", "ghost_bird", 1, RECENT),  # birds_data に無い
        {"tester_id": "", "bird_id": "shijukara"},  # tester 空
        {"tester_id": "a", "bird_id": ""},           # bird 空
    ]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    assert out["gardens"] == 0
    assert out["biomes"] == {}


def test_no_individual_identity_leaks():
    # 出力に tester_id が一切含まれないこと(匿名性の保証)
    rows = [_row("secret_user", "shijukara", 1, RECENT)]
    out = com.aggregate_atlas(rows, BIRDS, today=TODAY)
    flat = repr(out)
    assert "secret_user" not in flat


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
