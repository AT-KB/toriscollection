package com.toriscollection.app;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 2026-07-13 重大インシデント対応(保険・案2)。
 *
 * 根本原因はサーバー側のCORS設定(Streamlitの enableCORS=false、
 * toris_collection/.streamlit/config.toml 参照)で対処済みだが、それでも
 * 何らかの理由でWebSocket接続が確立できず、本編(タブ群)が一切描画されない
 * まま白紙/ネイティブスプラッシュで固まってしまった場合の保険として、
 * 一定時間後に自動でWebViewを1回だけリロードする仕組みをここに追加する。
 *
 * 仕組み:
 *  - Web側(app.py の `_inject_splash_hide()`)は、実際にタブ群が描画された
 *    直後(=本編が表示できた瞬間)に `window.AndroidWatchdog.markLoaded()` を
 *    呼ぶ。Web版(通常ブラウザ)や本インターフェース未登録のビルドでは
 *    `window.AndroidWatchdog` 自体が存在しないため、既存のtry/catchで
 *    無害にスキップされ、一切影響しない。
 *  - このActivityは起動から `WATCHDOG_TIMEOUT_MS` 後に `markLoaded()` が
 *    一度も呼ばれていなければ「固まった」とみなし、WebViewをリロードする。
 *  - リロード後も同じ監視をやり直すが、`MAX_RELOAD_ATTEMPTS` 回までしか
 *    リロードしない(無限リロードループの防止)。上限に達しても直らない
 *    場合は監視を打ち切り、それ以上は何もしない。
 *  - 正常時(数秒でスプラッシュが解除されるケース)は `markLoaded()` が
 *    タイムアウトよりずっと早いタイミングで呼ばれるため、`reload()` は
 *    一度も発生しない。
 */
public class MainActivity extends BridgeActivity {

    /** この時間内に本編描画の合図が無ければ「固まった」とみなす。 */
    private static final long WATCHDOG_TIMEOUT_MS = 25_000L;

    /** 自動リロードを試みる最大回数(無限ループ防止)。 */
    private static final int MAX_RELOAD_ATTEMPTS = 2;

    private final AtomicBoolean contentLoaded = new AtomicBoolean(false);
    private final AtomicInteger reloadAttempts = new AtomicInteger(0);
    private final Handler watchdogHandler = new Handler(Looper.getMainLooper());

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView != null) {
            webView.addJavascriptInterface(new WatchdogBridge(), "AndroidWatchdog");
        }

        scheduleWatchdogCheck();
    }

    private void scheduleWatchdogCheck() {
        watchdogHandler.postDelayed(this::runWatchdogCheck, WATCHDOG_TIMEOUT_MS);
    }

    private void runWatchdogCheck() {
        if (contentLoaded.get()) {
            return; // 正常に本編が描画済み。これ以上は監視しない。
        }
        if (reloadAttempts.get() >= MAX_RELOAD_ATTEMPTS) {
            return; // 上限まで試みても直らない場合は諦める(無限リロード防止)。
        }
        reloadAttempts.incrementAndGet();
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().reload();
        }
        // リロード後に描画されるかどうかも、同じ仕組みでもう一度だけ監視する。
        scheduleWatchdogCheck();
    }

    /** Web側(app.py)から「本編が描画された」ことをネイティブ側に伝えるためのブリッジ。 */
    private class WatchdogBridge {
        @JavascriptInterface
        public void markLoaded() {
            contentLoaded.set(true);
        }
    }
}
