# Toris Collection 内部仕様書

開発者本人向けの、コードと挙動の完全な解説。
他のAIに引き継ぐ時、または自分が後で見直す時の参照用。

最終更新: 2026-05-09

---

## 目次

1. プロダクトの全体像
2. ファイル構成と役割
3. データモデル(完全版)
4. 確率モデルの数式
5. 不在中ループの仕組み
6. 落とし物システム
7. UI構成とフロー
8. Google Sheets スキーマ
9. キャッシュとパフォーマンス
10. 既知の問題と回避策
11. 拡張ポイント

---

## 1. プロダクトの全体像

### 一言で

「植物を植えると、生態学的に正しい食物網に基づいて鳥が来訪する、放置型コレクションゲーム」

### 3つの軸

第一に、**癒し**。ねこあつめ的なUX、鳥の鳴き声、SVGの優しいビジュアル。

第二に、**コレクション**。35鳥種・79落とし物の収集。レア度差。

第三に、**教育**。生態学的に正しい食物網。GloBI由来の補正。「呼ぶには」で逆算的に学ぶ。

### コア体験のループ

```
土地を選ぶ → 植物を植える → アプリを閉じる
  ↓
不在中ループで生態系が時間進化(5分〜24時間スパン)
  ↓
ログイン → 新しい鳥が来ているかも → 図鑑が増える、落とし物が見つかる
  ↓
別の植物を植えてみる → 食物網がさらに複雑化 → ループ
```

---

## 2. ファイル構成と役割

```
toris_collection/
├── app.py             # Streamlit メインアプリ(2200行)
├── data.py            # シードデータ
├── engine.py          # 食物網エンジン
├── absence_loop.py    # 不在中ループ
├── mementos.py        # 落とし物システム
├── sheets_client.py   # Google Sheets I/O
├── xc_client.py       # xeno-canto API
├── centrality.py      # GloBI由来 PageRank
├── credentials.json   # Google Cloud認証(gitignore)
└── requirements.txt   # 依存ライブラリ
```

### app.py - メインアプリ

Streamlitの全UI。タブ7つで構成:

```python
tab_home, tab_plant, tab_sim, tab_birds, tab_mementos, tab_network, tab_help
```

セッション状態(`st.session_state`)で管理しているもの:
- `current_tester_id`: ログイン中のID
- `biome`: 現在のバイオーム
- `month`: 現在の月(1-12)
- `planted`: 植えた植物のリスト
- `residents`: 滞在中の鳥のセット
- `discovered`: 図鑑登録済みの鳥セット
- `mementos`, `mementos_set`: 落とし物のリスト・セット
- `absence_events`: 不在中の出来事
- `bird_visited_biomes`: 鳥がどのバイオームで観測されたか
- `rng`: 確率計算用の乱数生成器

### data.py - シードデータ

すべて静的なPython辞書:

```python
BIOMES   = {3つの土地}     # 名前、座標、温度、最大植物本数等
PLANTS   = {35種の植物}    # 学名、英名、適温、適合バイオーム
INSECTS  = {23種の昆虫}    # 学名、英名、適温、食草
BIRDS    = {35種の鳥}      # 学名、英名、色、適温、レア度、食性
SEASON_TEMP_OFFSET = {月→気温オフセット}
BIOME_MIGRATION = {旧ID → 新ID}  # 旧データの自動変換
```

### engine.py - 食物網エンジン

主要関数:

- `current_temperature(biome, month)`: その土地・月の気温を計算。南半球は6ヶ月反転
- `temperature_fit(temp, range)`: 適温範囲内なら1.0、外れるほど0に近づく
- `build_network(planted, biome, month)`: NetworkXのDiGraphを構築
- `calculate_arrival_probability(bird, G, biome, month)`: 鳥の出現確率を算出
- `run_turn(...)`: 1サイクル分の進化(到着・退去判定)
- `simulate_with_added_plant(...)`: 候補植物を追加した場合の確率を計算
- `suggest_for_bird(...)`: 鳥を呼ぶための植物候補を逆算
- `network_stats(G)`: ノード数・エッジ数・ハブ種を計算
- `force_directed_layout(G, ...)`: 同心円レイアウト

### absence_loop.py - 不在中ループ

主要関数:

