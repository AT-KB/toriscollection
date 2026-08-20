# Google Play のスクリーンショット(2026-08-20)

実機 Pixel 6a(1080x2400)の **release ビルド**で撮影。

## Play の条件を満たしていること
- **1080x2160**(縦横比ちょうど 1:2)。端末は 1080x2400 = 1:2.22 で
  **Play の上限 1:2 を超える**ため、上下を切って 2160 にしてある
  (上90px=ステータスバー / 下150px=ナビゲーションバー)。
- 24bit PNG、320px〜3840px の範囲内。

## ⚠️ release ビルドで撮ること
debug ビルドには右上に **DEBUG の赤い帯**が出る。ストアに出したら
未完成に見えるので、必ず `flutter build apk --release` で撮る。

    flutter build apk --release
    adb install -r build/app/outputs/flutter-apk/app-release.apk

⚠️ OneDrive 配下だと `build/.cxx` のロックで release ビルドが
`AccessDeniedException` で落ちることがある。`build/.cxx` を消してから
やり直すと通る。

## 中身

| ファイル | 画面 | 何を見せているか |
|---|---|---|
| 01_garden | 庭 | 裏庭・餌台・リス・鷹・植えたもの・来ている鳥 |
| 02_guide | 図鑑 | American Goldfinch の図版と、好きなもの・なぜ来たか |
| 03_radio | ラジオ | 土地の鳥の顔ぶれ、鳴いている鳥の点、環境音 |
| 04_wake | 目覚まし | 1羽目を選ぶ、2羽目以降は出会った鳥から |
| 05_network | 食物網 | 植物→虫→鳥のつながり(実データ) |

## まだ足りないもの
- **フィーチャーグラフィック 1024x500**(Play で必須)。
- タブレット用(7インチ/10インチ)は任意。
