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
当時は app.py の `_inject_local_restore_check()` と同じ「トップwindowの
documentに<script>要素を注入してそちらの実行コンテキストで遷移させる」手法に
統一していた。

2026-07-11追記(P1修正): 「儀式で会った鳥が図鑑に反映されないことがある」という
CEO報告の根本原因対応。ads.py の広告結果伝達で判明したのと同じ理由
(実機PlaywrightでCDPのページライフサイクル(frozen→active)により、視聴/観察の
確定イベントの「その場」でトップウィンドウへ直接ナビゲーションを試みる操作
自体が、タブ切り替え・バックグラウンド化と重なるタイミングでは不安定になる
ことを確認済み、ads.py モジュールdocstring「2026-07-10 追記(P1修正)」参照)で、
ritual.py の `saveObservations()` からもナビゲーションを完全に無くし、
window.top.localStorage への書き込みだけに留めた。実際にPython側へ届ける
ナビゲーションは app.py の `_inject_ritual_result_check()`
(`_inject_ad_result_check()` と同じパターン、毎回のrerunで動く独立した
ポーリング)に委譲する。
"""
import os
import re

_RITUAL_PATH = os.path.join(os.path.dirname(__file__), "..", "ritual.py")
_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _read_source() -> str:
    with open(_RITUAL_PATH, encoding="utf-8") as f:
        return f.read()


def _read_app_source() -> str:
    with open(_APP_PATH, encoding="utf-8") as f:
        return f.read()


def _extract_save_observations_body() -> str:
    """saveObservations() の関数本体だけを取り出す(モジュールdocstringの
    経緯説明文と、実際のJSコードとを区別するため。ads.py の
    `_ADMOB_REWARD_JS_TEMPLATE`(独立した文字列定数)をそのまま assert 対象に
    できるのと違い、ritual.py はJSが描画関数内のf-stringに埋め込まれている
    ため、正規表現で関数本体を切り出してから assert する)。
    """
    src = _read_source()
    m = re.search(
        r"function saveObservations\(\) \{\{.*?\n        \}\}\n", src, re.S
    )
    assert m, "saveObservations() が ritual.py に見つからない"
    return m.group(0)


def test_does_not_directly_assign_top_location_href():
    src = _read_source()
    assert "window.top.location.href =" not in src
    assert "window.top.location.href=" not in src


def test_save_observations_no_longer_navigates_from_ritual_js():
    # 2026-07-11追記(P1修正): 実機PlaywrightでCDPのページライフサイクル
    # (frozen→active)を再現したところ、観察確定イベントの「その場」で
    # トップウィンドウへ直接ナビゲーションを試みる旧実装(script要素注入)は
    # 不安定(成功したり失敗したりする)ことを確認した。ritual.py はもはや
    # ナビゲーションを一切試みず、localStorageへの書き込みだけを行うこと
    # (ナビゲーションはapp.py側の独立したポーリングに委譲)。
    body = _extract_save_observations_body()
    assert "window.top.document" not in body
    assert "createElement('script')" not in body
    assert "appendChild(script)" not in body


def test_save_observations_writes_pending_obs_to_top_local_storage():
    body = _extract_save_observations_body()
    assert "window.top.localStorage.setItem('toris_ritual_pending_obs'" in body
    # ids/ts を持つペイロードであること(app.py側の読み取りと整合)
    assert "ids: ids" in body
    assert "ts: Date.now()" in body


def test_app_injects_ritual_result_check_that_polls_and_navigates():
    # app.py 側: _inject_ritual_result_check() が localStorage をポーリングし、
    # 見つけたら script要素注入によるトップウィンドウナビゲーションを行う
    # (_inject_ad_result_check() と同じパターン)。
    src = _read_app_source()
    assert "_inject_ritual_result_check" in src
    assert "toris_ritual_pending_obs" in src
    assert "setInterval(tryDeliver" in src
    assert "removeItem(KEY)" in src  # 二重処理防止(読み取った時点で削除)
    assert "createElement('script')" in src
    assert "ritual_obs" in src


def test_still_reports_ritual_obs_query_param_end_to_end():
    # 修正後もPython側への片道経路(?ritual_obs=...)自体は変わっていないこと
    # (受け口は app.py の _handle_ritual_observation() のまま)。
    app_src = _read_app_source()
    assert "_handle_ritual_observation" in app_src
    assert "ritual_obs" in app_src


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