- `estimate_tick_count(elapsed_minutes)`: 経過時間からサイクル数を算出
- `evolve_state(planted, biome, month, last_at, now, residents, rng)`: 不在中の進化を実行
- `build_reason_text(event)`: 「○○が△△を食べに来た」のような説明文を生成
- `parse_iso(s)`: ISO形式の文字列からdatetimeへ

### mementos.py - 落とし物システム

主要関数と定数:

```python
PLUME_BIRDS = {限定9種の鳥}  # 羽冠を持つ鳥
DROP_PROBABILITIES = {twig: 0.10, feather: 0.05, plume: 0.015}
CATEGORIES = ["twig", "feather", "plume"]

roll_drop(bird_id, ..., rng) -> memento_id or None
memento_display(id, BIRDS, PLANTS, BIOMES) -> (icon, name, desc, color)
all_possible_mementos(BIRDS, PLANTS) -> list of dict
```

### sheets_client.py - Google Sheets I/O

主要関数:

- 読み込み: `load_active_plantings`, `load_mementos`, `load_collection`, `load_field_state`, `load_bird_notes`, `load_visited_biomes`
- 書き込み: `add_planting`, `remove_planting`, `add_visit`, `add_memento`, `upsert_collection`, `save_field_state`, `save_bird_note`
- ログ: `log_access`
- 全削除(テスト用): `reset_tester_data`

認証はローカルとクラウド両対応:
```python
if os.path.exists("credentials.json"):
    # ローカル: ファイルから
else:
    # クラウド: st.secrets["gcp_service_account"]から
```

### xc_client.py - xeno-canto API

鳥の鳴き声を取得。CC ライセンスでBGMとして使用可能。

- `get_audio_url(scientific_name)`: 学名で検索して最良の音源URLを取得
- `download_audio(scientific_name)`: ダウンロード&ローカルキャッシュ
- `get_citation(scientific_name)`: クレジット情報

### centrality.py - GloBI由来 PageRank

GloBIのGlobal Biotic Interactions公開データから計算した、各鳥の食物網中心性。
これを確率計算で「rarity_factor の補正」として使うことで、生態学的に重要な鳥(中心的な種)が来やすくなる。

事前計算なので、実行時はファイルから読むだけ。

---

## 3. データモデル(完全版)

### BIOMES の構造

```python
{
    "kyoto": {
        "name": "京都",            # 表示名
        "lat": 35.0, "lon": 135.8, # 緯度経度
        "temp_mean": 14,           # 年平均気温
        "precip_mean": 1500,       # 年降水量
        "hemisphere": "north",     # 北半球
        "max_plants": 8,           # 植物本数上限
        "description": "...",      # 説明
    },
    "sydney": { ..., "hemisphere": "south", "max_plants": 6 },
    "charlotte": { ..., "hemisphere": "north", "max_plants": 6 },
}
```

### PLANTS の構造

```python
{
    "sakura": {
        "name": "サクラ",
        "scientific": "Prunus serrulata",
        "english": "Japanese Cherry",
        "icon": "🌸",
        "temp_fit": (5, 22),       # 適温範囲(min, max)
        "biome": ["kyoto"],         # 適合バイオーム
    },
    ...
}
```

### INSECTS の構造

```python
{
    "ao_imo_mushi": {
        "name": "アオムシ(モンシロチョウ幼虫)",
        "scientific": "Pieris rapae larva",
        "english": "Cabbage white larva",
        "temp_fit": (10, 28),
        "eats_plants": ["rice", ...],
    },
    ...
}
```

### BIRDS の構造

```python
{
    "shijukara": {
        "name": "シジュウカラ",
        "scientific": "Parus minor",
        "english": "Japanese Tit",
        "color": "#5a8a5a",         # ノードの色
        "eats_plants": ["sakura", "kunugi"],
        "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 28),
        "biome_pref": ["kyoto"],
        "rarity": 0.15,             # 0=普通、1=超レア
        "description": "...",
    },
    ...
}
```

### 種数の現状

| 土地 | 植物 | 昆虫(関連) | 鳥 |
|---|---|---|---|
| 京都 | 13 | 9 | 14 |
| シドニー | 11 | 6 | 10 |
| シャーロット | 11 | 8 | 11 |
| **合計** | **35** | **23** | **35** |

---

## 4. 確率モデルの数式

### 鳥の出現確率

