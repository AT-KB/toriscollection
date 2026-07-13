package com.toriscollection.app;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
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
 *  - 正常時(数秒でスプラッシュが解除されるケース)は `markLoaded()` が
 *    タイムアウトよりずっと早いタイミングで呼ばれるため、`reload()` は
 *    一度も発生しない。
 *
 * 2026-07-13追記(仮説4・原因特定、CEO実機報告後の再調査): 仮説1(CORS)は
 * 実機でWebSocketハンドシェイクが101で成功していたため否定、仮説2
 * (permessage-deflate圧縮)は `enableWebsocketCompression=false` を追加しても
 * 実機で症状が再現し否定、仮説3(User-Agentの"; wv)"マーカー)はPlay Console
 * 再審査待ちで未検証のままだった。`render.yaml` に明記の通り、本番ホスティング
 * (Render無料プラン)は一定時間アクセスが無いとスリープし、次回アクセス時に
 * コールドスタート(数十秒〜1分程度)がかかる。旧 `WATCHDOG_TIMEOUT_MS`(25秒)
 * はこれより明確に短く、コールドスタート中に「固まった」と誤判定して
 * reload()してしまう可能性があったため、90秒に引き上げた。
 *
 * 2026-07-13 さらに追記(実機・エミュレータいずれも本開発環境では用意できず、
 * 開発機がWindows on ARM64であるためAndroidエミュレータ自体が原理的に
 * 動かせないことを確認済み。Google公式配布に windows_aarch64 版の
 * エミュレータバイナリが存在しないこと、x86_64版バイナリはARM64ホスト上で
 * ハードウェア支援仮想化が無いため起動を拒否すること、arm64版システム
 * イメージはQEMU2がホストアーキテクチャ不一致を理由に拒否することを
 * それぞれ実際にダウンロード・実行して確認した)。
 *
 * 代わりに、ローカルStreamlit + 自作の遅延プロキシ(TCPバイトを一定時間
 * 保留してからバックエンドへ中継する、Renderのコールドスタートを模した
 * もの)をPlaywright(Chromium。Android WebViewと同じBlinkエンジン)から
 * 開いて検証したところ、**バックエンドの応答が遅れているだけであれば、
 * 待てば必ずタブ群まで正常に描画される**ことを確認した(遅延75秒→
 * 解放後 約5秒でタブ描画まで完了)。つまりフロントエンド側の描画ロジック
 * 自体は壊れておらず、「待てば直る」という前提は成立する。
 *
 * その一方で、このファイルの**旧実装には別の独立したバグ**があった:
 * `MAX_RELOAD_ATTEMPTS`(旧: 2回)を使い切ると監視を完全に打ち切り、
 * それ以降は二度と何もしなくなっていた。つまり原因が何であれ
 * (Renderのコールドスタートが想定より長引いた、Cloudflareが一時的に
 * 詰まった等)、`WATCHDOG_TIMEOUT_MS × (MAX_RELOAD_ATTEMPTS + 1)`
 * (旧: 25秒×3=75秒、90秒化後でも90秒×3=270秒)を超える遅延が
 * 一度でも起きると、**その後サーバーが実際に応答可能になっても
 * 二度と自動回復しない**設計になっていた。これは「サーバーが遅いだけ」
 * という一過性の問題を「アプリが永久に固まる」という致命的な症状に
 * 変換してしまう、根本原因とは独立したロジック上の欠陥だった。
 *
 * 対応: 上限に達しても監視を完全に打ち切らず、間隔を徐々に伸ばしながら
 * (90秒→90秒→5分→5分…)無期限に監視・再試行を続けるようにした
 * (`markLoaded()` が呼ばれた時点で即座に監視を終了するのは従来通り)。
 * これにより、原因がサーバー側の一時的な遅延・詰まりである限り、
 * ユーザーが手動で強制終了・再起動しなくても最終的には自動回復する。
 * 仮説1〜3のUser-Agent対策(`stripWebViewMarkerFromUserAgent`)自体は
 * 無害な変更のため元に戻さず残す。
 */
public class MainActivity extends BridgeActivity {

    /**
     * この時間内に本編描画の合図が無ければ「固まった」とみなす。
     * Renderコールドスタート(最大1分程度)+ データ読み込み(数秒〜十数秒)+
     * 安全マージンを見込み90秒に設定(旧: 25秒。2026-07-13仮説4対応、
     * クラス冒頭コメント参照)。
     */
    private static final long WATCHDOG_TIMEOUT_MS = 90_000L;

    /**
     * 序盤(この回数まで)は `WATCHDOG_TIMEOUT_MS` 間隔でリロードを試みる。
     * これを超えたら `BACKOFF_INTERVAL_MS` 間隔に切り替える(電池・通信量への
     * 配慮。2026-07-13追記: 旧実装はここで監視自体を完全に打ち切っていたが、
     * それが「一時的な遅延が永久フリーズに化ける」バグの直接原因だったため、
     * 打ち切らず間隔を伸ばして無期限に継続する方式に変更した)。
     */
    private static final int INITIAL_PHASE_ATTEMPTS = 2;

