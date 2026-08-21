# Google Play への更新版(AAB)を作った(2026-08-20)

CEO「GooglePlay に実装する奴作ってほしい、更新したい最新のやつに」。

**成果物**: `C:\Users\kubok\TorisCollection-Release\toris-collection-2.0.0-7.aab`(89.0MB)

---

## 1. いちばん大事なところ — applicationId を Play 公開済みのものに合わせた

Play に**すでに上がっているのは Capacitor 版**(`android_app/`)で、

| | 公開済み(Capacitor) | 今回作った Flutter 版(変更前) |
|---|---|---|
| applicationId | `com.toriscollection.app` | `com.toriscollection.toris_app` |
| versionCode | 6 | 1 |
| versionName | 1.0.4 | 1.0.0 |
| 署名 | `TorisCollection-ReleaseKeys` の本鍵 | **debug 鍵**(Flutter の初期設定のまま) |

このままでは**別アプリ扱い**になり、既存の掲載を更新できない。Play は
「applicationId が同じ」「署名鍵が同じ」「versionCode がより大きい」の3つが
揃って初めて更新として受け付ける。そこで `toris_app/android/app/build.gradle.kts` の
applicationId を **`com.toriscollection.app`** に変え、本鍵で署名するようにした。

クラス名(`namespace`)は `com.toriscollection.toris_app` のままでよい。ただし
manifest の相対名(`.MainActivity` 等)が applicationId 側に解決されると
起動しなくなるので、**4つとも完全修飾名に書き換えた**(MainActivity /
BirdAlarmReceiver / BirdAlarmService / RadioService)。

## 2. 実際に確かめたこと(推測ではない)

AAB を開いて中身を読んだ結果:

- `applicationId = com.toriscollection.app` ✔
- `versionName = 2.0.0` / `versionCode = 7`(6 より大きい) ✔
- `android:label = "Toris Collection"` ✔ — 変更前は **`Toris (next)`** という
  開発中の名札のままだった。そのまま出したら Play にそう並ぶところだった。
- 署名の SHA-256 が本鍵と**一致**:
  `E2:9D:2C:40:2C:B2:26:64:F5:D1:3F:C1:45:4F:27:8D:BF:23:31:2C:10:F2:80:E7:2E:3C:00:76:7D:6C:45:F7`
  (`keytool -printcert -jarfile <aab>` と keystore の指紋を突き合わせた)
- minSdk 24 / targetSdk 36。Capacitor 版も minSdk 24 なので、
  **更新を受け取れなくなる既存ユーザーはいない**。

## 3. 鍵の置き場所

`toris_app/android/key.properties`(**git には入れない**。`.gitignore` に追加済み)。
中身は `android_app/android/key.properties` と同じもので、鍵の実体は
`C:\Users\kubok\TorisCollection-ReleaseKeys\toris-collection-release.keystore`。

key.properties が無い環境では debug 鍵に落ちるようにしてある
(`flutter run --release` が動くように)。**Play に出すビルドでは必ず
上の SHA-256 と一致しているか確かめること。**

## 4. 作り直す手順

    cd toris_app
    flutter build appbundle --release
    # -> build/app/outputs/bundle/release/app-release.aab

バージョンを上げるときは `pubspec.yaml` の `version: 2.0.0+7` を書き換える
(`+` の右が versionCode)。`android/local.properties` は flutter が毎回書き直す。

---

## 5. Play Console の実際の状態(CEO 提示・2026-08-20 時点)

引継ぎ資料は「クローズドテスト中」だったが、**実際は製品版で完全公開済み**だった。

| トラック | バージョン | 状態 |
|---|---|---|
| 製品版 | 6 (1.0.4) | 完全公開・2026-08-11 |
| クローズドテスト Alpha | 4 (1.0.3) | 公開中 |

アップロード済み App Bundle の最大は **6**。よって **versionCode 7 で通る**。

