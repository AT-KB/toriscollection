"""
test_absence_loop_item_reason.py - 広告リワード「今日の庭アイテム」が
生態ログ(GloBI由来の「なぜ来たか」)を汚さないことの回帰テスト。

実行: python3 toris_collection/tests/test_absence_loop_item_reason.py
absence_loop.py は engine.py 経由で networkx に依存する
(requirements.txt に既存の必須依存として記載済み)ため、他の tests/test_*.py
より依存が1つ多いが、対象ロジック(build_reason_text)自体はBIRDS辞書と
文字列整形だけの純粋関数。

確認すること:
  1. 食物網由来の経路(incoming_paths)が実在する場合、item_hint を渡しても
     一切使われない(=本物の生態学的理由がアイテムの宣伝文言で薄められない)。
  2. 食物網由来の経路が空(=食物網では説明できない到着)のとき、item_hint が
     無ければ従来通りの控えめな文(「が立ち寄りました。」)のまま。
  3. 食物網由来の経路が空で、かつ item_hint がある場合だけ、正直に
     「〇〇に誘われて立ち寄りました。」と表現する(理由の捏造をしない)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import absence_loop  # noqa: E402


def test_real_food_path_ignores_item_hint():
    info = {
        "incoming_paths": [("plant", "sakura", 0.8)],
    }
    reason, plant_id, insect_id = absence_loop.build_reason_text(
        "mejiro", info, item_hint="バードフィーダー"
    )
    assert "バードフィーダー" not in reason, \
        "食物網由来の理由があるのに、アイテム名が生態ログの理由文に混入した"
    assert "サクラ" in reason
    assert plant_id == "sakura"


def test_no_food_path_and_no_item_hint_stays_generic():
    info = {"incoming_paths": []}
    reason, plant_id, insect_id = absence_loop.build_reason_text("mejiro", info)
    assert reason == "メジロが立ち寄りました。"
    assert plant_id == "" and insect_id == ""


def test_no_food_path_with_item_hint_is_honest_not_fabricated():
    info = {"incoming_paths": []}
    reason, plant_id, insect_id = absence_loop.build_reason_text(
        "mejiro", info, item_hint="バードフィーダー"
    )
    assert reason == "メジロが、バードフィーダーに誘われて立ち寄りました。"
    # 植物・昆虫の関連IDは捏造しない(空のまま)
    assert plant_id == "" and insect_id == ""


if __name__ == "__main__":
    test_real_food_path_ignores_item_hint()
    test_no_food_path_and_no_item_hint_stays_generic()
    test_no_food_path_with_item_hint_is_honest_not_fabricated()
    print("OK: すべての生態ログ非汚染テストがパスしました。")
