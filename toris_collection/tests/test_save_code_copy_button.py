"""
test_save_code_copy_button.py - セーブコードのワンタップコピー機能(2026-07-10追記)の回帰テスト

実行: python3 toris_collection/tests/test_save_code_copy_button.py
依存なし(pytest 不要、stdlib のみ)。app.py はStreamlitランタイムに依存する
トップレベル実行文を含むため直接importせず、ソースをテキストとして検査する
(test_ads.py の `test_reward_js_template_contains_expected_admob_calls` と
同じ流儀)。実際のJS実行(クリップボードコピー)はNode --check + Playwrightで
別途確認する。
"""
import os

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_app_source():
    with open(APP_PATH, encoding="utf-8") as f:
        return f.read()


def test_copy_button_function_exists():
    src = _read_app_source()
    assert "_render_save_code_copy_button" in src


def test_copy_button_is_called_in_sidebar_backup_section():
    src = _read_app_source()
    assert "_render_save_code_copy_button(_save_code_str)" in src


def test_copy_button_has_three_stage_fallback():
    # Capacitorネイティブプラグイン → 標準Web API → execCommand の3段構え
    src = _read_app_source()
    assert "copyViaCapacitor" in src
    assert "copyViaWebApi" in src
    assert "copyViaExecCommand" in src
    assert "navigator.clipboard.writeText" in src
    assert "Capacitor.Plugins.Clipboard" in src
    assert "document.execCommand('copy')" in src


def test_copy_button_gives_success_and_failure_feedback():
    # 「押しても何も起こらない」ように見えないための必須要件
    src = _read_app_source()
    assert "コピーしました" in src
    assert "コピーできませんでした" in src


def test_copy_button_placed_before_download_button_as_primary():
    # ワンタップコピーを「主要な手段として前面に出す」(CEO依頼)
    # ソース上、_render_save_code_copy_button の呼び出しが
    # st.download_button("⬇️ セーブコードを書き出す" より前にあること
    src = _read_app_source()
    copy_idx = src.index("_render_save_code_copy_button(_save_code_str)")
    download_idx = src.index('"⬇️ セーブコードを書き出す"')
    assert copy_idx < download_idx


def test_existing_fallback_ui_still_present():
    # 既存の「選択してコピーできるテキスト表示」「アプリ内共有ボタン」は残す
    src = _read_app_source()
    assert "st.code(_save_code_str" in src
    assert "_inject_native_save_code_share_button(_save_code_str)" in src


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
