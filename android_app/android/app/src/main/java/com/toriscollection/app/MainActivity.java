package com.toriscollection.app;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.ImageView;

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

    /**
     * Toris Collection のセージ色(#ecf1e3)。システムスプラッシュの地色・
     * WebViewの地色・自前オーバーレイの地色を、すべてこの一色で揃えることで、
     * アイコンをタップした瞬間から本編が描画されるまで色が途切れないようにする。
     */
    private static final int SAGE = 0xFFECF1E3;

    /**
     * 2026-08 起動見た目の刷新で追加。安心メッセージ入りの全画面ロード画面
     * (splash.png)を、システムスプラッシュの後に自前オーバーレイとして重ねて出す。
     * これは本編が描画された合図(`markLoaded()`)で即座に外れるが、万一その合図が
     * 一度も来ない場合の保険として、この上限時間でオーバーレイだけは外す
     * (WebView地色はセージのまま、watchdog は別途リロードを継続)。watchdog の
     * 初回リロード(90秒)に一度チャンスを与えてから外れるよう、それより長くする。
     * 通常は本編描画時に即座に外れるため、ウォーム起動が固定待ちになることはない。
     */
    private static final long OVERLAY_SAFETY_TIMEOUT_MS = 100_000L;

    private final AtomicBoolean contentLoaded = new AtomicBoolean(false);
    private final AtomicInteger reloadAttempts = new AtomicInteger(0);
    private final Handler watchdogHandler = new Handler(Looper.getMainLooper());
    private Runnable watchdogRunnable;

    /** 安心メッセージ入りの全画面ロード画面(splash.png)を描く自前オーバーレイ。 */
    private View birdOverlay;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Android 12+ のシステムスプラッシュ(セージ地 + 鳥アイコン、styles.xml の
        // AppTheme.NoActionBarLaunch)を正しくセットアップし、最初のフレーム描画後に
        // 自動で消えるようにする。androidx 規約により super.onCreate() より前に呼ぶ。
        // Capacitor の SplashScreen プラグインは launchShowDuration:0 で起動時スプラッシュを
        // 無効化してあるため、ここでの installSplashScreen が二重にならない。
        androidx.core.splashscreen.SplashScreen.installSplashScreen(this);

        super.onCreate(savedInstanceState);

        WebView webView = getBridge() != null ? getBridge().getWebView() : null;
        if (webView != null) {
            // コールドスタート中、本編が描画されるまで WebView 自体の地色が素の白に
            // ならないようセージにする(白画面のちらつき防止・二重の保険)。
            webView.setBackgroundColor(SAGE);
            webView.addJavascriptInterface(new WatchdogBridge(), "AndroidWatchdog");
            // 鳴き声で起こす目覚まし(2026-08-11)。Web 側(radio.py)から
            // window.AndroidAlarm.setAlarm(...) で呼ぶ。Web 版(通常ブラウザ)には
            // このオブジェクト自体が存在しないため、Web 側は try/catch で素通りする。
            webView.addJavascriptInterface(new BirdAlarmBridge(this), "AndroidAlarm");
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

        showBirdOverlay();
        scheduleWatchdogCheck(WATCHDOG_TIMEOUT_MS);
    }

    /**
     * 安心メッセージ入りの全画面ロード画面(セージ地 + 鳥 + 「First launch can take
     * up to 30 seconds」)を、WebViewの上に重ねて表示する。
     *
     * なぜシステムスプラッシュだけでは足りないか: Android 12+ のシステム
     * スプラッシュ(styles.xml)は「背景色 + 中央アイコン」しか描けず、テキストも
     * 長時間の保持もできない。一方 server.url でリモートを直読みする構成のため、
     * Renderのコールドスタート(数十秒)中はどうしても待ち時間が生じる。そこで
     * システムスプラッシュが最初のフレームで自動的に消えた直後、その裏に既に
     * 用意してあるこのオーバーレイ(splash.png)が現れ、本編が実際に描画される
     * 合図(`markLoaded()`)が来た瞬間に外れる。両者ともセージ地のため境目は
     * 目立たず、タップ〜本編まで色・鳥が途切れない。
     */
    private void showBirdOverlay() {
        try {
            ViewGroup content = findViewById(android.R.id.content);
            if (content == null) {
                return;
            }
            int splashId = getResources().getIdentifier("splash", "drawable", getPackageName());
            if (splashId == 0) {
                return;
            }
            ImageView overlay = new ImageView(this);
            overlay.setImageResource(splashId);
            // FIT_CENTER: 画像全体を必ず画面内に収める(縦横比を保ったまま縮小)。
            // 以前は CENTER_CROP で画面高さに合わせて拡大していたため、縦長画面
            // (例 1080x2424 ≒ 20:9)では横1280pxの splash.png の左右が見切れ、
            // 「Getting the garden ready」の先頭G・末尾yなどテキスト両端が切れていた
            // (実機 Pixel 9a/Android 16 で確認)。FIT_CENTER なら上下(または左右)に
            // 余白ができるが、オーバーレイ地色をセージ(SAGE、splash.png の地色と一致)で
            // 塗ってあるため余白もセージで埋まり、黒帯/白帯は視覚的に出ず、テキストは
            // どの画面比率でも全文が切れずに表示される。
            overlay.setScaleType(ImageView.ScaleType.FIT_CENTER);
            overlay.setBackgroundColor(SAGE);
            // 背後のWebViewへ誤タップが抜けないようにする(表示中は操作を吸収)。
            overlay.setClickable(true);
            content.addView(
                overlay,
                new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            );
            birdOverlay = overlay;
            // 保険(OVERLAY_SAFETY_TIMEOUT_MS のコメント参照)。
            watchdogHandler.postDelayed(this::hideBirdOverlay, OVERLAY_SAFETY_TIMEOUT_MS);
        } catch (Exception e) {
            // オーバーレイ生成に失敗しても本編には一切影響させない。
        }
    }

    /** 全画面ロード画面のオーバーレイを、軽くフェードアウトして取り除く(冪等)。 */
    private void hideBirdOverlay() {
        final View overlay = birdOverlay;
        if (overlay == null) {
            return;
        }
        birdOverlay = null;
        try {
            overlay
                .animate()
                .alpha(0f)
                .setDuration(250)
                .withEndAction(() -> {
                    try {
                        ViewGroup parent = (ViewGroup) overlay.getParent();
                        if (parent != null) {
                            parent.removeView(overlay);
                        }
                    } catch (Exception e) {
                        // 取り外し失敗は無害(次のActivity破棄で解放される)。
                    }
                })
                .start();
        } catch (Exception e) {
            // アニメーション不可の環境でも、少なくとも参照は手放してある。
        }
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
            // 本編が実際に描画された合図。全画面ロード画面のオーバーレイを外す
            // (JSブリッジは別スレッドで呼ばれるため、UIスレッドへポストする)。
            // ウォーム起動ではこの合図が数秒で来るため、固定待ちにはならない。
            watchdogHandler.post(MainActivity.this::hideBirdOverlay);
        }
    }
}
