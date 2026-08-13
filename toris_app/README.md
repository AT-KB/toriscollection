# toris_app — Flutter 版(移行中)

**移行の目的そのもの(目覚まし・通知・端末連携)を最初に立てる**ための本体。
図鑑・庭・ラジオは現行版(Streamlit)が動いているので後回し
(提案書 §4「移行中、何も出荷できなくなる」のを避ける)。

## いま入っているもの

- **目覚まし**: 時刻と鳥を選んでセット/解除。設定状態の表示。
  Android 12+ の「正確なアラーム」が未許可なら、設定画面へ案内する。

## ネイティブ側は Capacitor 版からそのまま移した

| ファイル | 出所 | 変更 |
|---|---|---|
| `BirdAlarmService.java` | android_app | パッケージ名のみ |
| `BirdAlarmSounds.java` | android_app | パッケージ名のみ |
| `BirdAlarmReceiver.java` | android_app | パッケージ名と action 文字列のみ |
| `AlarmChannel.kt` | **新規** | `BirdAlarmBridge`(@JavascriptInterface)の置き換え |

787行の native のうち **325行はそのまま**動いた。Capacitor にも WebView にも
依存していなかったため。置き換えが要ったのは、Web から呼ぶための橋(138行)だけ。

## ⚠ パッケージ名

いまは `com.toriscollection.toris_app`。製品版は `com.toriscollection.app`。
**わざと別にしてある** — 同じにすると、開発中のビルドが実機の Play 版を潰す。
切り替え(提案書 §3 ステップ3)のときに製品版の名前へ変える。
そのときは**セーブコードの互換**を必ず守ること(`toris_core` で双方向確認済み)。

## ビルド

```sh
flutter build apk --release
flutter test
```

OneDrive 配下では `build` と `.dart_tool` を外へのジャンクションにしないと
Gradle が落ちる(理由は `flutter_spike/README.md` と同じ)。

## まだ無いもの

通知の実行時許可の要求(Android 13+)、端末再起動後の再設定、睡眠データ連携
(Health Connect)、ラジオ、図鑑、庭。