`calculate_arrival_probability(bird, G, biome, month)` の計算式:

```
probability = 0.5 × t_fit × biome_bonus × food_factor × rarity_factor
```

各係数:

**t_fit(気温適合度)**: 
- bird.temp_fit (min, max) と現在気温から計算
- min〜max内なら 1.0、外れるほど0に近づく
- 範囲外で 0.05 未満になると鳥が来ない

**biome_bonus(バイオーム適合)**:
- biome_id が bird.biome_pref に含まれる: 1.0
- 含まれない: 0.15(生態学的に来づらい外来環境扱い)

**food_factor(食物網スコア)**:
```
food_score = sum(その鳥に流入するエッジの重み)
food_factor = 1.0 - 0.6^food_score
```
飽和関数なので、食物が増えるほど効果は逓減。

**rarity_factor(レア度係数)**:
```
基本: rarity_factor = (1.0 - bird.rarity × 0.85) × 0.9
GloBI補正: PageRank中心性が高い鳥はrarity_factorをブースト
```

### 気温計算

`current_temperature(biome, month)`:

```python
temp = biomes[biome].temp_mean + SEASON_TEMP_OFFSET[adjusted_month]

# 南半球は6ヶ月反転
if biomes[biome].hemisphere == "south":
    adjusted_month = ((month + 6 - 1) % 12) + 1
```

### 退去率

```
leave_rate = 0.15 - 0.13 × probability
```

確率0.3の鳥なら退去率0.11(11%/サイクル)。
6サイクル後の残存率は (1-0.11)^6 ≈ 49%。

---

## 5. 不在中ループの仕組み

### サイクル数の計算

`estimate_tick_count(elapsed_minutes)`:

| 経過時間 | サイクル数 |
|---|---|
| 5分未満 | 0 |
| 5分〜30分 | 1 |
| 30分〜2時間 | 2 |
| 2〜6時間 | 3 |
| 6〜12時間 | 4 |
| 12〜24時間 | 5 |
| 24時間以上 | 6 (上限) |

### 各サイクルの処理

```
for サイクル in 1..N:
    1. 滞在中の各鳥について退去判定 → 出ていく
    2. 滞在数が4羽未満なら、新規到着判定:
       - 全鳥について確率を計算
       - 重み付きランダム抽選で1羽だけ選ぶ
       - 滞在リストに追加
    3. 訪問した鳥について落とし物判定:
       - twig(10%) → feather(5%) → plume(1.5%) の順に判定
       - 最初に当たったものを記録
```

### イベント記録

各サイクルの結果は `events` リストに蓄積:

```python
{
    "bird_id": "shijukara",
    "type": "arrival" / "departure",
    "arrived_at": datetime,
    "reason_text": "サクラを食べに来た",
    "related_plant_id": "sakura",
    "memento_id": "twig:shijukara" or None,
}
```

---

## 6. 落とし物システム

### 3カテゴリ + 限定アイテム

| カテゴリ | 確率 | 対象 | コレクション数 |
|---|---|---|---|
| 🌿 小枝 (twig) | 10% | 全鳥 | 35 |
| 🪶 羽根 (feather) | 5% | 全鳥 | 35 |
| ✨ 羽冠 (plume) | 1.5% | PLUME_BIRDS のみ | 9 |

PLUME_BIRDS:
- 派手な冠羽: キバタン、ショウジョウコウカンチョウ、エボシクマゲラ、アオカケス
- レアな鳥: キビタキ、カワセミ、イカル、ルビーノドハチドリ、キバラオーストラリアコマドリ

合計コレクション数: 79

### memento_id の形式

新形式: `kind:bird_id`(例: `feather:shijukara`)

旧形式互換:
- `seed:bird_id` → 種子(廃止カテゴリ・「旧」表示)
- `nut:bird_id` → 木の実(廃止カテゴリ・「旧」表示)
- `twig_kyoto`, `nut_charlotte` → バイオーム別(古いデータ・「旧」表示)

`load_mementos()` がこれらを正規化して読み込む。

---

## 7. UI構成とフロー

### サイドバー

- ヘッダ: ログイン中のテスターID
- バイオーム表示(月、気温、降水量)
- コレクション状況メトリクス(図鑑/滞在中/植えた植物/落とし物)
- 「ここを離れる」(気分転換)
- ログアウト
- 開発テスト用:
  - 時間スキップ(1〜48時間後をシミュ)
  - **データリセット**(2段階確認)

