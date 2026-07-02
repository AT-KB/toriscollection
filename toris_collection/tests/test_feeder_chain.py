"""
test_feeder_chain.py - 餌台→リス→Hawk→警戒鳥抑制の連鎖(純粋ロジック)。

実行: python3 toris_collection/tests/test_feeder_chain.py
依存なし(feeder_chain は stdlib のみ)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import feeder_chain as fc  # noqa: E402


def test_open_feeder_draws_squirrel():
    # 開放型の餌台(種)→ リスが来る
    assert fc.animals_present(["feeder_open"], []) == ["gray_squirrel"]


def test_cage_feeder_excludes_squirrel():
    # かご型のみ → 大型が届かず、リスは来ない
    assert fc.animals_present(["feeder_cage"], []) == []


def test_sunflower_alone_draws_squirrel():
    # ヒマワリの種だけでもリスは来る(large_access 扱い無しでも seed は届く…
    # が needs_large_access なので、種のみ=地面採餌可として large は付かない)
    # → 種はあるが large_access が無いので来ない(かご型と同じ扱い)
    assert fc.animals_present([], ["sunflower"]) == []
    # 堅果(白樫)は地面に落ちる=large_access が付き、リスが来る
    assert fc.animals_present([], ["white_oak"]) == ["gray_squirrel"]


def test_squirrel_draws_hawk():
    animals = fc.animals_present(["feeder_open"], [])
    assert fc.raptors_present(animals) == ["cooper_hawk"]


def test_no_squirrel_no_hawk():
    assert fc.raptors_present([]) == []


def test_hawk_suppresses_wary_birds():
    raptors = ["cooper_hawk"]
    # 警戒心の強い鳥(0.6)は大きく抑制、臆病でない鳥(0.1)はほとんど影響なし
    shy = fc.wary_arrival_multiplier(0.6, raptors)
    bold = fc.wary_arrival_multiplier(0.1, raptors)
    assert shy < bold
    assert 0.0 <= shy < 0.7          # 0.6*0.7=0.42 抑制 → 0.58 付近
    assert bold > 0.9


def test_no_hawk_no_suppression():
    assert fc.wary_arrival_multiplier(0.9, []) == 1.0


def test_resolve_full_chain():
    r = fc.resolve(["feeder_open"], ["sunflower"])
    assert r["animals"] == ["gray_squirrel"]
    assert r["raptors"] == ["cooper_hawk"]
    # かご型 + ヒマワリのみ → 連鎖は起きない(狙った小鳥を守れる庭)
    r2 = fc.resolve(["feeder_cage"], ["sunflower"])
    assert r2["animals"] == [] and r2["raptors"] == []


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
