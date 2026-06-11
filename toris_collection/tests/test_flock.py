"""
test_flock.py - 群れサイズモデルの単体テスト(純粋ロジック・I/O なし)

実行: python3 toris_collection/tests/test_flock.py
依存なし(pytest 不要)。flock.py は stdlib のみに依存する。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import flock as flk  # noqa: E402


# テスト用の鳥データ(rarity と任意の flock_max)
BIRDS = {
    "sparrow": {"name": "スズメ", "rarity": 0.1},                 # 普通種 → cap 3
    "tit":     {"name": "シジュウカラ", "rarity": 0.5},           # 中間 → cap 2
    "eagle":   {"name": "ワシ", "rarity": 0.9},                   # レア → cap 1
    "forced":  {"name": "強制群れ", "rarity": 0.9, "flock_max": 3},  # 明示上書き
    "capped":  {"name": "上限超過", "rarity": 0.1, "flock_max": 9},  # MAX_CAP に丸める
    "bad":     {"name": "壊れ値", "rarity": "x", "flock_max": "y"},  # 不正値は無視
}


def test_flock_cap_from_rarity():
    assert flk.flock_cap("sparrow", BIRDS) == 3
    assert flk.flock_cap("tit", BIRDS) == 2
    assert flk.flock_cap("eagle", BIRDS) == 1


def test_flock_cap_explicit_override():
    # レアでも flock_max=3 が優先される
    assert flk.flock_cap("forced", BIRDS) == 3


def test_flock_cap_clamps_to_max():
    assert flk.flock_cap("capped", BIRDS) == flk.MAX_CAP


def test_flock_cap_bad_values_fall_back():
    # rarity も flock_max も不正 → 既定の rarity=0.5 相当 (cap 2)
    assert flk.flock_cap("bad", BIRDS) == 2
    # 未知IDは rarity 既定 0.5 → cap 2
    assert flk.flock_cap("unknown", BIRDS) == 2


def test_flock_size_solitary_always_one():
    # cap=1 の種は観察回数がいくつでも常に1
    for c in (0, 1, 5, 99):
        assert flk.flock_size("eagle", c, BIRDS) == 1


def test_flock_size_grows_with_familiarity():
    # スズメ(cap3): 観察が増えると群れが育つ
    assert flk.flock_size("sparrow", 0, BIRDS) == 1
    assert flk.flock_size("sparrow", flk.GROWTH_EVERY, BIRDS) == 2
    assert flk.flock_size("sparrow", flk.GROWTH_EVERY * 2, BIRDS) == 3


def test_flock_size_never_exceeds_cap():
    # シジュウカラ(cap2): どれだけ会っても2で頭打ち
    assert flk.flock_size("tit", 1000, BIRDS) == 2
    # スズメ(cap3): 同上
    assert flk.flock_size("sparrow", 1000, BIRDS) == 3


def test_flock_size_handles_bad_count():
    # count が不正でも落ちずに最小1を返す
    assert flk.flock_size("sparrow", None, BIRDS) == 1
    assert flk.flock_size("sparrow", -5, BIRDS) == 1


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