## 6. データが更新で消えるかどうか(実機で検証した)

CEO「これってリリースするたびに消えるの？残るようにしてほしい端末に」

**消えない。** 端末で確かめた:

1. 検証用に `com.toriscollection.app` を入れ、土地を選び・植え・目覚ましを 7:00 にセット
2. `adb install -r` で**更新をかけた**
3. → 画面は「⏰ Set for 07:00」のまま、`dumpsys alarm` の登録も生きていた

理由: 保存先は `SharedPreferences`(`/data/data/com.toriscollection.app/shared_prefs/`)で、
Android は **applicationId と署名鍵が同じ限り**、更新をまたいでこのディレクトリを保持する。
`android:allowBackup` も既定の true のまま。

⚠️ **消えるのは次の場合だけ。ここを守れば残る。**
- **applicationId を変える**(今回 `com.toriscollection.app` に固定した理由でもある)
- **署名鍵を変える**
- ユーザーがアンインストール / 「ストレージを消去」する
- **今回の 6→7 だけは例外。** WebView 版はデータを端末アプリではなく
  Web 側に持っていたので、ネイティブ版には引き継がれない。

## 7. ついでに見つかった目覚ましの穴(v6 も同じ。今回の変更が原因ではない)

上の検証中に分かったこと。**更新では消えないが、次の2つでは消える。**

- **強制終了で登録が落ちる。** `am force-stop` 後、`dumpsys alarm` の生きた登録は
  **0件**(履歴に `Reason=pi_cancelled`)。なのに画面は「Set for 07:00」のまま。
- **再起動でも落ちる。** `RECEIVE_BOOT_COMPLETED` の権限は宣言してあるが、
  **受信する Receiver が無い**(manifest のコメントも「受信は今後」)。
- **一度鳴ったら終わり。** `setExactAndAllowWhileIdle` の単発で、鳴った後に
  翌日を組み直す処理がどこにも無い(`BirdAlarmService` / `BirdAlarmReceiver` とも)。
  `enabled` も true のままなので、画面はセット済みに見え続ける。

**公開中の Capacitor v6 も同じ作り**(`BirdAlarmBridge.java` も単発・Receiver 無し)なので、
v7 を出しても悪化はしない。直すなら別作業:

1. `met`(コーラスに出る鳥)を prefs に保存する — いま保存していないので組み直せない
2. 登録処理を Activity 依存から Context 依存に出す
3. `BOOT_COMPLETED` / `MY_PACKAGE_REPLACED` を受ける Receiver を足す
4. **毎日鳴らすのか単発のままかは CEO 判断**(仕様変更にあたる)

## 8. CEO にやってもらうこと(Play Console)

1. `テストとリリース > アプリの完全性 > アプリの署名` で、アップロード鍵の SHA-256 が
   上の `E2:9D:...` と一致することを確認。
2. **内部テストに v7 を上げて、自分の端末で起動を確認**(審査待ちなし)。
3. `ユーザーを増やす > ストアの掲載情報` で、スクショ6枚と
   `feature_graphic.png` を差し替え。
4. 製品版へ昇格。**完全公開ではなく段階的公開から**(作り直した別物のため)。
5. リリースノートに「進行は引き継がれない／セーブコードで移せる」を明記する
   (原則2「罰しない」)。

## 9. 承認が要ると思っているところ(CEO判断)

- **versionName を 2.0.0 にした。** 1.0.5 が良ければ `pubspec.yaml` を直して作り直せる。
- **既存ユーザーの進行は引き継がれない**(§6 の例外)。案内文が要る。
- **CEO 自身の端末も同じ。** 今入っているのは `com.toriscollection.toris_app`
  (開発用の別パッケージ)。Play 版は別アプリとして並び、庭は空から始まる。
  移すならセーブコードを先に控えること。今回は実機を元のまま戻してある。
- **目覚ましの穴(§7)を v7 に入れるか、v8 に回すか。**
