"""
test_ads.py - 広告UI土台(ads.py)の純粋ロジック単体テスト

実行: python3 toris_collection/tests/test_ads.py
依存なし(pytest 不要、stdlib のみ)。is_radio_active は
Streamlit にも依存しない純粋関数(render_* 側で遅延importしている)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ads  # noqa: E402


def test_radio_inactive_by_default():
    # ラジオを一度も開始していない(radio_readyキーが無い)状態では非活性
    assert ads.is_radio_active({}) is False


def test_radio_inactive_when_flag_false():
    assert ads.is_radio_active({"radio_ready": False}) is False


def test_radio_active_when_started():
    # radio.py の「🎙 ラジオを始める」ボタン押下後の状態を模す
    assert ads.is_radio_active({"radio_ready": True}) is True


def test_radio_active_ignores_unrelated_keys():
    state = {"biome": "kyoto", "radio_ready": True, "planted": ["sakura"]}
    assert ads.is_radio_active(state) is True


def test_is_radio_active_tolerates_object_without_get():
    # .get を持たないオブジェクトが渡っても例外を投げず False を返す(壊さない)
    class NoGet:
        pass

    assert ads.is_radio_active(NoGet()) is False


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