### メインエリア(7タブ)

#### Home(今の様子)

- 不在中バナー(あれば)
- フィールドSVG: 時間帯対応の空、植物アイコン、鳥アイコン
- 土地選択(2ステップ確認)
- 「今、ここにいる鳥たち」リスト + ハーモニー再生

#### Plant(植える)

- 「土地の収容力 N/M」バナー
- 植物カード(3列グリッド): クリックで植える
- 植えた植物リスト: 個別撤去 + 全部抜く

#### Simulator(シミュ)

- 土地・鳥・植物の3プルダウン
- 結果カード: 「現状X% → 植えた後Y%」
- 計算の内訳(折り畳み)

#### Birds(図鑑)

- 全種/発見済みのみ/未発見のみフィルタ
- 地域別/レア度順切替
- 地域別の場合、上部に発見状況サマリ
- 鳥詳細(expander):
  - 学名・英名・色付き表示
  - Google検索 / Wikipediaリンク
  - 鳴き声再生
  - 説明文・適温・好む環境
  - これまで出会った土地(自動)
  - 「呼ぶには」セクション(候補植物 + 確率変化)

#### Mementos(落とし物)

- 上部に3カテゴリのサマリカード
- 落とし物別ビュー: カテゴリごとに全候補のグリッド
- 鳥別ビュー: 発見済みの鳥ごとに3スロット表示

#### Network(ネットワーク)

- 4メトリクス(植物・昆虫・来うる鳥・相互作用)
- ハブ種ヒント
- 力学レイアウトのSVG
- ホバーでハイライト
- **食物経路がある種のみ表示**(軽量化)

#### Help(使い方)

- アプリの全体像と操作方法

---

## 8. Google Sheets スキーマ

スプレッドシートID: `18qZcHLNjR_DnXr3vaCaCHD3m2JsQPTaQcW2DALm8WM4`
サービスアカウント: `toris-922@torris.iam.gserviceaccount.com`

### 8つのシート

#### testers
| tester_id | name | created_at |

#### field_state
| tester_id | biome | temperature | season | residents (CSV) | last_access_at |

#### plantings
| id | tester_id | plant_id | planted_at | status | removed_at |

`status` は `active` / `removed`(物理削除しない、論理削除のみ)

#### bird_visits
| id | tester_id | bird_id | visit_type | reason_text | related_plant_id | related_insect_id | arrived_at |

`visit_type` は `live`(滞在中)/ `absence`(不在中ループ)

#### collection
| tester_id | bird_id | first_seen_at | last_seen_at | total_visits |

#### mementos
| memento_id | tester_id | kind | target_id | biome | found_at | via_bird_id | notes |

#### bird_notes
| tester_id | bird_id | location | note_text | first_saved_at | updated_at |

(現状UI削除済み・データのみ保持)

#### access_logs
| timestamp | tester_id | tab | action | detail |

### マイグレーション

旧バイオームID(`satoyama` 等)は `BIOME_MIGRATION` でロード時に変換される。

---

## 9. キャッシュとパフォーマンス

### キャッシュ階層

第一階層: **`@st.cache_data` メモリキャッシュ**(セッション越し共有)
- `_cached_arrival_probability`: 確率計算
- `_cached_network_layout`: ネットワーク図のレイアウト
- `_cached_audio_bytes`: xeno-canto音源bytes

第二階層: **xeno-canto のローカルファイルキャッシュ**(`.xeno_canto_cache/`)
- ローカルでは永続化、Streamlit Cloudでは再起動でリセット

第三階層: **Google Sheets**(常に外部I/O)
- セッション開始時に1回だけロード
- 書き込みは即時(write-through)

### パフォーマンス改善の効いた施策

1. ネットワーク図のサブグラフ化(食物経路がない鳥を除外、約50%のノード削減)
2. 力学レイアウトの結果キャッシュ
3. 音源bytesのメモリキャッシュ

### 改善余地

1. Sheetsへの初回ロードを並列化
2. xeno-canto音源の事前ダウンロード(全鳥分のキャッシュビルド)
3. `app.py` のファイル分割

---

## 10. 既知の問題と回避策

