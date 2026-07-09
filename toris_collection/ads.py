"""
ads.py - 広告UIの土台(プレースホルダー)

■ 位置づけ(交渉不能の原則・00_共通サマリ.md)
  - 全画面割り込み広告は絶対に実装しない。
  - 鳥の声・癒し体験(ラジオ)を広告でゲートしない(常に無料)。
  - リワード広告は完全に任意のおまけ。見なくても庭の進み方は一切変わらない。
  - 受動的であること(広告を見ないと不利になる設計にしない)。

■ 実装範囲(2026-07-08時点)
  ここにあるのは配置・表示/非表示ロジックだけの UI プレースホルダー。
  実際の広告配信ネットワーク(AdMob 等)へはまだ接続していない。
  理由: 広告=商用利用となり、xeno-canto の非商用(CC BY-NC 等)録音を
  含んだまま商用化するとライセンス違反になる。ライセンス監査
  (license_audit.py)が完了し、`xc_client.COMMERCIAL_ONLY` を商用可の
  音源だけに絞った状態で運用開始してから、実配信の着手を判断する
  (ROADMAP_GOOGLE_PLAY.md Phase 2 参照)。

  将来ここに実SDKを差し込む際は:
    - render_banner_placeholder() の中身を実SDKのタグ/コンポーネントに置き換える
    - render_reward_ad_button() の disabled/no-op 部分を実際のリワード広告呼び出しに置き換える
  だけで済むよう、呼び出し側(app.py)とはこの2関数のインターフェースだけで疎結合にしてある。

集計/判定ロジックは Streamlit から切り離した純粋関数。テスト可能。

■ 2026-07-08 追記: 広告リワードアイテム拡充
  docs/team/proposals/2026-07-08_広告リワードアイテム拡充案.md に基づき、
  以下2種類の「見ると1日1回だけ受け取れる」リワードを追加した(いずれも完全に任意):
    - 落とし物(mementos)連動リワード: 今日庭に来た鳥から小枝を1個確定付与。
    - 庭アイテム(garden_items.py・6種)配置リワード: 6時間だけ効くおまけを1つ置ける。
  どちらも1日1回のゲートは `has_claimed_today`/`mark_claimed_today`(ISO日付文字列の
  比較、`app._mark_met_today` と同じ「今日=1カウント」パターン)で管理する。
  実際の状態変更(memento付与・アイテム配置)は呼び出し側(app.py)の関数に委譲し、
  ここでは UI と日付ゲートの判定だけを持つ(疎結合を保つ既存方針を踏襲)。

■ 2026-07-08 追記(実SDK接続): リワード広告の視聴完了を待ってから報酬を確定する
  JS↔Python連携
  - `ADMOB_ENABLED=False`(既定・現状の本番設定)のときは、これまでどおり
    「ボタンを押したら即時付与」(壊さない=挙動を一切変えない)。
  - `ADMOB_ENABLED=True` のときだけ、ボタン押下は即時付与せず
    `session_state["ads_pending_twig"|"ads_pending_garden_item"]` に
    `{"nonce": ..., ...payload}` を積んで `st.rerun()` する。次の実行で
    `render_pending_ad_loader()` が実際に `@capacitor-community/admob` の
    `AdMob.showRewardVideoAd()` を呼び出す `components.html` を描画する。
  - Streamlitはコンポーネント→サーバーの汎用な双方向通信を持たないため、
    `ritual.py`(儀式UI)が使っている「JS が `window.top.location` にクエリ
    パラメータを付けてトップウィンドウごとリロードし、Python 側が
    `st.query_params` で読み取る」という既存の片道経路パターンをそのまま
    踏襲した(`app._handle_ritual_observation` 参照)。広告視聴完了
    (`onRewardedVideoAdDismissed`、reward獲得フラグ込み)のイベントを受けて
    `?ad_result=success|fail|unavailable&ad_nonce=...` を付けてトップを
    リロードし、`app._handle_ad_reward_result()` が pending の nonce と
    照合してから初めて報酬を確定する。nonceが一致しない・pendingが無い
    場合は何もしない(古いリロード・多重送信への耐性)。
  - Web版(通常ブラウザ、`window.Capacitor` が存在しない)では即座に
    `ad_result=unavailable` を返す。ADMOB_ENABLED=True の場合、Web版では
    「テスト用に即時付与」ではなく「アプリ版でのみ利用可」を選んだ
    (実SDK接続後は"広告なしで無料付与できる抜け道"を残さないため。
    詳細判断理由は開発部の報告参照)。
  - 広告読み込み失敗・視聴中断(`FailedToLoad`/`FailedToShow`/reward無しで
    `Dismissed`)は `ad_result=fail` を返し、報酬を付与せず静かに伝える
    (交渉不能の原則2「罰しない」・原則1「受動的」— 失敗してもペナルティは
    無く、いつでも再挑戦できる)。
"""
from __future__ import annotations

