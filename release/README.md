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

## ⚠️ いま置いてある AAB は「広告なし」の版

`toris-collection-2.0.0-7.aab` は **2026-08-20 のビルドで、広告は入っていない**。
そのまま Play に上げてよい。

**その後（2026-08-21）に広告を実装した。** いま `flutter build appbundle` で
作り直すと**テスト用の広告ユニット**が入った版になる（`lib/ads/ads.dart` の
`kUseTestAds = true`）。広告版を出すときは、
`toris_collection/docs/team/proposals/2026-08-21_広告のFlutter移植_設計.md` §10
の「公開の前にやること」を先に片づけること。
