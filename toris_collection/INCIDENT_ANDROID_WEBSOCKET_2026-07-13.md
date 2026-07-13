# インシデント記録: Android版が起動直後に白紙のまま固まる(2026-07-13)

対象: 誰かがこの問題を引き継ぐ場合の一次情報。時系列で経緯・仮説・検証結果を残す。
関連コミット: `dbb737b` `ffa13dd` `601a27b` `c50ec48`、および本ファイル更新時点の最新コミット。

## 結論(現時点、2026-07-13時点の最終メモ)

CEOから提供された一次情報(実機の chrome://inspect 観測の口頭報告、commit ffa13dd
記載の内容)が、**入手できる証拠のすべて**。追加のlogcat・スクリーンショット等は
今後も入手できない前提で、現時点で判明している範囲だけを根拠に修正を反映した。

- **確定した原因(1つ)**: `MainActivity.java` のwatchdog(自動リロード監視)に、
  一定回数リロードすると**監視自体を完全に打ち切り、その後サーバーが復旧しても
  二度と気づかない**という設計上のバグがあった。原因が何であれ(Renderの
  コールドスタート、CDNの詰まり等)、一定時間を超える遅延が一度でも起きると、
  本来一過性のはずの遅延が「永久に固まる」症状に変換されていた。→ **修正済み**
  (無期限バックオフ方式に書き換え。下記「実施した修正」参照)。
- **有力だが未確定の仮説**: Renderの無料プランのコールドスタート
  (最大1分程度)がwatchdogの旧タイムアウト(25秒)より長く、起動中に
  誤判定していた可能性(仮説4)。タイムアウトを90秒に引き上げ済み。
  遅延プロキシでの検証で「待てば直る」こと自体は確認できたが、
  実機のAndroid System WebView固有の挙動差(仮説3のUser-Agent関連含む)は
  実機・エミュレータいずれでも検証できておらず、**完全には排除できていない**。
- **現時点でこれ以上コードから追える手がかりは無い**。次に前進する材料は
  「この修正を実機で動かして、症状が変わるか(直るか/まだ固まるか)を
  見る」という実地の結果のみ。ログが取れなくても、直ったかどうかの
  結果(体感、待てば描画されるようになったか)だけで十分な判断材料になる。

## 症状

- **Android版(Capacitor WebView)** のみ、アプリ起動直後に本編(タブ群)が描画されず、
  ネイティブスプラッシュ/白紙のまま固まる。
- **Web版(通常ブラウザで同じRenderのURLにアクセス)は正常に表示される。**
- 実機の `chrome://inspect` で調べたところ、WebSocketハンドシェイクは101で成功し、
  接続も切れずに維持されている。しかし**メッセージが一切流れず**、描画が進まない
  (この観測自体は生ログ・スクリーンショットが残っておらず、口頭報告ベース)。

## ホスティング構成(前提)

`render.yaml` により、本番は **Renderの無料プラン**(`plan: free`)で運用。
無料プランは一定時間(目安15分)アクセスが無いとスリープし、次回アクセス時に
コールドスタート(数十秒〜1分程度)がかかる仕様。

## これまで検証・実装した仮説(時系列)

### 仮説1: CORS(Origin拒否) → 直接の原因ではない
`enableCORS=false` を追加。実機でWebSocketハンドシェイクは101で成功していたため、
CORSそのもので接続自体が拒否されているわけではないと判断。

### 仮説2: permessage-deflate圧縮 → 否定
`enableWebsocketCompression=false` を追加しても実機で症状は変わらず。

### 仮説3: User-Agentの埋め込みWebViewマーカー("; wv)") → 未検証のまま棚上げ
`MainActivity.java` でマーカー除去処理を追加、Play Console再審査待ちのまま
検証サイクルが重く非効率だったため、本セッションでは実機検証を行っていない。