import uuid
from datetime import date


def _today_str(today=None) -> str:
    """日付から 'YYYY-MM-DD' 文字列を作る(全ユーザー・全端末で同じ形式)。"""
    return (today or date.today()).isoformat()


def has_claimed_today(session_state, flag_key: str, today=None) -> bool:
    """指定のフラグキーが「今日」既に消費済みかどうか。

    `app._mark_met_today` と同じ「ISO日付文字列を保存し、今日の文字列と比較する」
    パターン(daily.py の「1日1回・全員共通」という設計思想を踏襲)。
    """
    try:
        return session_state.get(flag_key) == _today_str(today)
    except AttributeError:
        return False


def mark_claimed_today(session_state, flag_key: str, today=None) -> None:
    """指定のフラグキーに「今日」の日付文字列を記録する(1日1回ゲートの消費)。"""
    session_state[flag_key] = _today_str(today)


def is_radio_active(session_state) -> bool:
    """ラジオが再生開始状態かどうかを、Python 側から分かる範囲で近似する。

    radio.render_radio() は既定で key_prefix="radio" を使い、ユーザーが
    「🎙 ラジオを始める」ボタンを押すと session_state["radio_ready"] が
    True になる(radio.py 参照)。ラジオは iframe 内 Web Audio で鳴っており、
    庭タブに戻ってもオーディオはバックグラウンドで鳴り続けている可能性が
    あるため、その間は静かなバナーを隠す。

    session_state: st.session_state、またはテスト用の dict 等
                    (`.get(key, default)` を持つもの)。
    """
    try:
        return bool(session_state.get("radio_ready"))
    except AttributeError:
        return False



# ── AdMob(Android版のみ・Capacitorネイティブブリッジ経由) ─────────────
# 2026-07-08 追記: @capacitor-community/admob を android_app/ に導入済み
# (npm install・npx cap sync 済み。AndroidManifest.xml/strings.xml に
# Googleのテスト用App IDを設定済み)。ただし ADMOB_ENABLED は既定 False で、
# 有効化するまでは一切の広告呼び出しを行わない(壊さない=現状の挙動を
# 変えない)。
#
# 有効化方法(CEO操作): Streamlit secrets に admob_enabled = true を追加
# (または環境変数 ADMOB_ENABLED=1)。広告ユニットIDも同様に
# admob_banner_unit_id で差し替え可能(未設定時はGoogle公式のテスト用
# バナーIDを使うため、実収益は発生しない=安全に先行動作確認できる)。
#
# Web版(Renderの通常ブラウザアクセス)では window.Capacitor 自体が
# 存在しないため、ADMOB_ENABLED=True にしても常に何もしない
# (isNativePlatform() チェックで自動的に絞られる。
# app.py の _inject_native_share_button と同じ安全設計を踏襲)。
# 広告表示はネイティブAndroid Viewとして画面に重なる形で出るため、
# Streamlit側のHTML DOM(components.html)には描画されない。
_ADMOB_TEST_APP_ID = "ca-app-pub-3940256099942544~3347511713"
_ADMOB_TEST_BANNER_UNIT_ID = "ca-app-pub-3940256099942544/9214589741"


