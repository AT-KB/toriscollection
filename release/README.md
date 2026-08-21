# リリース成果物(Play にアップロードするもの)

`toris-collection-<versionName>-<versionCode>.aab` が **Play Console に上げる実体**。
中身は `toris_app` の `flutter build appbundle --release` の出力そのまま
(`build/app/outputs/bundle/release/app-release.aab` のコピー)。

## 作り直す

    cd toris_app
    flutter build appbundle --release
    cp build/app/outputs/bundle/release/app-release.aab \
       ../release/toris-collection-<versionName>-<versionCode>.aab

バージョンは `toris_app/pubspec.yaml` の `version:`(`+` の右が versionCode)。

## 上げる前に必ず確かめる

    keytool -printcert -jarfile release/<file>.aab | grep SHA256

**公開済みの鍵の指紋と一致していること**:

    E2:9D:2C:40:2C:B2:26:64:F5:D1:3F:C1:45:4F:27:8D:BF:23:31:2C:10:F2:80:E7:2E:3C:00:76:7D:6C:45:F7

一致しない AAB は Play が受け付けない。鍵の実体は
`C:\Users\kubok\TorisCollection-ReleaseKeys\`(**このリポジトリには入れない**)。

## git には入れない

`.aab` は 89MB あるので `.gitignore` 済み。この README だけ管理する。

## いま置いてあるもの

`toris-collection-2.0.0-8.aab` — **広告あり・本番ユニット**の Flutter 版。

- versionCode **8**(7 はアップロード済みだが「非アクティブ」で再利用できない)
- `kAdsEnabled = true` / `kUseTestAds = false`(本番ユニット)
- 開発機(Pixel 6a)は `kTestDeviceIds` に登録済み。**本番ユニットでもテスト広告**が
  返るので、自分で触っても無効なトラフィックにならない。
  ⚠️ **ID はアプリごとに変わる。** 実機のログで毎回確かめること:
  `adb logcat -d | grep setTestDeviceIds`

### Play Console で必要なこと(広告を入れたので)

1. **「広告が含まれる」に変更**
2. **データセーフティを出し直す**(広告 ID の収集・第三者との共有)
3. **製品版**のリリースに 8 を入れて公開する — 7 は非アクティブのままなので
   端末には古い 6 が配られ続ける
