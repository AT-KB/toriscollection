# Google Play の掲載素材(2026-08-20 更新 / 2026-10-15 追記)

> 🔴 **`02_guide.png` は Play に掲載中だが、もう実物と違う。配信前に差し替えが必須。**
> 詳細と撮り直しの手順は **§「02_guide.png の撮り直し指示書」**(この文書の末尾)。
> 他の5枚(`01_` `03_` `04_` `05_` `06_`)とフィーチャーグラフィック・アイコンは
> **1枚ずつ開いて確認済み・差し替え不要**(2026-10-15 SNS部)。

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
| 02_guide | 図鑑 | American Goldfinch の図版と、好きなもの・**なぜ来たか** 🔴 **この欄は 2026-09-22 に製品から削除された。掲載中の画像は実物と違う**(末尾の指示書) |
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

---

# 🔴 `02_guide.png` の撮り直し指示書(2026-10-15・SNS部 → PJ管理部長)

## 1. なぜ撮り直すのか

CEO 判断で **2026-09-22、「なぜ来たか」を製品から完全に削除**した(commit `885a6ee`)。
`toris_app/lib/garden/guide_page.dart`(429行、2026-10-15 に全文を読んだ)に
`_whyItCame()` もその呼び出しも**無い**。図鑑に **WHY IT CAME の欄はもう出ない。**

ところが **Play に掲載中の `02_guide.png` には、それが大きく映っている。**
画像を開いて実測した(1080x2160):

- **y≈1320〜1568**(罫線から罫線まで **248px**)が `WHY IT CAME` の見出しと
  `🌱 American Goldfinch came. It seems to have stopped by, drawn to Flowering Dogwood.` の2行。
- **画面の高さの約11.5%**。図鑑カードの中では下から2番目のブロックで、**完全に読める大きさ**。

**存在しない機能を、ストアの画像で見せている。** 交渉不能の原則4
(生態に誠実 = 映っていないものを宣伝で言わない)に正面から触れる。
2026-08-21 の `A radio made only of birds you've met` と**同じ種類の事故**。

**次に AAB を配信する前に、必ず差し替えること。**
(アイコンと同じく、**スクショは Console だけで差し替えられる**。アプリ更新は要らない。)

## 2. 何を撮るか — 差し替え後の `02_guide` の中身

図鑑の1ページから **WHY IT CAME が抜けただけ**で、他は変わっていない。
いま版面にあるものは、上から順に(`guide_page.dart` の `_Entry.build` のとおり):

| 順 | 要素 | 実装 |
|---|---|---|
| 1 | 図版(**近くで会った種は詳細画**) | `_plate(observed)` `:255-287` |
| 2 | 英名 / 学名(斜体)/ ★ / `🌱 N days together` | `_heading` `:221-249` / `_badge` `:290-295` |
| 3 | 罫線 | `_Rule` `:299-306` |
| 4 | **LIKES** | `:201` |
| 5 | **HOME** | `:202` |
| 6 | **FEARS**(属レベルなら `(from records of close relatives)` が付く) | `:203` / `:149-151` |
| 7 | **`🖼️ See a real photo`** / **`📖 Wikipedia (EN)`** の2チップ | `_OutLinks` `:366-408` |
| 8 | 罫線 → 説明文(`description_en`) | `:205-210` |

**この 1〜8 が1枚に収まった状態**を撮る。

## 3. どの種を開くか

- **🪶 が付いている種**(= 近くで会った種)を開く。🐦 だと図版が小さなアイコンのままで、
  **「会うと絵が育つ」という一番の売りが映らない**(`_plate` の `observed && detail != null`)。
- **LIKES / HOME / FEARS が3行とも埋まる種**を選ぶ。`_Row` は中身が空だと
  **行ごと消える**(`:318` `if (items.isEmpty) return const SizedBox.shrink();`)。
  - 🔴 **いま掲載中の American Goldfinch は FEARS が空**(掲載画像でも LIKES と HOME しか無い)。
    WHY IT CAME が抜けると版面がさらに寂しくなるので、**別の種にする**。
  - **推奨: Northern Cardinal**(Likes 4件 / Home: Charlotte / Fears: Snakes・Crows and jays・Hawks。
    `bird_profile.py` を実行した値。`2026-08-25_バッチ4…` §2 で確認済み)。
  - 次点: **Blue Jay**(Likes 5件 / Home: Charlotte / Fears: Hawks・Snakes。
    `landing/media/s_profile.jpg` に実機の実物が映っている)。
- CEO の本番データに 🪶 の Northern Cardinal / Blue Jay が無ければ、
  **3行とも埋まる 🪶 の種なら何でもよい**。開く前に畳んだまま一覧を見て選ぶ。

## 4. どこまでスクロールするか

1. Guide タブを開く。並びは **By region**(掲載中の画像と同じ。替えない)。
2. 目的の種の行を**タップして開く**。
3. **カード(`kPage` の白い枠)の上辺が、`By region / By rarity` のボタンの下に来る**ところまでスクロール。
4. **カードの下辺(説明文の最終行の下の余白)が、下のタブバーより上に収まる**ことを確認。
   - **WHY IT CAME が消えたぶん、カードは約250px短くなっている。** 以前より楽に1枚に収まるはず。
   - カードが1画面に入りきらない場合は、**説明文を切るより、Likes が2行に折り返さない種を選び直す**。
