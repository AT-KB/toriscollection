# Toris Collection

**毎日少しずつ、自分の土地に来る鳥たちを集める静かなコレクションゲーム**

植物を植えて、鳥を呼び、彼らの落とし物を集める。バックグラウンドで生態系が動き続け、ログインのたびに新しい出会いが待っている。生態学に基づいた食物網モデルを、ねこあつめ的なUXで包んだ教育プロダクト。

**公開URL**: https://toriscollection-test202605.streamlit.app/

---

## ターゲットと方針

- **ターゲット**: ライト層、毎日5〜10分だけ触る人。鳥や自然に関心があり、「育てる」より「眺める・偶然に出会う」を楽しみたい人
- **3つの軸**: 癒し / コレクション / 教育(生態学的に正しい知識)
- **マネタイズ想定**: 寄付連動(自然保護団体)
- **クローズドテスト**: 5-7名を予定、Streamlit Community Cloud にデプロイ済み

---

## コア体験

1. **土地(都市)を選ぶ**: 京都・シドニー・シャーロットの3つから1つ
2. **植物を植える**: その土地に合う植物を選んで植える(土地ごとに最大6-8種)
3. **生態系が動く**: アプリを閉じている間にも、不在中ループで生態系が時間進化
4. **鳥を眺める・聴く**: 来た鳥のコーラスを聴く。図鑑で詳細を確認
5. **落とし物を集める**: 鳥はときどき小枝・羽根・羽冠を残していく
6. **シミュ機能**: 「この植物を植えると、この鳥の確率がX%→Y%になる」が見える

---

## 技術スタック

- **言語**: Python 3.14
- **UIフレームワーク**: Streamlit
- **データ永続化**: Google Sheets(`gspread` 経由)
- **グラフ理論**: NetworkX(食物網の構築・解析)
- **音源**: xeno-canto API(鳥の鳴き声、CCライセンス)
- **生態データ補正**: GloBI(Global Biotic Interactions)由来のPageRank中心性
- **ホスティング**: Streamlit Community Cloud(無料枠)
- **CI/CD**: GitHub連携で push 時の自動デプロイ

---

## ファイル構成

```
toriscollection/
└── toris_collection/
    ├── app.py             # Streamlit メインアプリ(約2250行)
    ├── data.py            # シードデータ: BIOMES, PLANTS, INSECTS, BIRDS
    ├── engine.py          # 食物網構築 + 確率モデル + シミュレータ
    ├── absence_loop.py    # 不在中ループ(時間経過に応じて生態系を進化)
    ├── mementos.py        # 落とし物システム
    ├── sheets_client.py   # Google Sheets I/O
    ├── xc_client.py       # xeno-canto APIクライアント
    ├── centrality.py      # GloBI由来のPageRank中心性データ
    ├── requirements.txt   # 依存ライブラリ
    └── credentials.json   # Google Cloudサービスアカウント鍵(.gitignore)
```

ドキュメント類:

```
toriscollection/
├── README.md              # このファイル(プロジェクト概要)
├── PROGRESS.md            # 実装ステータスと計画メモ
├── INTERNAL_SPEC.md       # 内部仕様書(本人向け詳細解説)
├── CHECKLIST.md           # 動作確認チェックリスト
├── STARTGUIDE.md          # テスター向けスタートガイド
├── FEEDBACK_FORM.md       # フィードバックフォーム設計
├── TESTER_ROSTER.md       # テスター名簿テンプレート
└── create_feedback_form.gs # Google Forms 自動生成スクリプト(GAS)
```

---

## データモデル

### バイオーム(土地)

3都市。気候タイプ・緯度経度・最大植物本数を持つ。

```python
BIOMES = {
    "kyoto":     { "name": "京都",     "hemisphere": "north", "max_plants": 8, ... },
    "sydney":    { "name": "シドニー", "hemisphere": "south", "max_plants": 6, ... },
    "charlotte": { "name": "シャーロット", "hemisphere": "north", "max_plants": 6, ... },
}
```

南半球バイオームは月オフセットが6ヶ月反転(5月のシドニー = 11月相当の気温)。

### 種数(現状)

| 土地 | 植物 | 昆虫(関連) | 鳥 |
|---|---|---|---|
| 京都 | 13 | 9 | 14 |
| シドニー | 11 | 6 | 10 |
| シャーロット | 11 | 8 | 11 |
| 合計 | 35 | 23 | 35 |

### 食物網モデル

- ノード: 植物 / 昆虫 / 鳥
- エッジ: 「食う - 食われる」の関係(植物→昆虫、植物→鳥、昆虫→鳥)
- 鳥の出現確率 = `気温適合度 × バイオーム補正 × 食物係数 × レア度係数 × 0.5`
- レア度係数は GloBI 由来の PageRank 中心性で補正(中心的な種ほど来やすい)

### 不在中ループ

ログインごとに、前回アクセスから現在までの経過時間に応じて、生態系を複数サイクル進める:

| 経過時間 | サイクル数 |
|---|---|
| 5分未満 | 0 |
| 5-30分 | 1 |
| 30分-2時間 | 2 |
| 2-6時間 | 3 |
| 6-12時間 | 4 |
| 12-24時間 | 5 |
| 24時間以上 | 6(上限) |

各サイクルで滞在中の鳥について退去判定、次に新規到着判定(滞在最大4羽、1サイクル新規最大1羽)。

退去率: `0.15 - 0.13 × 出現確率`(確率0.3の鳥なら退去率0.11)

### 落とし物システム

3カテゴリ(全鳥固有・羽冠は限定鳥のみ):

