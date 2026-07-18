"""
ads.py - 広告UIの土台(プレースホルダー)

■ 位置づけ(交渉不能の原則・00_共通サマリ.md)
  - 全画面割り込み広告は絶対に実装しない。
  - 鳥の声・癒し体験(ラジオ)を広告でゲートしない(常に無料)。
  - リワード広告は完全に任意のおまけ。効果は対象の鳥への小さな到来確率
    ブースト等(+1〜6ポイント程度、常にプラス方向)であり、見なくても
    鳥の声・ラジオ・図鑑や通常(アイテムなし)の到来確率は変わらない
    (`garden_items.py` 参照)。
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
    - render_garden_item_button() の disabled/no-op 部分を実際のリワード広告呼び出しに置き換える
  だけで済むよう、呼び出し側(app.py)とはこれらの関数のインターフェースだけで疎結合にしてある。

集計/判定ロジックは Streamlit から切り離した純粋関数。テスト可能。

■ 2026-07-08 追記: 広告リワードアイテム拡充
  docs/team/proposals/2026-07-08_広告リワードアイテム拡充案.md に基づき、
  「見ると1日1回だけ受け取れる」庭アイテム(garden_items.py・6種)配置リワードを
  追加した(6時間だけ効くおまけを1つ置ける・完全に任意)。
  1日1回のゲートは `has_claimed_today`/`mark_claimed_today`(ISO日付文字列の
  比較、`app._mark_met_today` と同じ「今日=1カウント」パターン)で管理する。
  実際の状態変更(アイテム配置)は呼び出し側(app.py)の関数に委譲し、
  ここでは UI と日付ゲートの判定だけを持つ(疎結合を保つ既存方針を踏襲)。

■ 2026-07-09 追記(CEO確定仕様): リワード広告を1本化・完全ランダム化
  以前あった案A(落とし物連動・小枝を確定付与)と、「見ると到来確率が上がる」
  という未接続のダミー案は削除した。庭アイテムの「選ぶ」UIも廃止し、6種
  (バイオーム制約はそのまま)の中から完全ランダムで1つ付与する方式にした。
  広告=道具屋さんからのおまけ、という単純な1本のフローに揃えることで、
  AdMobフロー(P0で安定化した箇所)もシンプルに保てる。

■ 2026-07-08 追記(実SDK接続): リワード広告の視聴完了を待ってから報酬を確定する
  JS↔Python連携
  - `ADMOB_ENABLED=False`(既定・現状の本番設定)のときは、これまでどおり
    「ボタンを押したら即時付与」(壊さない=挙動を一切変えない)。
  - `ADMOB_ENABLED=True` のときだけ、ボタン押下は即時付与せず
    `session_state["ads_pending_garden_item"]` に
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

■ 2026-07-10 追記(P1修正): 広告結果の伝達をトップwindowへの直接ナビゲーション
  からlocalStorage経由の「書いて後で読む」方式に変更
  実機で「SecurityError回避策(window.top.documentへの<script>要素注入による
  自己遷移)を入れたのに、視聴後に報酬が確定しないことがある」という報告が
  あった。原因調査(PlaywrightでCDPの `Page.setWebLifecycleState`
  (frozen⇄active)によりページのバックグラウンド化を再現)の結果、
  ネイティブのフルスクリーン広告Activity表示中はこのWebViewが実際に
  バックグラウンド化されており、視聴完了(Dismissed等)イベントの
  コールバックそのものはバックグラウンド復帰後に正しく届くものの、
  「そのコールバックの中で直接トップウィンドウへナビゲーションを試みる」
  という操作自体が、復帰直後のタイミングでは成功したり失敗したりする
  不安定な挙動になることを確認した。
  このため `reportResult()` は、広告視聴の結果確定イベントを受けても
  もはやナビゲーションを一切試みない。代わりに
  `window.top.localStorage.setItem('toris_ad_pending_result', ...)` という
  ナビゲーションを伴わない同期的な書き込みだけを行う(`app._inject_local_save_write()`
  と同じ、バックグラウンド化の影響を受けにくい手段)。実際にPython側へ
  結果を届けるナビゲーションは、広告SDKのコールバックとは完全に独立した
  タイミングで動く `app._inject_ad_result_check()`(アプリの毎回のrerunで
  常に描画され、1秒おきにlocalStorageをポーリングする)が行う。
  こうして「広告SDKのコールバックが発火する不安定なタイミング」と
  「実際にPythonへ通知するナビゲーションを試みるタイミング」を分離し、
  後者を複数回リトライ可能にすることで、バックグラウンド化をまたいでも
  報酬が確実に反映されるようにした。

■ 2026-07-11 追記(P0根本修正): バナー広告が実機で一切表示されない不具合
  CEO報告「Android版で広告が表示されない」の原因調査で、`_ADMOB_BANNER_JS_TEMPLATE`
  自体のロジックバグを発見した。`@capacitor-community/admob` 8.0.0 のネイティブ実装
  (`BannerExecutor.resumeBanner()`)を読むと、AdView がまだ一度も作成されていない
  (`mAdView == null`)状態で呼んでも、内部のnullチェックとは無関係に
  必ず `call.resolve()` する(rejectしない)ことが確認できた。旧実装は
  「`resumeBanner().catch(() => showBanner(...))`」という、resumeBannerの失敗を
  「まだ一度も表示していない合図」として使うパターンだったため、アプリ起動後
  最初の1回は resumeBanner() が(何もしないまま)成功してしまい、catch内の
  `showBanner()` が一度も呼ばれず、バナーが永久に作成されないまま終わっていた。
  自前のフラグ(`win.__torisAdmobBannerCreated`)でAdView作成済みかどうかを
  管理する形に修正し、resumeBanner()の成否には依存しないようにした。
  なお、この修正とは別に `ADMOB_ENABLED`(Streamlit secrets/環境変数)が本番で
  実際に有効化されているかはコードからは確認できないため、CEO確認が必要。
"""
from __future__ import annotations

