"""
test_daily.py - 今日の庭(daily.py)の純粋ロジック単体テスト

実行: python3 toris_collection/tests/test_daily.py
依存なし(pytest 不要)。todays_bird は stdlib のみに依存する。
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import daily  # noqa: E402


BIRDS = {
    "shijukara":  {"name": "シジュウカラ", "biome_pref": ["kyoto"]},
    "mejiro":     {"name": "メジロ", "biome_pref": ["kyoto", "charlotte"]},
    "suzume":     {"name": "スズメ", "biome_pref": ["kyoto"]},
    "kookaburra": {"name": "ワライカワセミ", "biome_pref": ["sydney"]},
}

D1 = date(2026, 6, 11)
D2 = date(2026, 6, 12)


def test_deterministic_same_day_same_biome():
    # 同じ日・同じ土地なら常に同一(=全ユーザー共通の共有の瞬間)
    a = daily.todays_bird("kyoto", BIRDS, D1)
    b = daily.todays_bird("kyoto", BIRDS, D1)
    assert a == b


def test_changes_across_days():
    # 日が変われば「今日の一羽」は(ほぼ)入れ替わる。少なくとも複数日で同一固定ではない
    picks = {daily.todays_bird("kyoto", BIRDS, date(2026, 6, d)) for d in range(1, 28)}
    assert len(picks) >= 2  # 1種に張り付かない


def test_respects_biome():
    # 選ばれる鳥は必ずその土地に生息する種(kyoto の候補だけから出る)
    kyoto_ids = {"shijukara", "mejiro", "suzume"}
    for d in range(1, 29):
        assert daily.todays_bird("kyoto", BIRDS, date(2026, 6, d)) in kyoto_ids
    # sydney は kookaburra のみ → 常に kookaburra
    assert daily.todays_bird("sydney", BIRDS, D1) == "kookaburra"


def test_biome_with_no_birds_returns_none():
    assert daily.todays_bird("mars", BIRDS, D1) is None


def test_different_biomes_can_differ():
    # 同じ日でも土地ごとに別の「今日の一羽」を持てる
    kyoto = daily.todays_bird("kyoto", BIRDS, D1)
    charlotte = daily.todays_bird("charlotte", BIRDS, D1)
    assert kyoto in ("shijukara", "mejiro", "suzume")
    assert charlotte == "mejiro"  # charlotte は mejiro のみ


def test_is_met():
    observed = {"shijukara": {"count": 3}, "mejiro": {"count": 0}}
    assert daily.is_met("shijukara", observed) is True
    assert daily.is_met("mejiro", observed) is False    # count 0 は未会
    assert daily.is_met("suzume", observed) is False     # 記録なし
    assert daily.is_met("x", {}) is False


def test_seed_is_stable_per_day():
    assert daily.daily_seed(D1) == daily.daily_seed(D1)
    assert daily.daily_seed(D1) != daily.daily_seed(D2)


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