### 仮説4: Renderコールドスタートとwatchdogタイムアウトの不整合 → 部分的に支持・修正済み
旧 `WATCHDOG_TIMEOUT_MS`(25秒)がRenderのコールドスタート最大時間(〜1分)より
短く、起動中に「固まった」と誤判定してreload()していた可能性を指摘し、90秒に
引き上げ済み(前セッション)。**本セッションでの追加検証で、この仮説の一部を
裏付ける具体的証拠と、それとは独立した別のバグを発見した(下記参照)。**

## 2026-07-13 本セッションでの追加調査(制約なし・証拠優先)

### 試みたが実施できなかったこと: 実機・エミュレータでの再現

開発機のAndroid SDK(`android_app/android/local.properties` が指す
`C:\Users\kubok\AppData\Local\Android\Sdk`)には元々 `emulator` パッケージも
システムイメージも入っていなかった。以下を実際に試し、**このWindows開発機
(Windows on ARM64)ではAndroidエミュレータそのものが原理的に動かせないことを
確認した**(推測ではなく実際にダウンロード・実行して得た一次情報):

1. `sdkmanager --list` で `emulator` パッケージが一覧に出ない。Googleの
   リポジトリXML(`https://dl.google.com/android/repository/repository2-3.xml`)
   を直接確認したところ、`emulator`(revision 15828024)には
   `windows_x64`・`linux_x64`・`darwin_x64`・`darwin_aarch64` の4アーカイブしか
   無く、**`windows_aarch64` 版はGoogleから配布されていない**
   (`<host-arch>x64</host-arch>` 等で明示的にフィルタされている)。
2. `emulator-windows_x64-15828024.zip` を直接ダウンロードしてSDKに手動配置し、
   `system-images;android-34;google_apis;arm64-v8a` を入れて起動を試みたところ:
   `FATAL | Avd's CPU Architecture 'arm64' is not supported by the QEMU2
   emulator on x86_64 host. System image must match the host architecture.`
   → x64ビルドのエミュレータはarm64システムイメージを実行できない。
3. 代わりに `system-images;android-34;google_apis;x86_64` を入れて起動を
   試みたところ: `ERROR | x86_64 emulation currently requires hardware
   acceleration!` / `CPU Acceleration status: Android Emulator requires an
   Intel/AMD processor with virtualization extension support. (Virtualization
   extension is not supported)` → ARM64ホストにはx86向けのハードウェア支援
   仮想化が無く、x64システムイメージも動かせない。

結論: **この開発機ではエミュレータによる再現は不可能**(x64ビルド×arm64イメージは
アーキテクチャ不一致で拒否、x64ビルド×x64イメージはHW仮想化が無く拒否、
そもそもwindows_aarch64ビルド自体がGoogleから配布されていない)。実機
(`adb devices` でも接続なし)も本セッションでは利用できなかった。

### 新たに検証した仮説5(このセッションで発案): components.html iframeの
sandbox属性によるクロスオリジン隔離 → **否定(証拠あり)**

`_inject_splash_hide()`(`app.py`)は `st.components.v1.html()` が作る
sandboxed iframe内から `window.parent.Capacitor` 等にアクセスする。sandbox属性に
`allow-same-origin` が無ければ `window.parent` へのプロパティアクセスで
SecurityErrorが発生し、`SplashScreen.hide()` も `AndroidWatchdog.markLoaded()`
も静かに失敗する(try/catchで握りつぶされる)のではないかと疑い、Playwright
(既存Chromiumバイナリ、Android WebViewと同じBlinkエンジン)でローカルStreamlitを
実際に開いて検証した。

**結果**: 実際のsandbox属性は
`allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox
allow-same-origin allow-scripts allow-downloads` であり、`allow-same-origin` は
含まれている。実際に「新規スタート」→タブ描画まで進めたところ、
`SplashScreen.hide()` 呼び出し・`AndroidWatchdog.markLoaded()` 呼び出しは
**両方とも正常に発生し**、コンソールにもSecurityError等のエラーは一切出なかった
(出たのは無害な `Unrecognized feature` 警告と、意図通りの
`allow-scripts`+`allow-same-origin` 併用に関するChromeの一般的な注意warningのみ)。
→ **この仮説は否定された。** splash-hide/watchdogの仕組み自体はブラウザレベルでは
正しく機能している。

