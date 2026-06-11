"""
test_disturbance.py - 撹乱・遷移モデルの単体テスト(純粋ロジック・I/O なし)

実行: python3 toris_collection/tests/test_disturbance.py
依存なし(pytest 不要)。disturbance.py は stdlib のみに依存するため、
gspread 等の重い依存を引かずに高速に回る。
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import disturbance as dist  # noqa: E402


# テスト用の植物データ(感受性・遷移役割つき)
PLANTS = {
    "oak":     {"name": "ナラ", "biome": ["kyoto"], "successional_role": "late",
                "disturbance_sensitivity": 0.2},
    "pioneer": {"name": "アカメガシワ", "biome": ["kyoto"], "successional_role": "pioneer",
                "disturbance_sensitivity": 0.9},
    "grass":   {"name": "ススキ", "biome": ["kyoto"]},  # 形質未設定=既定値
    "gum":     {"name": "ユーカリ", "biome": ["sydney"], "successional_role": "pioneer"},
}


def test_plant_sensitivity_default_and_clamp():
    assert dist.plant_sensitivity("grass", PLANTS) == dist.DEFAULT_SENSITIVITY
    assert dist.plant_sensitivity("oak", PLANTS) == 0.2
    assert dist.plant_sensitivity("unknown", PLANTS) == dist.DEFAULT_SENSITIVITY


def test_is_pioneer():
    assert dist.is_pioneer("pioneer", PLANTS) is True
    assert dist.is_pioneer("grass", PLANTS) is True       # 未設定=候補
    assert dist.is_pioneer("oak", PLANTS) is False        # late=候補外


def test_roll_disturbance_frequency_and_validity():
    rng = random.Random(0)
    hits = [dist.roll_disturbance(rng) for _ in range(2000)]
    fired = [h for h in hits if h is not None]
    # 基礎確率 0.10 前後(低頻度であること)
    rate = len(fired) / len(hits)
    assert 0.06 < rate < 0.15, f"撹乱頻度が想定外: {rate}"
    # 返るタイプは必ず定義済み
    for h in fired:
        assert h["type"] in dist.DISTURBANCES
        assert "severity" in h and "recovery" in h


def test_apply_disturbance_never_wipes_all():
    rng = random.Random(1)
    planted = ["pioneer", "pioneer", "pioneer"]  # 感受性0.9
    storm = {"severity": 1.0}  # 最大強度でも
    for _ in range(50):
        removed = dist.apply_disturbance(planted, storm, PLANTS, rng)
        assert len(removed) < len(planted), "庭が全滅してはいけない(最後の1本は残す)"


def test_apply_disturbance_respects_sensitivity():
    rng = random.Random(2)
    # 感受性0の木は倒れない
    tough = {"name": "鉄の木", "disturbance_sensitivity": 0.0}
    data = {"iron": tough}
    removed = dist.apply_disturbance(["iron"] * 20, {"severity": 1.0}, data, rng)
    assert removed == []


def test_roll_succession_picks_unplanted_pioneer_in_biome():
    rng = random.Random(3)
    # recovery=1.0 で必ず芽吹く。kyoto で未植栽のパイオニア = pioneer/grass
    planted = ["oak"]
    got = set()
    for _ in range(50):
        s = dist.roll_succession(planted, "kyoto", PLANTS, {"recovery": 1.0}, rng)
        assert s is not None
        got.add(s)
    assert got <= {"pioneer", "grass"}, f"想定外の芽吹き: {got}"
    assert "oak" not in got        # late は芽吹かない
    assert "gum" not in got        # 別バイオームは出ない


def test_roll_succession_excludes_just_fallen():
    rng = random.Random(9)
    # grass が倒れたばかりなら、その場で grass は生え直さない(移ろいになる)
    planted = ["oak"]
    for _ in range(50):
        s = dist.roll_succession(planted, "kyoto", PLANTS, {"recovery": 1.0}, rng,
                                 exclude=["grass"])
        assert s == "pioneer", f"倒れた grass を除外できていない: {s}"


def test_roll_succession_recovery_zero_never_sprouts():
    rng = random.Random(4)
    for _ in range(50):
        assert dist.roll_succession(["oak"], "kyoto", PLANTS,
                                    {"recovery": 0.0}, rng) is None


def test_disturbance_story_branches():
    ev = {"icon": "🌀", "label": "嵐"}
    s1 = dist.disturbance_story(ev, ["ナラ"], "アカメガシワ")
    assert "倒れた" in s1 and "芽吹き" in s1
    s2 = dist.disturbance_story(ev, ["ナラ"], None)
    assert "倒れた" in s2 and "新しい芽" in s2
    s3 = dist.disturbance_story(ev, [], "アカメガシワ")
    assert "芽吹いた" in s3
    s4 = dist.disturbance_story(ev, [], None)
    assert "持ちこたえた" in s4


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
