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

## 🔵 いま上げるもの(2026-11-08)

`toris-collection-2.0.7-15.aab` — versionCode **15** / versionName **2.0.7**。署名一致・広告 ID は `pub-3571`。
リリースノートは `2.0.7-15_リリースノート.txt`。

- **鳥の来るペース**(`toris_core/lib/src/pacing.dart`):3時間で1コマ(実時間に比例・端数は持ち越し)、
  全体×0.5・珍しさ×(1−0.7r)。京都20種を集めるのに約35日(前は26日)
- **庭のなじみ**:開いた日数の合計で Lv0〜4。珍しい鳥ほど伸びる。連続ではない
- **慣れと名前**:近くで6/12/18回会うと名前の枠が1/2/3。来た子が名前のある子なら
  「ルリツグミのピョンタ」。名前は端末ローカル(引っ越しコードには入らない)
- 2.0.6+14 は 2026-11-07 時点で Play 公開済み

## 🔵 いま上げるもの(2026-11-03)

`toris-collection-2.0.6-14.aab` — **日本語版**。versionCode **14** / versionName **2.0.6**。

- 署名 `E2:9D:…:6C:45:F7` 一致 / 広告 ID は `pub-3571`(App ID + バナー + リワード)/ 和名 37/37 種
- リリースノートは `2.0.6-14_リリースノート.txt`(ja-JP / en-US をそのまま貼る)
- 🔴 **13(2.0.5)は Play の審査で却下された**(「ログイン認証情報が無い」)。
  審査担当者がチュートリアル中に右上の「引っ越し」を開き、コード欄をログイン画面と判定した
  (`NGpic.png`)。14 で直した: チュートリアル中はボタンを出さない / 「アカウントやログインは
  ありません」と明記 / 入れる側は「前の端末のコード」と限定
- 中身: 日本語対応(種名まで)・切替ボタン(全タブ右上)・端末が日本語なら日本語で開く・
  儀式の鳥が1羽ずつ動く(2.0 / 2.75 / 3.25秒、敷居120秒)・きょうの道具の説明・
  去った鳥/嵐の一文の日本語
- Play Console の「アプリのアクセス権」は **「すべての機能を特別なアクセス権なしで利用できる」**
- **`USE_EXACT_ALARM` を外した**(Play の制限付き権限。目覚まし・カレンダーが中心機能のアプリだけ)。
  `SCHEDULE_EXACT_ALARM` だけで、未許可なら目覚まし画面が「設定」へ案内する(実機で確認)

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