### 問題1: Streamlit Cloud のスリープ

24時間アクセスがないと休眠。次回アクセス時に30秒〜1分の起動時間。

**回避策**: スタートガイドに記載済み。実用上は問題ないはず。

### 問題2: `st.components.v1.html` の警告

来月削除予告。現状はまだ動く。

**回避策**: 来月直前に `st.html` への置換を実施。

### 問題3: 旧データの混在

過去テストの seed:xxx, nut:xxx などのレコードがmementosシートに残っている。

**回避策**: `load_mementos` が自動正規化、UIには3カテゴリのみ表示。
完全クリアは「データリセットボタン」で。

### 問題4: 鳥の鳴き声が見つからないことがある

xeno-canto に音源がない鳥種(ヤマガラなど一部の希少種)。

**回避策**: 「録音が見つかりませんでした」と表示してフォールバック。アプリは落ちない。

---

## 11. 拡張ポイント

### 鳥・植物の追加

`data.py` の `BIRDS` / `PLANTS` / `INSECTS` に項目を追加するだけ。

注意点:
- `eats_plants`, `eats_insects` で参照IDが正しいか確認
- `temp_fit` を実在の生態に基づいて設定
- `biome_pref` を正しく
- レア度は 0(普通)〜1(超レア)

### バイオームの追加

第一に、`data.py` の `BIOMES` に追加(温度・座標・最大植物本数)。

第二に、その地域の植物・昆虫・鳥を追加し、`biome` / `biome_pref` に新IDを記載。

第三に、必要に応じて `current_temperature` の半球判定を確認(熱帯なら半球の概念がない)。

第四に、`render_field_view` のSVGデザインを地域固有に調整(ユーカリ林、針葉樹林など)。

### 新しい落とし物カテゴリ

`mementos.py` の `CATEGORIES`、`DROP_PROBABILITIES`、`_CAT_META` を更新。

注意: スプレッドシートの旧データとの互換性も考慮(`memento_display` で旧形式表示)。

### 季節イベント

例: 「桜が咲く週」「紅葉週」「クリスマス」など。
実装案: `data.py` に `SEASON_EVENTS = {month: event_info}` を追加し、ホーム画面のSVGに季節装飾を加える。鳥の確率にイベント補正を加えても面白い。

### ソーシャル要素

「他のテスターのフィールドを覗く」機能。
Sheetsに既に各テスターの状態が保存されているので、別テスターIDの`field_state`をread-onlyで表示するだけで実装可能。プライバシーには注意。

---

## 12. 開発スタンスのメモ

### 一貫している判断

- **シンプルさ優先**: 機能追加より重複削減
- **ねこあつめ風はUI/UXのみ**: コア体験は生態学ベース
- **GloBIデータでやる**: 外部設定は最小限
- **インタラクションを通じて気づかせる教育**: 読ませる教育ではない

### 撤去された機能(歴史的経緯)

- 24時間ペナルティ(植物の効果遅延): 複雑化に対するリターン小
- 不適合フラグ(警告): 確率0%として自然表示
- 種子・木の実カテゴリ: 整理のため削減
- GloBIタブ: 一般ユーザーには過剰
- 記録タブ: ホームの不在中バナーで集約
- メモ機能(図鑑): 自動表示で十分

これらは「足したけど引いた」機能。判断の歴史として記録。

---

## 13. クローズドテスト計画

### 第1週(自分+親しい1〜2名)

- 動作確認チェックリストを実施
- 重大バグがあれば修正
- 親しい1〜2名に試してもらう
- 緊急修正

### 第2週(残り全員)

- 残り5名にロールアウト
- 1〜2週間使ってもらう

### 第3週(フィードバック収集・反映)

- フィードバックフォームで集計
- 改善優先度を決定
- 次のリリースを検討

### 関連ドキュメント

- `README.md`: プロジェクト概要(他AI向け)
- `PROGRESS.md`: 実装ステータスと計画
- `CHECKLIST.md`: 動作確認チェックリスト
- `STARTGUIDE.md`: テスター向けスタートガイド
- `FEEDBACK_FORM.md`: フィードバックフォーム設計
- `TESTER_ROSTER.md`: テスター名簿
- `INTERNAL_SPEC.md`: この文書(内部仕様)
- `create_feedback_form.gs`: GASスクリプト

