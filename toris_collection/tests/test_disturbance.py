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

import i18n  # noqa: E402
import disturbance as dist  # noqa: E402

# 既定言語(EN)= 実際に出荷される表示。トーン検証は出荷言語に対して行う。
i18n.set_lang("en")


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
        assert "severity" in h


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


def test_disturbance_story_branches():
    ev = {"icon": "🌀", "label": "嵐"}
    # 倒れた植物があれば純減として語る(自動の植え直し・芽吹きは語らない)
    s1 = dist.disturbance_story(ev, ["ナラ"])
    assert "knocked down" in s1.lower()
    assert "sprout" not in s1.lower() and "new bud" not in s1.lower()
    # 何も倒れなければ「持ちこたえた」= held on
    s2 = dist.disturbance_story(ev, [])
    assert "held on" in s2.lower()


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
