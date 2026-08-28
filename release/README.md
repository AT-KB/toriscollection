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


## いま置いてあるもの(2026-08-28)

| ファイル | 中身 | 状態 |
|---|---|---|
| `toris-collection-2.0.3-11.aab` | **これを上げる。** 広告あり + **ラジオの不具合修正** | 署名確認済み・未アップロード |
| `toris-collection-2.0.2-10.aab` | 1つ前。広告はあるが**ラジオが起動のたび空になる不具合が入ったまま** | **上げない** |

**2.0.3+11 で入ったもの**(`0672333`):
- 🔴 **ラジオが起動のたび空だったのを直した。** `RadioPage` が `initState` で
  1回だけ読み込み、そのとき庭がまだ読めていないので `observed` が空のまま
  固定されていた。**Listen が一度も出ない状態**だった。
  ストア掲載文とLPの「会った鳥の声が聴けるラジオ」は、これを直すまで
  **成り立っていなかった**。
- 目覚ましの説明の単複("the 1 birds" → "1 bird")。

**出す前に通した検証**: `flutter analyze` 新規指摘なし /
`flutter test` 56件 pass / `tools/migration_audit.py` exit 0・問題なし
(未検証 35 → 33 に減少)。

**中身の確認**(`zipfile` で直接見た): AdMob App ID
`ca-app-pub-9002945296291643~1195899268` / INTERNET 権限 /
広告SDKのメタデータ、いずれも入っている。

## git には入れない

`.aab` は 89MB あるので `.gitignore` 済み。この README だけ管理する。

## いま置いてあるもの

`toris-collection-2.0.2-10.aab` — **広告あり・本番ユニット**の Flutter 版。
**アイコンを直した版**(8 は Flutter の初期ロゴのまま出てしまっていた)。

- versionCode **10** / versionName **2.0.2**
- 8 は 2026-08-21 に製品版で公開済み(Play が配信を確認)。
  10 は **ラジオの修正**(会っていない鳥が鳴いていた) + **アイコン**
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

## アイコンは2か所ある(片方は更新不要)

| | どこ | 反映 |
|---|---|---|
| ストアの一覧・DL 画面 | Console `ストアの掲載情報 > アプリアイコン` に `marketing/phase-1/SNS部/素材/store/app_icon_512.png` | **アプリ更新なしで即反映** |
| 端末のホーム画面 | `toris_app/.../res/mipmap-*` | **アプリの更新が要る**(= この 10) |

両方まとめて `py -3 tools/gen_app_icons.py` で作る。素材は
`marketing/phase-1/SNS部/素材/ヘッダー.png`(9羽のドット絵)。

**丸で統一してある**(CEO 2026-08-21)。端末はどのみち丸く切り抜くので、
元絵をそのまま敷くと四隅の3羽が欠ける。**白い円の中に9羽を収める**形に
揃え、アダプティブの背景も白にしてある(継ぎ目を出さないため)。
ストア用は Play が透過を弾くので、円の外はセージ地(#ecf1e3)。