5. 下に次の行(`❓ ???` など)が少し覗くのは**そのままでよい**(掲載中の画像も同じ)。
   ただし **カードそのものは絶対に切らない**。

## 5. どのビルドで撮るか

**第一希望: release ビルド**(他の5枚と完全に揃うので、これが本筋)

    flutter build apk --release
    adb install -r build/app/outputs/flutter-apk/app-release.apk

- 切る量は **上 100px / 下 140px** → **1080x2160**。他の5枚と同じ。
- ⚠️ OneDrive 配下だと `build/.cxx` のロックで落ちる。消してやり直す(この文書の上の方)。
- ⚠️ ステータスバーは demo mode で整える(時刻 9:00・電池100・通知なし)。**撮り終わったら戻す。**

**第二希望: `.dev` ビルド**(release が入らないとき)

`HANDOFF_00_最初に読む.md` §3 のとおり、**実機で起動できるのは `.dev` だけ**という状態が
2026-08-25 時点で続いている(`com.toriscollection.toris_app` は起動できるアクティビティが無く、
Play の `com.toriscollection.app` は端末に入っていない)。

- `.dev` には **DEBUG の赤帯**が出る。**1080幅なら上端 150px を切れば消える**
  (720x1600 の録画なら 100px。release 用の `STATUS = 64` では足りない)。
- 切る量は **上 150px / 下 140px** → **1080x2110**。
  - ⚠️ 下を 90px しか切らないと **1080x2160 ちょうどに揃うが、システムのナビゲーションバー
    (y=2274 から)が 36px 残って映る。** 揃えるために下を削らないこと。
  - 1080x2110 は縦横比 1:1.95 で **Play の上限 1:2 の内側**。24bit PNG・320〜3840px も満たす。
    **他の5枚と高さが 50px 違うだけ**で、審査は通る。
- ⚠️ `.dev` は**別データ**なので、CEO の庭・目覚まし・図鑑には触れない。代わりに
  **図鑑がほぼ `???`**(`2026-08-25_実機素材…` §4)。先に **儀式(Listen closely)で
  1種と近くで出会ってから**でないと 🪶 の行が作れない。
- ⚠️ `.dev` で撮った場合、見出しが `Guide 1/37` のように**少ない数**になる。
  掲載中は `Guide 6/37`。**数を偽らない**(原則4)。少なく見えるのが嫌なら release で撮る。

## 6. 出す前のチェックリスト

- [ ] 画像のどこにも **`WHY IT CAME` の文字が無い**
- [ ] どこにも **DEBUG の赤帯**が無い(右上の角に赤い三角が残っていないか、拡大して見る)
- [ ] 下端に**システムのナビゲーションバー**が映っていない
- [ ] 図版が**詳細画**になっている(小さなアイコンではない)
- [ ] **LIKES / HOME / FEARS** の3行が出ている
- [ ] **`🖼️ See a real photo`** と **`📖 Wikipedia (EN)`** の2チップが出ている
- [ ] 説明文が最後まで読める
- [ ] 24bit PNG / 幅1080 / 縦横比が 1:2 の内側
- [ ] ステータスバーの demo mode を**戻した**

## 7. 他の5枚について(2026-10-15 確認済み)

**1枚ずつ開いて目で見た。** `WHY IT CAME` が映っているのは `02_guide.png` だけ。

| ファイル | 映っているもの | 判定 |
|---|---|---|
| 01_garden | 庭・餌台・リス・鷹・Cedar Waxwing / Red-bellied Woodpecker・`Listen closely`・`Your land`・`Plant 4/4` | ✅ そのまま |
| 03_radio | `Garden radio`・House Finch / American Robin / Cedar Waxwing・`Berry and nectar lovers today`・環境音7タイル・音量・`Sleep 15/30/60 min` | ✅ そのまま |
| 04_wake | `Wake with the birds`・`7:00 AM`・`First to sing`・`Two more join as it grows, drawn from the 5 birds you have met up close.` | ✅ そのまま |
| 05_network | 食物網の図(Plant / Insect / Bird の凡例つき) | ✅ そのまま。**`NetworkPage` は削除の影響を受けていない** |
| 06_away | `🌙 While you were away: Red-bellied Woodpecker stopped by once` のダイアログ | ✅ そのまま。文言は `toris_core/lib/src/stories.dart:84,103` といまも一致 |
| feature_graphic / app_icon_512 | — | ✅ そのまま |

**プログラムでも裏を取った**: 6枚とも上端12%に DEBUG の赤帯の画素は0件
(release ビルドで撮ってあるため)。

## 8. ⚠️ ついでに見つかった別件 — **LP の実機スクショに DEBUG の赤帯が残っている**

ストアの素材を1枚ずつ確かめるときに `landing/media/` も開いた。
**`s_plant` / `s_profile` / `s_radio` / `s_bird` / `s_garden` / `s_network` の6枚**の右上に、
`.dev` ビルドの **DEBUG の赤帯の角**が残っている。**うち3枚(`s_plant` / `s_profile` /
`s_radio`)は、いま torriscollection.com に出ている。**

ストアの6枚は **release ビルドで撮ってあるので、こちらは無事**。
直し方と影響は `marketing/phase-1/SNS部/2026-08-25_バッチ4_見せ方のバリエーション_7本.md` §7.7 D。

