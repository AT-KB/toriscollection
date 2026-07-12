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


# ── リワード広告(実SDK接続、2026-07-08追記) ────────────────────────────

def test_load_admob_rewarded_unit_id_falls_back_to_google_test_id():
    orig = os.environ.get("ADMOB_REWARDED_UNIT_ID")
    try:
        os.environ.pop("ADMOB_REWARDED_UNIT_ID", None)
        # 未設定時はGoogle公式のテスト用リワード広告ID(実収益が発生しない安全な値)
        assert ads._load_admob_rewarded_unit_id() == ads._ADMOB_TEST_REWARDED_UNIT_ID
    finally:
        if orig is not None:
            os.environ["ADMOB_REWARDED_UNIT_ID"] = orig


def test_load_admob_rewarded_unit_id_prefers_env_override():
    orig = os.environ.get("ADMOB_REWARDED_UNIT_ID")
    try:
        os.environ["ADMOB_REWARDED_UNIT_ID"] = "ca-app-pub-9999/8888"
        assert ads._load_admob_rewarded_unit_id() == "ca-app-pub-9999/8888"
    finally:
        if orig is None:
            os.environ.pop("ADMOB_REWARDED_UNIT_ID", None)
        else:
            os.environ["ADMOB_REWARDED_UNIT_ID"] = orig


def test_render_pending_ad_loader_noop_when_disabled():
    # ADMOB_ENABLED=False(既定)では、pendingが積まれていても何もせず False
    # (Streamlit未起動のテスト環境でも例外を出さないことの確認・壊さない)
    orig = ads.ADMOB_ENABLED
    try:
        ads.ADMOB_ENABLED = False
        state = {"ads_pending_garden_item": {"nonce": "abc", "item_id": "feeder"}}
        assert ads.render_pending_ad_loader(state, "ads_pending_garden_item") is False
    finally:
        ads.ADMOB_ENABLED = orig


def test_render_pending_ad_loader_noop_when_no_pending():
    # ADMOB_ENABLED=True でも pending が無ければ何もせず False
    orig = ads.ADMOB_ENABLED
    try:
        ads.ADMOB_ENABLED = True
        assert ads.render_pending_ad_loader({}, "ads_pending_garden_item") is False
    finally:
        ads.ADMOB_ENABLED = orig


def test_reward_js_template_contains_expected_admob_calls():
    # 広告視聴イベント名・API呼び出しがテンプレートに含まれているか(タイプミス防止)。
    # 実際のJS実行はNode --check + Playwrightで別途確認する。
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    for token in (
        "prepareRewardVideoAd", "showRewardVideoAd",
        "onRewardedVideoAdReward", "onRewardedVideoAdDismissed",
        "onRewardedVideoAdFailedToShow", "onRewardedVideoAdFailedToLoad",
        "toris_ad_pending_result", "localStorage.setItem",
    ):
        assert token in js, f"missing token: {token}"


# ── 2026-07-09追記: 「読み込んでいます」が永遠に固まるP0バグの修正 ──────────

def test_reward_js_template_has_staged_timeouts_that_never_hang_forever():
    # 開始前(12秒)・視聴中(90秒)の二段階タイムアウトが両方存在すること
    # (CEO実機報告: 広告が「読み込んでいます」のまま一生終わらない、への対策)。
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "12000" in js, "12秒の開始前タイムアウトが無い"
    assert "90000" in js, "90秒の視聴中タイムアウトが無い"
    # 120秒の単一タイムアウト(旧実装)には戻っていないこと
    assert "120000" not in js


def test_reward_js_template_listens_for_loaded_and_showed_events():
    # 開始前→視聴中の安全弁切り替えに必要な Loaded/Showed イベントを購読している
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "onRewardedVideoAdLoaded" in js
    assert "onRewardedVideoAdShowed" in js


def test_reward_js_template_has_console_logging_for_debugging():
    # 実機再現時にログから原因を追えるよう console.log を仕込んでいること
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "console.log" in js


# ── 2026-07-09追記: リワード広告を1本化・完全ランダム化(CEO確定仕様) ──────

def test_twig_and_dummy_reward_functions_are_removed():
    # 案A(小枝確定付与)・「珍しい鳥が来やすくなる」ダミー案は完全に削除されている
    assert not hasattr(ads, "render_twig_reward_button")
    assert not hasattr(ads, "render_reward_ad_button")


def test_no_rare_bird_probability_wording_remains_in_module():
    # 交渉不能の原則4(生態に誠実): 広告で到来確率を操作する概念の文言が
    # ソース中に残っていないこと(コメント・docstring含め完全除去の確認)。
    src = open(os.path.join(os.path.dirname(__file__), "..", "ads.py"),
                encoding="utf-8").read()
    assert "珍しい" not in src


def test_garden_item_button_is_now_the_only_reward_pending_key():
    # pending_key の一本化: ads_pending_twig は完全に廃止され、
    # ads_pending_garden_item だけが残っていること。
    src = open(os.path.join(os.path.dirname(__file__), "..", "ads.py"),
                encoding="utf-8").read()
    assert "ads_pending_twig" not in src
    assert "ads_pending_garden_item" in src


