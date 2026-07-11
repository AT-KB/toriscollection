"""
test_ritual.py - 儀式UI(ritual.py)のJSテンプレート回帰テスト

実行: python3 toris_collection/tests/test_ritual.py
依存なし(pytest 不要、stdlib のみ)。ritual.py 自体は streamlit / xc_client に
依存する重い描画関数のため import して呼び出すことはせず、ソースをテキストとして
読んで既知のバグパターンへの後退が無いかだけを確認する(ads.py の
test_no_rare_bird_probability_wording_remains_in_module と同じ手法)。

2026-07-10追記: sandbox iframe から top window を直接遷移できない不具合
(「Unsafe attempt to initiate navigation ... sandboxed」SecurityError)の修正の
回帰テスト。components.html() のiframeは sandbox に allow-top-navigation 系
フラグを持たないため、`window.top.location.href = ...` の直接代入は拒否される。
app.py の `_inject_local_restore_check()` と同じ「トップwindowのdocumentに
<script>要素を注入してそちらの実行コンテキストで遷移させる」手法に統一した。
"""
import os

_RITUAL_PATH = os.path.join(os.path.dirname(__file__), "..", "ritual.py")


def _read_source() -> str:
    with open(_RITUAL_PATH, encoding="utf-8") as f:
        return f.read()


def test_does_not_directly_assign_top_location_href():
    src = _read_source()
    assert "window.top.location.href =" not in src
    assert "window.top.location.href=" not in src


def test_injects_script_into_top_document_for_navigation():
    src = _read_source()
    assert "window.top.document" in src
    assert "createElement('script')" in src
    assert "appendChild(script)" in src


def test_still_reports_ritual_obs_query_param():
    # 修正後もPython側への片道経路(?ritual_obs=...)自体は変わっていないこと
    src = _read_source()
    assert "ritual_obs" in src


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