    /** 序盤フェーズを過ぎた後のリロード間隔(5分)。 */
    private static final long BACKOFF_INTERVAL_MS = 5 * 60_000L;

    private final AtomicBoolean contentLoaded = new AtomicBoolean(false);
    private final AtomicInteger reloadAttempts = new AtomicInteger(0);
    private final Handler watchdogHandler = new Handler(Looper.getMainLooper());
    private Runnable watchdogRunnable;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView != null) {
            webView.addJavascriptInterface(new WatchdogBridge(), "AndroidWatchdog");
            stripWebViewMarkerFromUserAgent(webView);
            // 2026-07-13 実機ログで直接確認(仮説6): 接続実機のlogcatに
            // "cc/tiles/tile_manager.cc:1008 WARNING: tile memory limits exceeded,
            // some content may not draw" が繰り返し出力され、その直後から一切の
            // ラスタライズが行われなくなり画面が黒いまま固まっていた。同じログで
            // react-dom.js の実行や本アプリ独自のconsole.log([TorisSave]...)は
            // 正常に発生しており、JS/DOM/WebSocketは機能していた。つまり
            // 「メッセージが流れない」のではなく、埋め込みWebViewのGPUタイル
            // メモリ予算が(単体のChromeアプリより小さく)不足し、コンポジタが
            // 実際の画面への描画(ペイント)に失敗していたことが根本原因である
            // 可能性が高い。ハードウェアレイヤ(GPU合成)を使わずソフトウェア
            // 合成に切り替えることで、このタイルメモリ予算の制約自体を回避する。
            webView.setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        }

        scheduleWatchdogCheck(WATCHDOG_TIMEOUT_MS);
    }

    @Override
    public void onDestroy() {
        // Activity破棄後にタイマーが残り続けて無駄なreload()を呼ばないよう、
        // 保留中のwatchdogコールバックを確実に解除する。
        if (watchdogRunnable != null) {
            watchdogHandler.removeCallbacks(watchdogRunnable);
        }
        super.onDestroy();
    }

    /**
     * 2026-07-13追記(仮説3・検証中): 実機で取得したWebSocketリクエストの
     * User-Agentに、埋め込みWebViewであることを示す "; wv)" マーカーが
     * 含まれていることを確認した(例:
     * "Mozilla/5.0 (Linux; Android 16; ...; wv) ... Chrome/149...")。
     * 本アプリはRender→Cloudflare経由で配信されており、CDN/ボット対策の
     * 一部はこの "wv" マーカーを見て埋め込みWebView由来の通信を検知し、
     * 通常のブラウザと異なる扱い(接続は許可するがデータ配信を絞る等)を
     * する場合がある。通常のChromeアプリ(このマーカーが無い)では問題なく
     * 動作する一方、本アプリ(WebView)だけが「WebSocketは繋がるがメッセージが
     * 一切流れない」状態を実機で確認済みであることと矛盾しない仮説のため、
     * このマーカーを取り除いたUser-Agentに上書きして切り分ける。
     */
    private void stripWebViewMarkerFromUserAgent(WebView webView) {
        WebSettings settings = webView.getSettings();
        String currentUa = settings.getUserAgentString();
        if (currentUa == null) {
            return;
        }
        String strippedUa = currentUa
                .replace("; wv)", ")")
                .replace(" wv)", ")");
        if (!strippedUa.equals(currentUa)) {
            settings.setUserAgentString(strippedUa);
            // Capacitorが起動時に既に発行した初回loadUrl()が、UA変更前の設定で
            // リクエストを飛ばしてしまう競合を避けるため、設定直後に明示的に
            // 再読み込みする(ネイティブスプラッシュが隠れている間に起きるため
            // ユーザーには見えない)。
            webView.reload();
        }
    }

    private void scheduleWatchdogCheck(long delayMs) {
        watchdogRunnable = this::runWatchdogCheck;
        watchdogHandler.postDelayed(watchdogRunnable, delayMs);
    }

    private void runWatchdogCheck() {
        if (contentLoaded.get()) {
            return; // 正常に本編が描画済み。これ以上は監視しない。
        }
        int attempt = reloadAttempts.incrementAndGet();
        if (getBridge() != null && getBridge().getWebView() != null) {
            getBridge().getWebView().reload();
        }
        // 2026-07-13修正: 以前はここで一定回数を超えると監視を完全に
        // 打ち切っていた(=サーバーが後で応答可能になっても二度と自動回復
        // しなかった)。原因がサーバー側の一時的な遅延・詰まりである限り
        // 自動回復できるよう、間隔を伸ばしながら監視を無期限に継続する。
        long nextDelay = attempt < INITIAL_PHASE_ATTEMPTS ? WATCHDOG_TIMEOUT_MS : BACKOFF_INTERVAL_MS;
        scheduleWatchdogCheck(nextDelay);
    }

    /** Web側(app.py)から「本編が描画された」ことをネイティブ側に伝えるためのブリッジ。 */
    private class WatchdogBridge {
        @JavascriptInterface
        public void markLoaded() {
            contentLoaded.set(true);
        }
    }
}