### ローカル保存の自動復元フロー(戻ってきたユーザーの通常経路)の実測

`_inject_local_restore_check()` は、localStorageに保存コードがあると
`window.location.href` でトップウィンドウ全体を `?local_restore=<コード>` 付きで
リロードする(iframe内から直接 `top.location` を書き換えるとsandboxで拒否される
ため、`window.parent.document` に `<script>` を注入する手法を使っている)。
これが「戻ってきたユーザーが毎回、本編に辿り着くまでに実際に何回サーバーへ
往復しているか」を、本番Render環境に対してPlaywrightで実測した
(`page.on("request")` でdocumentリクエスト、`page.on("websocket")` でWS接続の
発生回数を計測。単なる `history.pushState` によるURL見た目上の変化と、実際の
フルページロードを取り違えないよう、ネットワークイベントで直接検証した)。

**結果(Render温間状態)**:
- 実際のdocumentリクエスト(=完全なページロード)は **2回**
  (`/` → `/?local_restore=<code>`)。
- WebSocket接続も **2回**(1回目の接続を明示的にCLOSEしてから2回目をOPEN)。
- `?local_restore=` 処理後にURLが `/` に戻る動きも観測されたが、これは
  `st.query_params.pop("local_restore", None)`(Python側)によるクライアント側の
  URL書き換え(`history.replaceState` 相当)であり、**新しいdocumentリクエストも
  新しいWebSocket接続も伴わない**(証拠: この時点でdocumentリクエスト・WS OPENは
  発生していない)。当初「3回ナビゲーションしている」と誤認しかけたが、
  ネットワークイベントで検証した結果、実質は2回である。
- 所要時間(Render温間・実測): 新規スタートで13秒、その後の「再オープン」
  (reloadで模擬)で8秒弱。

**意味**: 戻ってきたユーザーは毎回、本編(タブ群)に辿り着くまでに
**Streamlitのスクリプト実行とWebSocket接続を2セット**消化する。Renderが
スリープしていた場合、コールドスタートのコストを払うのは基本的に1回目
(ここでプロセスが起動する)で、2回目はプロセスが既に温まっているため
速いはずだが、**旧`MAX_RELOAD_ATTEMPTS`ロジック(下記)と組み合わさると
危険な相互作用になり得る**(1回目の途中でwatchdogが発火してreload()すると、
2回目の遷移が起きる前に振り出しに戻ってしまう可能性がある)。

### 遅延プロキシによる「待てば直るのか」の直接検証

CEOから「待てば直る気がしない」という指摘があったため、実際に検証した。
TCPバイトを一定時間(75秒)保留してからバックエンド(ローカルStreamlit)へ
中継する自作の遅延プロキシを立て、Playwrightでそのプロキシ経由でアプリを開いた
(Renderのコールドスタート=「バックエンドがまだリクエストに応答できない」を
人工的に再現する狙い)。

**結果**: 75秒保留した後、実際にバイトが流れ始めると、ページロード・
ログイン画面描画・タブ群描画までが**約5秒で完走し、正常に最後まで描画された**。
待っている間、ブラウザ側(Blinkエンジン)は特にエラーを出さず、正常に応答を
待ち続けていた。

**意味**: **「待てば直る」という前提はブラウザ/フロントエンド側では成立する**
ことを確認した。つまり、Streamlitのフロントエンドの描画ロジック自体が
コールドスタート的な遅延で壊れるわけではない。

### 新たに発見した、根本原因とは独立したロジック上のバグ(本セッションの主な成果)

`MainActivity.java` の旧実装を精査した結果、**原因が何であれ(Renderのコールド
スタート、Cloudflareの詰まり、その他一時的な要因)、一定の遅延を超えると
二度と自動回復しなくなる設計上の欠陥**を発見した:

```java
private void runWatchdogCheck() {
    if (contentLoaded.get()) return;
    if (reloadAttempts.get() >= MAX_RELOAD_ATTEMPTS) {
        return; // ← ここで監視自体を完全に打ち切って、二度と何もしなくなる
    }
    reloadAttempts.incrementAndGet();
    ...reload()...
    scheduleWatchdogCheck(); // 次のチェックをスケジュール
}
```

