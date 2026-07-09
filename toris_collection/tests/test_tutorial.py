"""
test_tutorial.py - 新規スタート向けチュートリアル(tutorial.py)の単体テスト

実行: python3 toris_collection/tests/test_tutorial.py
依存なし(pytest 不要、stdlib のみ)。resolve_step / advance_step / is_done /
step_content は Streamlit にも依存しない純粋関数。

Streamlit実挙動(バナー表示・スキップ・自動進行・復元ユーザーへの非表示)の確認は
別途 AppTest で実施済み(「壊さない検証」ステップ2、開発部の作業ログ参照)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tutorial  # noqa: E402


def test_resolve_step_stays_at_land_step_without_action():
    # ステップ0(土地を選ぶ)は、植物の有無に関わらずそのまま
    assert tutorial.resolve_step(0, []) == 0
    assert tutorial.resolve_step(0, ["sakura"]) == 0


def test_resolve_step_auto_advances_when_planted():
    # ステップ1(植物を植える)は、実際に1つ植えたら自動でステップ2へ
    assert tutorial.resolve_step(1, []) == 1
    assert tutorial.resolve_step(1, ["sakura"]) == 2


def test_resolve_step_final_step_is_stable():
    assert tutorial.resolve_step(2, []) == 2
    assert tutorial.resolve_step(2, ["sakura"]) == 2


def test_advance_step_moves_forward_one_at_a_time():
    assert tutorial.advance_step(0) == 1
    assert tutorial.advance_step(1) == 2


def test_advance_step_caps_at_total_steps():
    # 最終ステップの「次へ」を連打しても TOTAL_STEPS を超えない
    assert tutorial.advance_step(2) == tutorial.TOTAL_STEPS
    assert tutorial.advance_step(tutorial.TOTAL_STEPS) == tutorial.TOTAL_STEPS
    assert tutorial.advance_step(99) == tutorial.TOTAL_STEPS


def test_is_done_only_at_or_past_total_steps():
    assert tutorial.is_done(0) is False
    assert tutorial.is_done(1) is False
    assert tutorial.is_done(2) is False
    assert tutorial.is_done(tutorial.TOTAL_STEPS) is True
    assert tutorial.is_done(tutorial.TOTAL_STEPS + 1) is True


def test_step_content_step0_mentions_land():
    content = tutorial.step_content(0, "京都(温帯)")
    assert "土地を選び" in content["title"]
    assert "京都(温帯)" in content["body"]
    assert content["next_label"]


def test_step_content_step1_mentions_planting():
    content = tutorial.step_content(1, "京都(温帯)")
    assert "植物を植え" in content["title"]
    assert "植える" in content["body"]


def test_step_content_final_step_has_finish_label_not_skip():
    content = tutorial.step_content(2, "京都(温帯)")
    assert "はじめる" in content["next_label"]
    # 強制ブロックの煽り文句(数字カウントダウン等)を持たない
    assert "しないと" not in content["body"]


def test_step_content_out_of_range_clamped():
    # 呼び出し側のバグで範囲外を渡しても例外にならず、最終案内相当を返す
    content_low = tutorial.step_content(-1, "京都(温帯)")
    content_high = tutorial.step_content(999, "京都(温帯)")
    assert content_low["title"]
    assert content_high["title"]


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