def _load_admob_enabled() -> bool:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "admob_enabled" in st.secrets:
            return bool(st.secrets["admob_enabled"])
    except Exception:
        pass
    import os
    return os.environ.get("ADMOB_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _load_admob_banner_unit_id() -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "admob_banner_unit_id" in st.secrets:
            val = str(st.secrets["admob_banner_unit_id"]).strip()
            if val:
                return val
    except Exception:
        pass
    import os
    env_val = (os.environ.get("ADMOB_BANNER_UNIT_ID") or "").strip()
    return env_val or _ADMOB_TEST_BANNER_UNIT_ID


ADMOB_ENABLED = _load_admob_enabled()

_ADMOB_BANNER_JS_TEMPLATE = """
<script>
(function () {
  try {
    var win = window.parent;
    if (!win.Capacitor || !win.Capacitor.isNativePlatform || !win.Capacitor.isNativePlatform()) {
      return; // Web版(通常ブラウザ)では何もしない
    }
    var AdMob = win.Capacitor.Plugins && win.Capacitor.Plugins.AdMob;
    if (!AdMob) {
      return; // プラグイン未導入のネイティブビルドでも落とさない
    }
    var shouldHide = __HIDE__;
    var unitId = "__UNIT_ID__";
    var isTesting = __IS_TESTING__;

    function showOrHide() {
      if (shouldHide) {
        AdMob.hideBanner().catch(function () {});
        return;
      }
      AdMob.resumeBanner().catch(function () {
        AdMob.showBanner({
          adId: unitId,
          adSize: "ADAPTIVE_BANNER",
          position: "BOTTOM_CENTER",
          margin: 0,
          isTesting: isTesting
        }).catch(function () {});
      });
    }

    if (!win.__torisAdmobInitialized) {
      win.__torisAdmobInitialized = true;
      AdMob.initialize().then(showOrHide).catch(function () {});
    } else {
      showOrHide();
    }
  } catch (e) {
    // AdMob非搭載環境・ブリッジ未接続等で失敗しても本編には影響させない
  }
})();
</script>
"""


def render_admob_banner(session_state, key_prefix: str = "ads") -> None:
    """Android版(Capacitorネイティブ)でのみ、AdMobの静かなバナー広告を表示する。

    ADMOB_ENABLED=False(既定)のときは何もしない。ラジオ再生中は
    render_banner_placeholder と同じ is_radio_active 判定で隠す
    (交渉不能の原則: 鳥の声と癒しは常に無料・広告で邪魔しない)。
    """
    if not ADMOB_ENABLED:
        return

    import streamlit.components.v1 as components

    unit_id = _load_admob_banner_unit_id()
    hide = is_radio_active(session_state)
    is_testing = unit_id == _ADMOB_TEST_BANNER_UNIT_ID

    js = (
        _ADMOB_BANNER_JS_TEMPLATE
        .replace("__HIDE__", "true" if hide else "false")
        .replace("__UNIT_ID__", unit_id)
        .replace("__IS_TESTING__", "true" if is_testing else "false")
    )
    components.html(js, height=0)


_ADMOB_TEST_REWARDED_UNIT_ID = "ca-app-pub-3940256099942544/5224354917"


def _load_admob_rewarded_unit_id() -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "admob_rewarded_unit_id" in st.secrets:
            val = str(st.secrets["admob_rewarded_unit_id"]).strip()
            if val:
                return val
    except Exception:
        pass
    import os
    env_val = (os.environ.get("ADMOB_REWARDED_UNIT_ID") or "").strip()
    return env_val or _ADMOB_TEST_REWARDED_UNIT_ID


# JS↔Python連携の片道経路(ritual.py と同じ設計、上のクラスdocstring参照)。
# 視聴完了(Dismissed)まで待ってから top window をリロードする。navigateを
# 「Rewarded」の瞬間ではなく「Dismissed」の瞬間に遅らせているのは、リワード広告
# 自体はネイティブの別Activity(WebViewの上に重なる全画面ビュー)として表示され、
# 裏のWebViewを先にナビゲートしても広告再生は妨げないはずだが、念のため
# ユーザーが広告を見終えてから戻す方が自然な体感になるため。
_ADMOB_REWARD_JS_TEMPLATE = """
<script>
(function () {
  var NONCE = "__NONCE__";

  function reportResult(status) {
    try {
      var url = new URL(window.top.location.href);
      url.searchParams.set('ad_result', status);
      url.searchParams.set('ad_nonce', NONCE);
      window.top.location.href = url.toString();
    } catch (e) {}
  }

  var settled = false;
  function finish(status) {
    if (settled) return;
    settled = true;
    reportResult(status);
  }

  try {
    var win = window.parent;
    if (!win.Capacitor || !win.Capacitor.isNativePlatform || !win.Capacitor.isNativePlatform()) {
      finish('unavailable'); // Web版(通常ブラウザ)には広告SDKが無い
      return;
    }
    var AdMob = win.Capacitor.Plugins && win.Capacitor.Plugins.AdMob;
    if (!AdMob) {
      finish('unavailable'); // プラグイン未導入のネイティブビルドでも落とさない
      return;
    }

    var unitId = "__UNIT_ID__";
    var isTesting = __IS_TESTING__;
    var earned = false;

    AdMob.addListener('onRewardedVideoAdReward', function () { earned = true; });
    AdMob.addListener('onRewardedVideoAdDismissed', function () {
      finish(earned ? 'success' : 'fail');
    });
    AdMob.addListener('onRewardedVideoAdFailedToShow', function () { finish('fail'); });
    AdMob.addListener('onRewardedVideoAdFailedToLoad', function () { finish('fail'); });

    function playAd() {
      AdMob.prepareRewardVideoAd({ adId: unitId, isTesting: isTesting })
        .then(function () { return AdMob.showRewardVideoAd(); })
        .catch(function () { finish('fail'); });
    }

    if (!win.__torisAdmobInitialized) {
      win.__torisAdmobInitialized = true;
      AdMob.initialize().then(playAd).catch(function () { finish('fail'); });
    } else {
      playAd();
    }

    // 安全弁: 実機の異常系でイベントが一切発火しない場合でも pending 状態が
    // 固まらないよう、2分でタイムアウトして失敗扱いにする(通常のリワード
    // 動画は数十秒で終わる想定。報酬は付与しない=安全側に倒す)。
    setTimeout(function () { finish('fail'); }, 120000);
  } catch (e) {
    finish('fail'); // Capacitor非搭載環境・ブリッジ未接続等で失敗しても本編には影響させない
  }
})();
</script>
"""


def render_pending_ad_loader(session_state, pending_key: str, key_prefix: str = "ads") -> bool:
    """`pending_key` に保留中の広告視聴リクエストがあれば、実際にリワード広告を
    再生する `components.html` を描画し、視聴完了まで待つ画面を返す。

    保留が無い、または ADMOB_ENABLED=False(既定)のときは何もせず False を返す
    (呼び出し側は通常のボタンUIをそのまま表示すればよい)。保留を検出して
    広告ローダーを描画したときは True を返す(呼び出し側はこの回、通常の
    ボタンUIの代わりにこちらだけを表示する)。

    実際の報酬確定は行わない(`app._handle_ad_reward_result()` の責務)。
    ここは「広告を再生し、結果を top window のクエリパラメータで知らせる」
    までを担当する。
    """
    if not ADMOB_ENABLED:
        return False
    pending = session_state.get(pending_key)
    if not pending:
        return False

    import streamlit as st
    import streamlit.components.v1 as components

    st.caption("🎬 広告を読み込んでいます……見終わると自動で戻ります。")
    unit_id = _load_admob_rewarded_unit_id()
    is_testing = unit_id == _ADMOB_TEST_REWARDED_UNIT_ID
    js = (
        _ADMOB_REWARD_JS_TEMPLATE
        .replace("__NONCE__", str(pending.get("nonce", "")))
        .replace("__UNIT_ID__", unit_id)
        .replace("__IS_TESTING__", "true" if is_testing else "false")
    )
    components.html(js, height=0)
    if st.button("キャンセルする", key=f"{key_prefix}_{pending_key}_cancel_btn"):
        session_state.pop(pending_key, None)
        st.rerun()
    return True


def render_banner_placeholder(session_state, key_prefix: str = "ads") -> None:
    """ホーム下部の静かなバナー広告のプレースホルダーを描画する。

    ラジオ再生中(is_radio_active）は非表示にする。
    実際の広告SDKは未接続。枠と表示/非表示ロジックのみを検証する目的。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    if is_radio_active(session_state):
        return

    st.markdown(
        "<div style='margin-top:22px;padding:10px 16px;border-radius:8px;"
        "background:#f4f2ec;border:1px dashed #cfc7b0;text-align:center;'>"
        "<span style='color:#9a9078;font-size:0.82em;'>🌾 広告スペース(準備中)</span>"
        "<div style='font-size:0.76em;color:#b0a890;margin-top:2px;'>"
        "実際の広告はまだ配信していません・ラジオ再生中は表示しません"
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_reward_ad_button(key_prefix: str = "ads") -> None:
    """任意のリワード広告ボタンのプレースホルダーを描画する。

    将来「見ると今日だけ珍しい種が来やすくなる」等の一時的なブーストを
    想定しているが、現時点では広告配信を開始していないため、押しても
    ゲーム進行には何の影響も与えないダミー。あくまで完全に任意のおまけで
    あり、見なくても庭の進み方・鳥の声は変わらないことを明示する。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    with st.expander("🎁 応援広告(準備中)", expanded=False):
        st.caption(
            "見ると今日だけ珍しい鳥が来やすくなる……予定の任意広告です。"
            "今はまだ広告配信を始めていません。見ても見なくても、"
            "庭の進み方や鳥の声はいつもどおりです。"
        )
        if st.button(
            "▶ 広告を見る(準備中)",
            key=f"{key_prefix}_reward_btn",
            use_container_width=True,
        ):
            st.info("広告はまだ準備中です。もうしばらくお待ちください。")


def render_twig_reward_button(session_state, residents, birds_data, grant_fn,
                              key_prefix: str = "ads") -> None:
    """落とし物(mementos)連動リワード(1日1回)。

    今日庭に来ている鳥(residents)から1羽選び、小枝(twig)を1個確定付与する。
    実際の付与処理は `grant_fn(bird_id)` に委譲する(app.py 側が mementos の
    session反映・Sheetsへのベストエフォート書き戻しを持つ。ここではUIと
    「1日1回」の日付ゲートだけを扱う)。

    庭に誰も来ていない日はボタンを無効化(選べる鳥がないため)する。

    ADMOB_ENABLED=True のときは、押しても即時付与せず `session_state["ads_pending_twig"]`
    に選んだ鳥と乱数(nonce)を積んで広告視聴フローへ回す(実際の付与は
    `app._handle_ad_reward_result()` が視聴完了イベントを受け取ってから行う)。
    ADMOB_ENABLED=False(既定)のときは、これまでどおり即時付与のまま(壊さない)。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    flag_key = "twig_reward_claimed_date"
    pending_key = "ads_pending_twig"
    with st.expander("🎁 応援広告(今日来た鳥から、小枝をもう一つ)", expanded=False):
        st.caption(
            "見ると、今日庭に来てくれた鳥から、記念の小枝をもう一つもらえます。"
            "見なくても、鳥の声や落とし物のチャンスはいつもどおりです。"
        )
        if has_claimed_today(session_state, flag_key):
            st.caption("✓ 今日はもう受け取りました。また明日。")
            return
        if not residents:
            st.caption("今日はまだ庭に鳥が来ていません。鳥が来てから受け取れます。")
            return

        if render_pending_ad_loader(session_state, pending_key, key_prefix=key_prefix):
            return  # 広告視聴中: 通常のボタンUIは隠す

        ids_sorted = sorted(
            residents, key=lambda b: birds_data.get(b, {}).get("name", b)
        )
        choice = st.selectbox(
            "小枝をもらう鳥を選ぶ",
            options=ids_sorted,
            format_func=lambda b: birds_data.get(b, {}).get("name", b),
            key=f"{key_prefix}_twig_bird_choice",
        )
        if st.button(
            "▶ 広告を見て、小枝をもらう",
            key=f"{key_prefix}_twig_reward_btn",
            use_container_width=True,
        ):
            if ADMOB_ENABLED:
                session_state[pending_key] = {"nonce": uuid.uuid4().hex, "bird_id": choice}
            else:
                grant_fn(choice)
                mark_claimed_today(session_state, flag_key)
            st.rerun()


def render_garden_item_button(session_state, biome_id, birds_data, place_fn,
                              key_prefix: str = "ads") -> None:
    """庭アイテム(garden_items.py・6種)配置リワード(1日1回・6時間持続)。

    実際の配置処理は `place_fn(item_id)` に委譲する(app.py 側が
    session_state["garden_item_placement"] を更新する)。
    pp数値はユーザーには見せず、`garden_items.ITEMS` の hint/culture_note の
    言葉に翻訳して見せる(提案書§4 UI仕様)。

    ADMOB_ENABLED=True のときは、押しても即時配置せず
    `session_state["ads_pending_garden_item"]` に選んだアイテムと乱数(nonce)を
    積んで広告視聴フローへ回す(実際の配置は `app._handle_ad_reward_result()` が
    視聴完了イベントを受け取ってから行う)。ADMOB_ENABLED=False(既定)のときは、
    これまでどおり即時配置のまま(壊さない)。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ
    import garden_items as gi

    flag_key = "garden_item_claimed_date"
    pending_key = "ads_pending_garden_item"
    with st.expander("🎁 応援広告(今日の庭アイテムを選ぶ)", expanded=False):
        active = session_state.get("garden_item_placement")
        if gi.is_active(active):
            item = gi.ITEMS.get(active.get("item_id"), {})
            hrs = gi.hours_remaining(active)
            st.caption(
                f"{item.get('emoji', '')} 今は「{item.get('name', '')}」を"
                f"置いています(あと{hrs:.1f}時間)。"
            )
            return
        if has_claimed_today(session_state, flag_key):
            st.caption("✓ 今日はもう1つ選びました。また明日、別のアイテムを選べます。")
            return

        if render_pending_ad_loader(session_state, pending_key, key_prefix=key_prefix):
            return  # 広告視聴中: 通常のボタンUIは隠す

        st.caption(
            "見ると、庭に6時間だけ道具を1つ置けます。アメリカの裏庭バードウォッチング"
            "文化の道具を紹介する、今日だけの特別な小窓です。見なくても庭の進み方は"
            "いつもどおりです。"
        )
        for item_id in gi.ITEM_ORDER:
            item = gi.ITEMS[item_id]
            label = f"{item['emoji']} {item['name']}"
            available = gi.is_available(item_id, biome_id, birds_data)
            if available:
                st.markdown(f"**{label}**")
                st.caption(f"{item['hint']} {item['culture_note']}")
                if st.button(
                    f"▶ {label} を置く",
                    key=f"{key_prefix}_item_{item_id}_btn",
                    use_container_width=True,
                ):
                    if ADMOB_ENABLED:
                        session_state[pending_key] = {
                            "nonce": uuid.uuid4().hex, "item_id": item_id,
                        }
                    else:
                        place_fn(item_id)
                        mark_claimed_today(session_state, flag_key)
                    st.rerun()
            else:
                st.markdown(f"~~{label}~~ (今のこの庭では選べません)")
                st.caption(gi.unavailable_reason(item_id, biome_id, birds_data))
            st.markdown("---")