`MAX_RELOAD_ATTEMPTS=2` に達すると `runWatchdogCheck()` は即座に `return` し、
**次の `scheduleWatchdogCheck()` が呼ばれない**。つまり
`WATCHDOG_TIMEOUT_MS × (MAX_RELOAD_ATTEMPTS + 1)`
(90秒化後でも 90秒×3 = 270秒)を超えて応答が遅れる状況が一度でも起きると、
**その後サーバーが実際に応答可能になっても、アプリ側は二度と気づかず、
ユーザーが強制終了して再起動するまで永久にそのまま固まる**。

これは「サーバーが遅いだけ」という本来一過性のはずの問題を、「アプリが
永久に固まる」という致命的な症状に**変換してしまう**、根本原因(Render/
Cloudflare/WebView固有の何か)とは独立したロジック上の欠陥であり、
CEOが実機で観測した「WebSocketは繋がっているが永遠に白紙のまま」という
症状と正確に一致する。90秒への引き上げだけでは、この「打ち切り」自体は
解消されない(単に打ち切りまでの時間が延びるだけ)。

## 実施した修正(本セッション)

`MainActivity.java` のwatchdogを、上限に達しても監視を完全に打ち切らず、
間隔を伸ばしながら無期限に継続する方式に変更した:

- 最初の2回は `WATCHDOG_TIMEOUT_MS`(90秒)間隔でreload()を試みる。
- それ以降は `BACKOFF_INTERVAL_MS`(5分)間隔で無期限にreload()を試み続ける
  (`markLoaded()` が呼ばれた時点で即座に監視終了するのは従来通り)。
- Activity破棄時(`onDestroy()`)にタイマーを確実に解除し、リークを防ぐ。

これにより、原因がサーバー側の一時的な遅延・詰まりである限り、ユーザーが
手動で強制終了・再起動しなくても最終的には自動回復するようになった。

## 未検証・引き続き不明なこと

- 実機・エミュレータいずれでも再現できなかったため、**「WS 101成功後に
  メッセージが完全に止まる」という元の観測そのもの**を、本セッションでは
  再現できていない。ローカル環境での検証(仮説5の否定、遅延プロキシでの
  「待てば直る」確認)はいずれも**Blinkエンジン(Chromium)止まり**であり、
  Android System WebView固有の挙動差(仮説3のUser-Agent関連や、実機だけの
  何らかのネットワークスタックの違いなど)を排除できたわけではない。
- Sheets連携(`sheets_client.py`)が本番Renderで実際に設定されているかは
  未確認。設定されていなければ `_sheets_safe()` は `FileNotFoundError` で
  即座に失敗する(ブロッキングしない)ため無関係と考えられるが、もし
  `st.secrets["gcp_service_account"]` が設定されている場合、`gspread.authorize()`
  の初回トークン取得がRenderのネットワーク条件下でハングする可能性は
  理論上否定できていない(コード上は該当パスが今回のローカル保存主体の
  セッション開始経路では通常呼ばれないため、優先度は低いと判断した)。

## 今後の進め方(追加のログは前提にしない)

CEOからログ・スクリーンショット等の追加の一次情報はこれ以上出てこない前提で進める。
次に必要なのは調査ではなく、**この修正を実機で動かした結果**のみ:

- Play Consoleへ再提出し、実機で「症状が二度と直らず固まる」から
  「時間はかかるが最終的に直る(90秒×2回・5分間隔で自動リロードを
  試み続ける)」に変わるかどうかを見る。
- もしそれでも全く直らない(何分待っても白紙のまま)場合は、
  watchdogのロジックの問題ではなく、仮説3(User-Agent)またはまだ
  排除できていないAndroid System WebView固有の要因(実機・エミュレータ
  いずれでも本セッションでは検証不可だった)が本命ということになる。
  その場合は改めて切り分けが必要。
- 直ったかどうかは、ログを取らなくても体感(待てば表示されるか/
  永久に白紙のままか)だけで十分な判断材料になる。
