"""
test_tab_persistence.py - タブ選択状態の保持(app.py 内 _inject_active_tab_persistence)
の回帰テスト。

実行: python3 toris_collection/tests/test_tab_persistence.py
依存なし(pytest 不要、stdlib のみ)。app.py 自体は streamlit の実行コンテキスト無しに
importできない(モジュールトップレベルで st.tabs() 等を呼ぶため)ので、
ritual.py/ads.py の既存テストと同じ手法(ソースをテキストとして読んで既知の
バグパターンへの後退が無いかだけを確認する)を踏襲する。

背景(2026-07-11・CEO報告「毎回ラジオ画面/ログイン画面に戻る」): ローカルセーブ
自動復元・広告視聴結果受信・儀式の観察記録は、いずれも「JSがtopウィンドウを
`window.location.href` 経由でフルリロードし、Python側が `st.query_params` で
受け取る」という片道パターンを使っている。`st.tabs()` は選択中のタブを
フロントエンドの内部状態としてのみ持つため、フルリロードのたびに最初のタブ
(🎙 ラジオ)に戻ってしまっていた。`_inject_active_tab_persistence()` は
`st.tabs()` 自体・タブ構成・コアループには一切手を入れず、フロントエンドの
DOM操作(タブクリックをlocalStorageに記録→ページ読み込み後に該当タブを
`.click()`して復元)だけで表示状態を補助する。

実際の「フルリロードをまたいでタブが維持されるか」という動的な確認は、
ローカルのStreamlitサーバー起動+Playwrightで別途実施済み(このテストファイルには
含まない。壊さない検証の4ステップ内・スクラッチパッドのスクリプトで実施)。
"""
import os

_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_source() -> str:
    with open(_APP_PATH, encoding="utf-8") as f:
        return f.read()


def test_active_tab_persistence_function_exists():
    src = _read_source()
    assert "_inject_active_tab_persistence" in src
    assert "def _inject_active_tab_persistence():" in src


def test_active_tab_persistence_is_called_right_after_tabs_definition():
    src = _read_source()
    tabs_idx = src.index("tab_radio, tab_home, tab_plant, tab_sim, tab_birds, tab_mementos, tab_network, tab_help = st.tabs(")
    # 関数定義自体("def _inject_active_tab_persistence():")にも同じ文字列が
    # 部分一致してしまうため、最後(=呼び出し箇所)を rindex で拾う
    call_idx = src.rindex("_inject_active_tab_persistence()")
    def_idx = src.index("def _inject_active_tab_persistence():")
    assert def_idx < tabs_idx  # 定義はタブ生成より前にある
    assert tabs_idx < call_idx  # 呼び出しはタブ生成の直後にある


def test_uses_role_tab_selector_matching_streamlit_dom():
    # 実機Playwright確認済みのDOM構造(role="tab" / aria-selected)に基づくセレクタ
    src = _read_source()
    assert 'querySelectorAll(\'[role="tab"]\')' in src
    assert "aria-selected" in src


def test_saves_and_restores_via_parent_local_storage():
    src = _read_source()
    assert "_ACTIVE_TAB_STORAGE_KEY" in src
    assert "window.parent.localStorage.setItem" in src
    assert "window.parent.localStorage.getItem" in src


def test_does_not_touch_tabs_widget_construction():
    # タブの本数・ラベル・並び順(コアループ)は変更していないこと。
    # EN/JA 切替対応で各ラベルは t(...) でラップされたが、日本語原文・並び順は不変。
    src = _read_source()
    assert (
        '[t("🎙 ラジオ"), t("🏞️ 庭の様子"), t("🌱 植える"), t("🧪 シミュ"), t("📖 図鑑"),\n'
        '     t("🎁 落とし物"), t("🕸️ ネットワーク"), t("❓ 使い方")]'
    ) in src


def test_restore_polls_for_tab_dom_and_gives_up_gracefully():
    # タブDOMがまだ描画されていない場合に備えたポーリング+タイムアウト(壊さない)
    src = _read_source()
    assert "restoreInterval" in src
    assert "clearInterval(restoreInterval)" in src


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
