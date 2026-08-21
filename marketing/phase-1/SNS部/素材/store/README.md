# Google Play の掲載素材(2026-08-20 更新)

実機 Pixel 6a(1080x2400)の **release ビルド**で撮影。
撮り直しの元になった APK は `flutter build apk --release`(versionCode 7)。

## Play の条件を満たしていること
- スクショは **1080x2160**(縦横比ちょうど 1:2)。端末は 1080x2400 = 1:2.22 で
  **Play の上限 1:2 を超える**ため、上下を切って 2160 にしてある。
  切る量は毎回測った値: **上 100px / 下 140px**
  (ステータスバーの文字は y=86 で終わり、ナビゲーションバーは y=2274 から)。
- 24bit PNG、320px〜3840px の範囲内。
- フィーチャーグラフィックは **1024x500**。

## ⚠️ release ビルドで撮ること
debug ビルドには右上に **DEBUG の赤い帯**が出る。ストアに出したら
未完成に見えるので、必ず `flutter build apk --release` で撮る。

    flutter build apk --release
    adb install -r build/app/outputs/flutter-apk/app-release.apk

⚠️ OneDrive 配下だと `build/.cxx` のロックで release ビルドが
`AccessDeniedException` で落ちることがある。`build/.cxx` を消してから
やり直すと通る。

⚠️ ステータスバーは demo mode で整えてから撮る(時刻 9:00・電池100・通知なし)。
撮り終わったら **必ず戻す**:

    adb shell am broadcast -a com.android.systemui.demo -e command exit
    adb shell settings put global sysui_demo_allowed 0

## 中身

| ファイル | 画面 | 何を見せているか |
|---|---|---|
| 01_garden | 庭 | 裏庭・餌台・リス・鷹・植えたもの・来ている鳥 |
| 02_guide | 図鑑 | American Goldfinch の図版と、好きなもの・なぜ来たか |
| 03_radio | ラジオ | 土地の鳥の顔ぶれ、鳴いている鳥の点、環境音 |
| 04_wake | 目覚まし | 1羽目を選ぶ、2羽目以降は出会った鳥から |
| 05_network | 食物網 | 植物→虫→鳥のつながり(実データ) |
| 06_away | 留守中の到来 | 「While you were away」— 開いていない間に鳥が来ていた |
| feature_graphic | フィーチャーグラフィック | 1024x500(Play で必須)。`tools/store_feature_graphic.py` で生成 |

06 は**受動性(原則1)がそのまま映っている唯一の画面**。何もしていない間に
Red-bellied Woodpecker が寄っていた、という実際の復帰ダイアログ。

## フィーチャーグラフィックの作り直し

    py -3 tools/store_feature_graphic.py

絵は `toris_app/assets/sprites/` の**アプリ本物のドット絵**、色は
`theme.dart` / `tree_scene.dart` の実値、文言は `landing/page.html` の
確定コピーだけを使っている(原則4)。フォントは Flutter SDK 同梱の
Roboto(Apache-2.0)。

## まだ足りないもの
- タブレット用(7インチ/10インチ)は任意。
- アプリ名の最終決定は CEO(`marketing/phase-s/SNS部/store_listing_prep.md` の A/B 案)。
