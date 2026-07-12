"""
test_query_param_isolation.py - クエリパラメータの「自分が処理したキーだけを消す」ことの
回帰テスト(AppTestレベル)。

2026-07-11追記(CEO実機Playwright報告): PJ管理部長が実際にStreamlitサーバーを起動し
Playwrightで操作したところ、儀式UI(`?ritual_obs=<bird_id>`)からの意図的なフルリロードが、
ローカルセーブの自動復元チェックJS(`_inject_local_restore_check()`)による
`?local_restore=<コード>` 付きリロードとたまたま同じリロードに乗った場合
(自動復元チェックは localStorage にセーブコードがある限り**毎回のページロードで無条件に
発火**し、既存のクエリを保持したまま `local_restore=` を追加するため、これは通常運用の
ほぼ全ケースで起こり得る)、`_handle_local_restore_query()` が
`st.query_params.clear()`(クエリ文字列**全体**を消す)を呼んでいたため、後続の
`_handle_ritual_observation()` に `ritual_obs` が届かず、儀式で会った鳥が図鑑に
一切反映されない不具合が実機で再現された。`_handle_ad_reward_result()` も全く同じ
構造(`ad_result`/`ad_nonce`/`ad_reason`)のバグを抱えていた。

修正: 各ハンドラは `st.query_params.clear()` ではなく、自分が処理した個別キーだけを
`st.query_params.pop(key, None)` で削除する。このテストは、`local_restore` と
`ritual_obs`(または `ad_result`/`ad_nonce`)が同一クエリに共存する状況を実際に
`AppTest` で再現し、両方が正しく処理されること(儀式観察の反映・広告報酬の付与)を確認する。

実行: python3 toris_collection/tests/test_query_param_isolation.py
または: pytest toris_collection/tests/test_query_param_isolation.py
依存: pytest 環境に streamlit がインストールされていること(既存のアプリ依存と同じ)。
AppTest はアプリ全体(app.py)を実際にヘッドレス起動するため、他の純粋関数テストより
実行に数秒かかる。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from streamlit.testing.v1 import AppTest  # noqa: E402

import save_code  # noqa: E402

_APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _build_restore_code():
    """discovered が空の、まっさらな復元用セーブコードを1本作る。"""
    return save_code.encode_save({
        "biome": "kyoto",
        "discovered": [],
        "observed": {},
        "residents": [],
        "planted": [],
        "saved_at": "2026-07-11T10:00:00",
    })


def test_local_restore_and_ritual_obs_coexist_both_processed():
    # 自動復元チェックJSが ?ritual_obs=... のリロードに便乗して
    # ?local_restore=... を足した状況(実機で再現されたケース)を再現する。
    at = AppTest.from_file(_APP_PATH, default_timeout=60)
    at.query_params["local_restore"] = _build_restore_code()
    at.query_params["ritual_obs"] = "northern_cardinal"
    at.run()

    assert not at.exception, f"起動時に例外が発生した: {at.exception}"

    ss = at.session_state
    # local_restore が処理され、セッションが始まっていること
    assert ss["current_tester_id"] is not None
    # ritual_obs が握りつぶされず、儀式で会った鳥として図鑑に反映されていること
    assert "northern_cardinal" in ss["discovered"]
    assert ss["observed"].get("northern_cardinal", {}).get("count", 0) >= 1
    # 両方処理済みでクエリパラメータが残っていないこと(次回リロードでの二重処理防止)
    assert dict(at.query_params) == {}


def test_local_restore_and_ad_result_coexist_both_processed():
    # 広告視聴結果通知(?ad_result=...&ad_nonce=...)にも同じ構造のバグが
    # あったため、同様に local_restore と共存するケースを確認する。
    at = AppTest.from_file(_APP_PATH, default_timeout=60)
    at.query_params["local_restore"] = _build_restore_code()
    at.query_params["ad_result"] = "success"
    at.query_params["ad_nonce"] = "test-nonce-123"
    # ads.py の _handle_ad_reward_result() が参照する保留中リクエストを
    # あらかじめ積んでおく(実際には ads.py が広告視聴開始時にこれを積む)。
    at.session_state["ads_pending_garden_item"] = {
        "item_id": "feeder",
        "nonce": "test-nonce-123",
    }
    at.run()

    assert not at.exception, f"起動時に例外が発生した: {at.exception}"

    ss = at.session_state
    assert ss["current_tester_id"] is not None
    # ad_result が握りつぶされず、広告報酬(庭アイテム配置)が確定していること
    assert ss["garden_item_placement"] is not None
    assert ss["garden_item_placement"].get("item_id") == "feeder"
    # 両方処理済みでクエリパラメータが残っていないこと
    assert dict(at.query_params) == {}


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
