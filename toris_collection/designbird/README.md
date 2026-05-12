# designbird フォルダの使い方

このフォルダには、各鳥のドット絵スプライト(PNG画像)が入っています。

---

## 配置場所

```
toriscollection/
└── toris_collection/
    ├── app.py
    ├── data.py
    └── designbird/        ← このフォルダ
        ├── shijukara.png
        ├── mejiro.png
        ├── ...(35羽分)
```

## ファイル名のルール

ファイル名は `data.py` の `BIRDS` の **キー名** と一致させます。

例:
- `shijukara.png` → シジュウカラ
- `mejiro.png` → メジロ
- `northern_cardinal.png` → ショウジョウコウカンチョウ
- `blue_jay.png` → アオカケス

完全一致が条件です(大文字小文字、アンダースコアに注意)。

---

## 仕様

| 項目 | 値 |
|---|---|
| サイズ | **64×64ピクセル** |
| フォーマット | PNG(透過対応) |
| 色数 | 16-32色程度 |
| 背景 | 透過(`#00000000`) |

サイズは厳密に64×64でなくても表示はされますが、統一感のため推奨します。

---

## どこに表示されるか

第一に、**図鑑タブの鳥詳細**: 128×128ピクセルで大きく表示。

第二に、**ホーム画面のフィールドSVG**: 48×48ピクセルで鳥が滞在中の様子として表示。

第三に、**未来の拡張で他の場所**: 落とし物画面、ネットワーク図のホバー時など。

ファイルがない鳥は自動的に Emoji(🐦)にフォールバックします。

---

## 差し替え方法

第一に、新しいPNGを用意(64×64推奨、ファイル名は `{bird_id}.png`)。

第二に、`designbird/` フォルダに同名で上書きアップロード。

第三に、GitHubにpush → Streamlit Cloudが自動再デプロイ → 反映完了。

注意点として、ブラウザのキャッシュが残ることがあるので、テスト時は Ctrl+F5 で強制リロードしてください。

---

## 全鳥のID一覧

### 京都(14種)
- shijukara - シジュウカラ
- mejiro - メジロ
- suzume - スズメ
- hiyodori - ヒヨドリ
- uguisu - ウグイス
- kogera - コゲラ
- yamagara - ヤマガラ
- kibitaki - キビタキ
- tsubame - ツバメ
- kawasemi - カワセミ
- ikaru - イカル
- kawarahiwa - カワラヒワ
- enaga - エナガ
- kakesu - カケス

### シドニー(10種)
- rainbow_lorikeet - ゴシキセイガイインコ
- kookaburra - ワライカワセミ
- australian_magpie - カササギフエガラス
- sulphur_crested_cockatoo - キバタン
- eastern_yellow_robin - キバラオーストラリアコマドリ
- superb_fairywren - ルリオーストラリアムシクイ
- noisy_miner - クロガオミツスイ
- galah - モモイロインコ
- willie_wagtail - オウギビタキ
- satin_bowerbird - アオアズマヤドリ

### シャーロット(11種)
- northern_cardinal - ショウジョウコウカンチョウ
- blue_jay - アオカケス
- eastern_bluebird - ルリツグミ
- american_robin - コマツグミ
- carolina_wren - カロライナミソサザイ
- pileated_woodpecker - エボシクマゲラ
- ruby_throated_hummingbird - ルビーノドハチドリ
- mourning_dove - ナゲキバト
- tufted_titmouse - エボシガラ
- american_goldfinch - オウゴンヒワ
- downy_woodpecker - セジロコゲラ

合計: 35種

---

## 仮スプライトについて

現在配置されている35羽のスプライトは**動作確認用の超簡易版**です。
各鳥の `color` フィールドを反映していますが、品質は GBA ポケモン水準には届きません。

本格的な制作の方針は `SPRITE_DESIGN_GUIDE.md` を参照してください。

---

## トラブルシューティング

### スプライトが表示されない

- ファイル名のスペルを確認(`shijukara.png` で `shujukara` などタイポしていない?)
- 拡張子が `.png` であること(`.PNG` 大文字は環境依存)
- フォルダパスが `toris_collection/designbird/` であること

### Emoji にフォールバックされる

- 該当鳥のスプライトファイルが存在しないか、読み込めなかった場合の正常動作
- ファイル名のIDと `data.py` のキーを照合してください

### ブラウザに反映されない

- Streamlit Cloud の自動再デプロイ(2-3分)を待つ
- ブラウザで Ctrl+F5(強制リロード)
- Streamlit Cloud のキャッシュは `@st.cache_data(ttl=3600)` で1時間。1時間待つか、アプリの「Reboot」を実行