# ── 2026-07-10追記: sandbox iframe から top を直接遷移できない不具合の修正 ──
# (最初の修正: window.top.documentへのscript注入による自己遷移。
#  その後さらにP1修正でlocalStorage方式に置き換え。下のセクション参照。)

def test_reward_js_template_does_not_directly_assign_top_location_href():
    # components.html() のiframeはsandboxにallow-top-navigation系フラグが無いため、
    # `window.top.location.href = ...` の直接代入はSecurityErrorで拒否される
    # (実機Playwright確認済み)。この後継のP1修正でナビゲーション自体をこの
    # モジュールから無くしたが、直接代入への後退が無いことは引き続き確認する。
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "window.top.location.href =" not in js
    assert "window.top.location.href=" not in js


# ── 2026-07-10追記(P1修正・CEO承認): 広告結果の伝達をlocalStorage経由の
# 「書いて後で読む」方式に変更(_inject_local_save_write/_inject_local_restore_checkと同じパターン) ──

def test_reward_js_template_no_longer_navigates_directly_from_ad_callback():
    # 実機PlaywrightでCDPのページライフサイクル(frozen→active)により、
    # 広告視聴中の実際のバックグラウンド化を再現したところ、広告SDKコールバック
    # の中で直接トップウィンドウへナビゲーションを試みる旧実装(window.top.document
    # へのscript注入)は不安定(成功したり失敗したりする)ことが判明した。
    # このモジュールはもはやナビゲーションを一切試みず、localStorageへの
    # 書き込みだけを行うこと(ナビゲーションはapp.py側の独立したポーリングに委譲)。
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "window.top.document" not in js
    assert "createElement('script')" not in js
    assert "appendChild(script)" not in js


def test_reward_js_template_writes_pending_result_to_top_local_storage():
    js = ads._ADMOB_REWARD_JS_TEMPLATE
    assert "window.top.localStorage.setItem('toris_ad_pending_result'" in js
    # status/nonce/reason/ts を持つペイロードであること(app.py側の読み取りと整合)
    assert "status: status" in js
    assert "nonce: NONCE" in js
    assert "reason: reason" in js
    assert "ts: Date.now()" in js


def test_app_injects_ad_result_check_gated_by_admob_enabled():
    # app.py 側: _inject_ad_result_check() が localStorage をポーリングし、
    # 見つけたらナビゲーションする(旧ads.py実装と同じ「script注入」手法を
    # app.py 側に引き継いでいる)。ADMOB_ENABLED=False(既定)のときは
    # 何もしない(壊さない)ことも確認する。
    src = open(os.path.join(os.path.dirname(__file__), "..", "app.py"),
                encoding="utf-8").read()
    assert "_inject_ad_result_check" in src
    assert "toris_ad_pending_result" in src
    assert "if not ads.ADMOB_ENABLED" in src
    assert "setInterval(tryDeliver" in src
    assert "removeItem(KEY)" in src  # 二重処理防止(読み取った時点で削除)


# ── 2026-07-11追記(P0根本修正): バナー広告が実機で一切表示されない不具合 ──────
# @capacitor-community/admob 8.0.0 の resumeBanner() は、AdView未作成でも
# 必ず resolve する(rejectしない)ため、「resumeBanner().catch(()=>showBanner)」
# という旧実装だと最初の1回、showBanner() が永久に呼ばれない(=バナー非表示)。

def test_banner_js_tracks_creation_state_instead_of_relying_on_resume_reject():
    # 自前のフラグでAdView作成済みかどうかを管理していること
    # (resumeBanner()の成否だけに依存する実装に戻っていないことの確認)
    js = ads._ADMOB_BANNER_JS_TEMPLATE
    assert "__torisAdmobBannerCreated" in js


def test_banner_js_calls_show_banner_directly_when_not_yet_created():
    # 「まだ一度もAdViewを作成していない」分岐では、resumeBanner()のcatchの中では
    # なく、直接 showBanner() を呼ぶこと(P0バグの再発防止)。
    js = ads._ADMOB_BANNER_JS_TEMPLATE
    if_not_created_idx = js.index("if (win.__torisAdmobBannerCreated) {\n        // 既にAdViewを作成済み")
    show_banner_idx = js.index("AdMob.showBanner({")
    resume_banner_idx = js.index("AdMob.resumeBanner()")
    # showBanner() の呼び出しが、条件分岐(既存フラグチェック)より後、かつ
    # resumeBanner() の呼び出しの後(=elseブロック相当)に単独で存在すること
    assert if_not_created_idx < show_banner_idx
    assert resume_banner_idx < show_banner_idx
    # 旧実装の特徴的なパターン(resumeBanner().catch(function () { ... showBanner)
    # には戻っていないこと
    assert "resumeBanner().catch(function () {\n        AdMob.showBanner" not in js


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