| カテゴリ | 確率 | 内容 |
|---|---|---|
| 🌿 小枝 | 10% | その鳥が止まっていた小枝(全鳥) |
| 🪶 羽根 | 5% | その鳥の羽根(全鳥) |
| ✨ 羽冠 | 1.5% | その鳥の冠羽(派手な4種+レア5種のみ) |

合計約16.5%、訪問7回に1回くらい何か落とす。
総コレクション数: 35 + 35 + 9 = **79種**

---

## Streamlit UI構成

7タブ構成:

1. **🏞️ 今の様子**: フィールドのSVG描画、不在中の出来事サマリ、ハーモニー再生
2. **🌱 植える**: 植物の選択(本数制限・個別撤去対応)
3. **🧪 シミュ**: 鳥×植物の確率変化シミュレーター(プルダウン選択型)
4. **📖 図鑑**: 全鳥の詳細(地域別/レア度順)、発見地、Google検索リンク
5. **🎁 落とし物**: コレクション画面(カテゴリ別/鳥別ビュー切替)
6. **🕸️ ネットワーク**: 食物網の可視化(力学レイアウト + ホバーハイライト)
7. **❓ 使い方**: 仕様書として常設

サイドバー:
- 現在のテスター情報
- バイオーム表示と気温・降水量
- コレクション状況メトリクス
- 開発テスト用:
  - 時間スキップ機能(1〜48時間後をシミュレート)
  - **データリセット機能**(2段階確認、テスター個別)

---

## Google Sheets スキーマ

スプレッドシートID: `18qZcHLNjR_DnXr3vaCaCHD3m2JsQPTaQcW2DALm8WM4`

- `testers`: テスターIDのリスト
- `field_state`: 各テスターの現在のバイオーム・滞在中の鳥・最終アクセス時刻
- `plantings`: 植えた植物の履歴(plant_id, planted_at, status)
- `bird_visits`: 鳥の訪問記録(滞在中・不在中)、なぜ来たかの理由
- `collection`: 図鑑(各鳥の初回観測・最終観測・累計訪問回数)
- `mementos`: 落とし物の獲得履歴
- `bird_notes`: 図鑑メモ(UI削除済み、互換データのみ保持)
- `access_logs`: 画面遷移と操作の行動ログ

サービスアカウント: `toris-922@torris.iam.gserviceaccount.com`

---

## 起動方法(ローカル)

```bash
# Python 3.14、Windows + PowerShell の場合
cd toris_collection
py -m pip install -r requirements.txt

# credentials.json をプロジェクト直下に配置(Google Cloud のサービスアカウント鍵)

# 起動
py -m streamlit run app.py
# → http://localhost:8501
```

---

## デプロイ(Streamlit Community Cloud)

第一に、GitHub にリポジトリを push(.gitignore で credentials.json は除外)。

第二に、https://share.streamlit.io/ にログインし「New app」。

第三に、リポジトリ・ブランチ・main file path(`toris_collection/app.py`)を指定。

第四に、Advanced settings → Secrets に TOML 形式で認証情報を貼り付け:

```toml
[gcp_service_account]
type = "service_account"
project_id = "torris"
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
client_email = "toris-922@torris.iam.gserviceaccount.com"
...
```

第五に、Deploy を押す。2-3分でビルド完了。

push のたびに自動で再デプロイされる。

---

## パフォーマンス対策

第一階層: `@st.cache_data` メモリキャッシュ(セッション越し共有)
- `_cached_arrival_probability`: 確率計算
- `_cached_network_layout`: ネットワーク図のレイアウト(サブグラフ抽出で約50%軽量化)
- `_cached_audio_bytes`: xeno-canto音源bytes

第二階層: xeno-canto のローカルファイルキャッシュ(`.xeno_canto_cache/`)

第三階層: Google Sheets(セッション開始時に1回だけロード)

---

## 開発スタンス

- **小さく試して使用感を聞くを繰り返す**
- **シンプルさ優先**(機能追加より重複削減)
- **GloBIデータでやる**(外部設定は最小限)
- **ねこあつめ風はUI/UXのみ**、コア体験は生態学ベース
- **インタラクションを通じて気づかせる教育**(読ませる教育ではない)

---

## クローズドテスト準備物

すべて完成済み。`STARTGUIDE.md`、`CHECKLIST.md`、`FEEDBACK_FORM.md`、`TESTER_ROSTER.md`、`create_feedback_form.gs` を参照。

第1週: 自分で動作確認 + 親しい1〜2名に試してもらう。

第2週: 残り5名にロールアウト、1〜2週間。

第3週: フィードバック収集 + 反映。

---

## ライセンス・データ出典

- 鳥の鳴き声: [xeno-canto](https://xeno-canto.org/)(CC BY-NC-SA)
- 種間相互作用データ: [Global Biotic Interactions (GloBI)](https://globalbioticinteractions.org/)(CC0)
- シードデータの食物関係: 生態学文献(Sony CSL「日本の里山生態系」など)とGloBI観察記録の手作業ハイブリッド

---

## 主な設計判断の履歴

- **24時間ペナルティ撤去**: 複雑化に対するリターン小、本数制限で十分
- **不適合フラグ廃止**: 確率0%として自然表示
- **落とし物カテゴリ削減(5→3)**: 種子・木の実を廃止、コレクション体験の均質化
- **GloBIタブ・記録タブ削除**: 重複情報の排除
- **バイオーム名簡略化**: 「京都(日本・温帯モンスーン)」→「京都」
- **シミュレーター独立タブ化**: 植える画面に押し込まずタブ分離(複雑度低減)
- **ネットワーク図の軽量化**: 食物経路がない鳥を非表示にしてノード数を約50%削減