import uuid
from datetime import date

from i18n import t


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

    // 2026-07-11追記(P0根本修正): 「バナーが実機で一切表示されない」不具合の原因調査。
    // @capacitor-community/admob 8.0.0 のネイティブ実装(BannerExecutor.resumeBanner)は、
    // まだ一度も showBanner() で AdView を作成していない状態(mAdView == null)で
    // 呼んでも、内部の null チェックに関わらず必ず call.resolve() する(rejectしない)。
    // そのため旧実装の「resumeBanner().catch(() => showBanner(...))」は、
    // アプリ起動後 最初の1回、mAdView が存在せず何も起きないにも関わらず
    // resumeBanner() のPromiseが成功してしまい、catch内のshowBanner()が
    // 一度も呼ばれないまま終わっていた(=バナーが永久に作成されない)。
    // このため「AdViewを作成済みかどうか」を自前のフラグ(win.__torisAdmobBannerCreated)
    // で管理し、resumeBanner()の成否には依存しない形に修正する。
    function showOrHide() {
      if (shouldHide) {
        if (win.__torisAdmobBannerCreated) {
          AdMob.hideBanner().catch(function () {});
        }
        return;
      }
      if (win.__torisAdmobBannerCreated) {
        // 既にAdViewを作成済み: 再表示するだけ
        AdMob.resumeBanner().catch(function () {});
        return;
      }
      // 初回: 必ず showBanner() でAdViewを新規作成する
      // (resumeBanner()の成功/失敗を作成済み判定の代わりに使わない)
      win.__torisAdmobBannerCreated = true;
      AdMob.showBanner({
        adId: unitId,
        adSize: "ADAPTIVE_BANNER",
        position: "BOTTOM_CENTER",
        margin: 0,
        isTesting: isTesting
      }).catch(function () {
        // 作成に失敗した場合は、次回の描画でまた作成を試せるようにフラグを戻す
        win.__torisAdmobBannerCreated = false;
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
#
# 2026-07-09 追記(P0修正): 実機で「読み込んでいます」のまま終わらない不具合が
# 報告された。原因は特定できていない(AdMob.initialize()が理由不明のまま
# 一度も resolve/reject しない、等が実機ログから疑われる)が、原因の如何を
# 問わず「絶対に固まらない」ことを保証するため、二段階のタイムアウトを導入する。
#   1. START_TIMEOUT(12秒): 広告が実際に画面に表示される(Showedイベント)前に
#      12秒経っても進まなければ、initialize/prepare/show のどこで止まっていても
#      失敗扱いにする(CEO実機報告への直接対応: 10〜15秒で見切りをつける)。
#   2. WATCH_TIMEOUT(90秒): 広告が表示された後、視聴完了(Dismissed)が万一
#      来ない異常系に備えた、より長い最終安全弁。
# あわせて console.log でも段階を記録し(タグ "[TorisAd]")、次回実機再現時に
# chrome://inspect のリモートデバッグ / logcat から原因を追いやすくする。
_ADMOB_REWARD_JS_TEMPLATE = """
<script>
(function () {
  var NONCE = "__NONCE__";
  var TAG = '[TorisAd]';

  function log(msg) {
    try { console.log(TAG, msg); } catch (e) {}
  }

  function reportResult(status, reason) {
    try {
      log('結果を保存します(localStorage): ' + status + (reason ? ' (' + reason + ')' : ''));
      // 2026-07-10追記(P1修正): ここでトップウィンドウへ直接ナビゲーションを
      // 試みていた旧実装(トップwindowのdocumentへの<script>要素注入による
      // 自己遷移)は、実機PlaywrightでCDPのページライフサイクル
      // (frozen→active、ネイティブ広告Activity表示中の実際のバックグラウンド化を
      // 再現)により、視聴完了直後のタイミングでは不安定(成功したり失敗したり)
      // であることを確認した。ナビゲーションという操作自体をこの場では行わず、
      // トップwindowのlocalStorage への同期的な書き込みだけに留める(モジュール
      // docstring「2026-07-10 追記(P1修正)」参照)。実際にPython側へ結果を
      // 届けるナビゲーションは、この広告SDKコールバックとは完全に独立した
      // タイミングで動く app._inject_ad_result_check() が行う。
      var payload = {
        status: status,
        nonce: NONCE,
        reason: reason || null,
        ts: Date.now(),
      };
      window.top.localStorage.setItem('toris_ad_pending_result', JSON.stringify(payload));
    } catch (e) {
      log('reportResult failed: ' + e);
    }
  }

  var settled = false;
  var startTimer = null;
  var watchTimer = null;

  function clearTimers() {
    if (startTimer) { clearTimeout(startTimer); startTimer = null; }
    if (watchTimer) { clearTimeout(watchTimer); watchTimer = null; }
  }

  function finish(status, reason) {
    if (settled) return;
    settled = true;
    clearTimers();
    reportResult(status, reason);
  }

  // 安全弁1(開始前): initialize/prepare/show のどこで止まっても、
  // 広告が実際に表示される前に12秒経てば失敗扱いにする。
  startTimer = setTimeout(function () {
    log('タイムアウト: 12秒たっても広告が始まらない(init/prepare/showのどこかで停止)');
    finish('fail', 'timeout_before_start');
  }, 12000);

  try {
    var win = window.parent;
    if (!win.Capacitor || !win.Capacitor.isNativePlatform || !win.Capacitor.isNativePlatform()) {
      log('Web版のため広告SDKなし');
      finish('unavailable'); // Web版(通常ブラウザ)には広告SDKが無い
      return;
    }
    var AdMob = win.Capacitor.Plugins && win.Capacitor.Plugins.AdMob;
    if (!AdMob) {
      log('AdMobプラグインが見つからない');
      finish('unavailable'); // プラグイン未導入のネイティブビルドでも落とさない
      return;
    }

    var unitId = "__UNIT_ID__";
    var isTesting = __IS_TESTING__;
    var earned = false;

    AdMob.addListener('onRewardedVideoAdLoaded', function () {
      log('event: Loaded');
    });
    AdMob.addListener('onRewardedVideoAdShowed', function () {
      log('event: Showed(広告が表示された。安全弁を延長)');
      // 安全弁2(視聴中): 実際に表示されたら、開始前タイマーを止めて
      // 視聴完了(Dismissed)が万一来ない異常系向けの長め安全弁に切り替える。
      if (startTimer) { clearTimeout(startTimer); startTimer = null; }
      watchTimer = setTimeout(function () {
        log('タイムアウト: 表示後90秒たってもDismissedが来ない');
        finish('fail', 'timeout_after_show');
      }, 90000);
    });
    AdMob.addListener('onRewardedVideoAdReward', function () {
      log('event: Reward獲得');
      earned = true;
    });
    AdMob.addListener('onRewardedVideoAdDismissed', function () {
      log('event: Dismissed (earned=' + earned + ')');
      finish(earned ? 'success' : 'fail', earned ? undefined : 'dismissed_without_reward');
    });
    AdMob.addListener('onRewardedVideoAdFailedToShow', function (err) {
      log('event: FailedToShow ' + (err && err.message ? err.message : ''));
      finish('fail', 'failed_to_show');
    });
    AdMob.addListener('onRewardedVideoAdFailedToLoad', function (err) {
      log('event: FailedToLoad ' + (err && err.message ? err.message : ''));
      finish('fail', 'failed_to_load');
    });

    function playAd() {
      log('prepareRewardVideoAd を呼び出します');
      AdMob.prepareRewardVideoAd({ adId: unitId, isTesting: isTesting })
        .then(function () {
          log('prepareRewardVideoAd 完了、showRewardVideoAd を呼び出します');
          return AdMob.showRewardVideoAd();
        })
        .catch(function (e) {
          log('prepare/show が失敗: ' + (e && e.message ? e.message : e));
          finish('fail', 'prepare_or_show_rejected');
        });
    }

    if (!win.__torisAdmobInitialized) {
      win.__torisAdmobInitialized = true;
      log('AdMob.initialize() を呼び出します');
      AdMob.initialize().then(function () {
        log('initialize 完了');
        playAd();
      }).catch(function (e) {
        log('initialize が失敗: ' + (e && e.message ? e.message : e));
        finish('fail', 'init_rejected');
      });
    } else {
      log('初期化済みのため playAd へ');
      playAd();
    }
  } catch (e) {
    log('想定外の例外: ' + e);
    finish('fail', 'exception'); // Capacitor非搭載環境・ブリッジ未接続等で失敗しても本編には影響させない
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

    st.caption(t(
        "🎬 広告を読み込んでいます……見終わると自動で戻ります"
        "(10秒ほど始まらない場合は自動的に終了します)。"
    ))
    unit_id = _load_admob_rewarded_unit_id()
    is_testing = unit_id == _ADMOB_TEST_REWARDED_UNIT_ID
    js = (
        _ADMOB_REWARD_JS_TEMPLATE
        .replace("__NONCE__", str(pending.get("nonce", "")))
        .replace("__UNIT_ID__", unit_id)
        .replace("__IS_TESTING__", "true" if is_testing else "false")
    )
    components.html(js, height=0)
    if st.button(t("キャンセルする"), key=f"{key_prefix}_{pending_key}_cancel_btn"):
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
        f"<span style='color:#9a9078;font-size:0.82em;'>{t('🌾 広告スペース(準備中)')}</span>"
        "<div style='font-size:0.76em;color:#b0a890;margin-top:2px;'>"
        f"{t('実際の広告はまだ配信していません・ラジオ再生中は表示しません')}"
        "</div></div>",
        unsafe_allow_html=True,
    )


# 2026-07-09 追記(CEO確定仕様): 広告リワードは「庭アイテムをランダムで1つ」
# の1本に一本化した。以前あった案A(小枝を確定付与・render_twig_reward_button)、
# および「見ると到来確率が上がる」という未接続のダミー案
# (render_reward_ad_button)は削除した(交渉不能の原則4「生態に誠実」——
# 到来確率を広告で恣意的に操作する概念は採用しない、という判断を明文化)。
# 実質1種類のボタンにすることで、AdMobフロー(P0の安定化対象)もシンプルになる。


def render_garden_item_button(session_state, biome_id, birds_data, place_fn,
                              key_prefix: str = "ads") -> None:
    """庭アイテム(garden_items.py・6種)配置リワード(1日1回・6時間持続)。

    2026-07-09 追記(CEO確定仕様): 「選ぶ」UIを廃止し、完全ランダムで1つ
    付与する方式に一本化した(このリワードが広告ボタンの唯一の種類になる)。
    今のバイオームで意味を持つアイテム(既存の `garden_items.is_available` の
    制約=例: ハチドリ用給餌器はシャーロットのみ、をそのまま踏襲)の中から
    等確率で1つ選ぶ。アイテム自体・数値効果は一切変更しない。

    実際の配置処理は `place_fn(item_id)` に委譲する(app.py 側が
    session_state["garden_item_placement"] を更新する)。

    ADMOB_ENABLED=True のときは、押しても即時配置せず
    `session_state["ads_pending_garden_item"]` に選んだアイテムと乱数(nonce)を
    積んで広告視聴フローへ回す(実際の配置は `app._handle_ad_reward_result()` が
    視聴完了イベントを受け取ってから行う)。ADMOB_ENABLED=False(既定)のときは、
    これまでどおり即時配置のまま(壊さない)。
    """
    import random
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ
    import garden_items as gi

    flag_key = "garden_item_claimed_date"
    pending_key = "ads_pending_garden_item"
    with st.expander(t("🎁 応援広告(庭に道具をひとつ)"), expanded=False):
        active = session_state.get("garden_item_placement")
        if gi.is_active(active):
            item = gi.ITEMS.get(active.get("item_id"), {})
            hrs = gi.hours_remaining(active)
            st.caption(t(
                "{emoji} 今は「{name}」を置いています(あと{hrs}時間)。",
                emoji=item.get('emoji', ''), name=t(item.get('name', '')),
                hrs=f"{hrs:.1f}",
            ))
            return
        if has_claimed_today(session_state, flag_key):
            st.caption(t("✓ 今日はもう受け取りました。また明日。"))
            return

        if render_pending_ad_loader(session_state, pending_key, key_prefix=key_prefix):
            return  # 広告視聴中: 通常のボタンUIは隠す

        available_items = [
            item_id for item_id in gi.ITEM_ORDER
            if gi.is_available(item_id, biome_id, birds_data)
        ]
        st.caption(t(
            "見ると、アメリカの裏庭インテリアショップから、ランダムで道具を"
            "1つもらえます。庭に6時間だけ置けるおまけです。見なくても庭の"
            "進み方はいつもどおりです。"
        ))
        if not available_items:
            st.caption(t("今のこの庭では、まだ選べる道具がありません。"))
            return
        if st.button(
            t("▶ 広告を見て、道具をもらう"),
            key=f"{key_prefix}_item_random_btn",
            use_container_width=True,
        ):
            item_id = random.choice(available_items)
            if ADMOB_ENABLED:
                session_state[pending_key] = {
                    "nonce": uuid.uuid4().hex, "item_id": item_id,
                }
            else:
                place_fn(item_id)
                mark_claimed_today(session_state, flag_key)
            st.rerun()
