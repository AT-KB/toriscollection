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


# ── AdMob(2026-07-08追記) ────────────────────────────────────────────

def test_admob_disabled_by_default():
    # secrets/環境変数を何も設定していないテスト実行環境では、AdMobは既定で無効
    # (壊さない=既存の広告プレースホルダー挙動を変えないことの保証)
    assert ads.ADMOB_ENABLED is False


def test_load_admob_enabled_reads_env_var():
    orig = os.environ.get("ADMOB_ENABLED")
    try:
        os.environ["ADMOB_ENABLED"] = "1"
        assert ads._load_admob_enabled() is True
        os.environ["ADMOB_ENABLED"] = "0"
        assert ads._load_admob_enabled() is False
    finally:
        if orig is None:
            os.environ.pop("ADMOB_ENABLED", None)
        else:
            os.environ["ADMOB_ENABLED"] = orig


def test_load_admob_banner_unit_id_falls_back_to_google_test_id():
    orig = os.environ.get("ADMOB_BANNER_UNIT_ID")
    try:
        os.environ.pop("ADMOB_BANNER_UNIT_ID", None)
        # 未設定時はGoogle公式のテスト用バナーID(実収益が発生しない安全な値)
        assert ads._load_admob_banner_unit_id() == ads._ADMOB_TEST_BANNER_UNIT_ID
    finally:
        if orig is not None:
            os.environ["ADMOB_BANNER_UNIT_ID"] = orig


def test_load_admob_banner_unit_id_prefers_env_override():
    orig = os.environ.get("ADMOB_BANNER_UNIT_ID")
    try:
        os.environ["ADMOB_BANNER_UNIT_ID"] = "ca-app-pub-1234/5678"
        assert ads._load_admob_banner_unit_id() == "ca-app-pub-1234/5678"
    finally:
        if orig is None:
            os.environ.pop("ADMOB_BANNER_UNIT_ID", None)
        else:
            os.environ["ADMOB_BANNER_UNIT_ID"] = orig


def test_render_admob_banner_is_noop_when_disabled():
    # ADMOB_ENABLED=False のときは streamlit.components すら import せず即return する
    # (Streamlit未起動のテスト環境でも例外を出さないことの確認)
    orig = ads.ADMOB_ENABLED
    try:
        ads.ADMOB_ENABLED = False
        ads.render_admob_banner({"radio_ready": False})  # 例外が出なければOK
    finally:
        ads.ADMOB_ENABLED = orig


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
