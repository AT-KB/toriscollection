# Toris Collection — 引き継ぎ仕様書

最終更新: 2026-06-11  
対象読者: 次に開発を引き継ぐ AI・開発者  
前仕様書: `PROJECT_SPEC.md`(2026-05-20)、`PROGRESS.md`(2026-05-26)  
ブランチ: `claude/admiring-gauss-xx5Gq`（→ main へ PR #17 / #18 マージ待ち）

---

## 1. プロダクトの一行サマリー

**「実際に同じ場所で共存している鳥たちが、本物の空間音響で会話する"生きた庭"」**

集めた鳥を眺めるだけでなく、鳥たちが生態的に正しい顔ぶれで集まり、掛け合いで鳴く体験をゴールにする。これが競合（Birdfull 等の収集ゲー、Merlin 等の識別ツール）にはない唯一無二の軸。

### 1-1. 製品の背骨（2026-06-11 決定・交渉不能）

**ラジオがコア。儀式はラジオに出す鳥に「会う」手段。**

```
会う（儀式）→ 出会った鳥がラジオに加わる → ラジオが豊かになる
            → もっと違う顔ぶれを聴きたくなる → また会いに行く
```

この決定が以後のすべての設計判断の上位にある。具体的な含意:

- **ラジオは毎日帰ってくる場所（destination）**。情報設計上いちばん前に置く。
- **儀式は獲得（acquisition）の入口**。「コーラス」「聴く」という言葉はラジオのもの。儀式は「会う」。
- **二重コアの解消**: 儀式とラジオはどちらも鳥の声を鳴らすが、儀式＝出会いの瞬間（一時的・目的志向）、ラジオ＝日々の伴侶（持続的・アンビエント）と役割を分ける。
- **生態学の堀はラジオに奉仕する**。「誰と誰が一緒に鳴くか」はラジオの魔法。だが受動層には共起の正しさは"聞こえない"ので、**ナレーション（なぜこの顔ぶれか）で可視化**して初めて価値になる。
- **明日開く理由はラジオに宿す**。昨日会った鳥が今日ラジオに増えている、という因果フックが retention の本体。
- **種の拡充は背骨が証明されるまで後回し**。コレクションのグラインドは"癒し"軸と喧嘩する。

---

## 2. 2026-06-11 時点の実装状態

### 2-1. タブ構成（9タブ）

```
ラジオ | 庭の様子 | 植える | シミュ | 図鑑 | 落とし物 | あしあと | ネットワーク | 使い方
```

背骨決定（§1-1）に伴う変更:
- **ラジオを最前面（タブ1・コア）に移動**。毎日帰る場所として front door に置く。
- **ホーム → 「庭の様子」に改称**。鳥に「会う」場所（儀式・フィールド・植える導線）。
- **ホームの折りたたみラジオを撤去**（二重コアの解消・聴く体験はラジオに一本化）。
- **儀式完了の知らせを「🎙 ラジオの顔ぶれに加わりました」に変更**（会う→聴くのループを可視化）。
- **あしあと**（訪問カレンダー・旧「足跡」）→ シート修正で正常動作化

### 2-2. 主要ファイル（最新）

| ファイル | 役割 | 変更状況 |
|---|---|---|
| `app.py` | Streamlit UI・9タブ制御 | ラジオタブ追加・ホームにラジオ埋め込み |
| `data.py` | シードデータ（BIOMES/PLANTS/INSECTS/BIRDS 35種） | 変更なし |
| `engine.py` | 食物網エンジン・確率計算・力学レイアウト | 変更なし |
| `ritual.py` | 儀式UI（距離メカニクス・Web Audio・スプライト）| 変更なし |
| `radio.py` | 庭のラジオ（新規、約680行） | 最新 |
| `ecology.py` | 共起ネットワーク計算（新規、約160行） | 最新 |
| `sheets_client.py` | Google Sheets I/O | `_ensure_access_logs_sheet()` 追加 |
| `xc_client.py` | xeno-canto API | 変更なし |
| `freesound_client.py` | Freesound 環境音キャッシュ | 変更なし |
| `observation_log.py` | 近距離観察記録ラッパー | 変更なし |
| `mementos.py` | 落とし物システム | 変更なし |
| `absence_loop.py` | 不在中ループ | 変更なし |
| `centrality.py` | GloBI 由来 PageRank 補正 | 変更なし |
| `globi_client.py` | GloBI API クライアント | 変更なし |
| `build_globi_cache.py` | GloBI キャッシュビルダー（初回のみ手動実行） | 変更なし |

### 2-3. 種数

| バイオーム | 植物 | 昆虫 | 鳥 |
|---|---|---|---|
| 京都 | 13 | 9 | 14 |
| シドニー | 11 | 6 | 10 |
| シャーロット | 11 | 8 | 11 |
| **合計** | **35** | **23** | **35** |

---

## 3. 庭のラジオ（radio.py）— 設計と仕組み

### 3-1. 概要

観察済みの鳥たちが掛け合いで鳴くアンビエントプレイヤー。「捕まえる」仕組みはなく、ただ聴く。

### 3-2. データの起点

ラジオには `observed`（儀式での近距離観察記録）と `discovered`（コレクション済み set）の両方を統合したものを渡す。`discovered` のみの鳥はデフォルト count=1 として扱う。これにより「集めた全鳥がラジオに出られる」。

```python
# app.py での組み立て
_radio_obs = dict(st.session_state.get("observed", {}))
for _bid in st.session_state.get("discovered", set()):
    _radio_obs.setdefault(_bid, {"count": 1, "first": "", "last": ""})
```

### 3-3. 顔ぶれ選択（ecology.py によるネットワーク選択）

**ただのランダムではない。** 共起ネットワーク重み付きで選ぶ。

```
co_occurrence(A, B) = 気候ニッチ重なり(temp_fit) × ギルド係数 × 競争抑制
```

- **気候ニッチ重なり**: `temp_fit` レンジの Jaccard。同じ環境を好む鳥ほど一緒に出やすい（environmental filtering）。
- **ギルド係数**: 同じ採餌ギルド（insectivore / herbivore / omnivore）なら 1.0、違えば 0.45。
- **競争抑制**: 餌の Jaccard > 0.7 なら線形に抑制（競争排除則）。食物が完全に同じ鳥は共存しにくい。

**注意**: 「同じ餌を分け合う = 仲間」は**誤り**（競争排除則、Gause 1934）。修正済み。

`pick_lineup()` は seed 鳥を観察回数で引き、以後「すでに選んだ鳥と共起度が高い鳥を引きやすく」積み上げる。→ カラ類混群やドングリ食グループが自然に揃う。

### 3-4. 選曲の観察回数 → 音響レベル

```python
def _obs_to_depth(count: int) -> str:
    if count >= 6: return "b1"   # 近い・クリア
    if count >= 3: return "b2"   # 中間
    return "b3"                  # 遠い・エコー強め
```

### 3-5. 季節システム

アプリ内時間のみ（現実カレンダーとは独立）。

```python
_APP_EPOCH = date(2025, 3, 1)  # 春の始まり
_WEEKS_PER_SEASON = 1           # 1週間で季節が変わる
```

渡り鳥（キビタキ・ツバメ・ルビーノドハチドリ）は春・夏のみ出現。

### 3-6. 音響エンジン（Web Audio API）

```
hp(highpass 520Hz)
  → filter(lowpass, 深さによりカットオフ変化)
  → ana(AnalyserNode, RMS 計測)
  → gate(Gain, ノイズゲート)
  → agcGain(Gain, AGC)
  → gain(Gain, 深さ固定ゲイン)
  → chGain(Gain, 呼応のフォア/バック切替)
  → pan(PannerNode HRTF / StereoPanner フォールバック)
  → master(DynamicsCompressor)
  → destination
  ↕ wet(Gain) → ConvolverNode(リバーブ IR)
```

**AGC**: `peakRMS` を fast attack / slow decay で追跡。target RMS=0.065、clamp 0.5–3.5、3秒スムージング。  
**呼応（かけあい）**: `activeIdx` が 1 羽のフォアグラウンド（chGain=1.0）。フレーズ終端（12 フレーム無音）を検出し、40% 確率で次の鳥にバトン（共起度の高い鳥ほど選ばれやすい）。  
**環境音**: `freesound_api_key.txt` があれば Freesound から CC0 森の音を取得・キャッシュ、なければシンセ合成ノイズ。  
**HRTF**: `PannerNode` で立体定位。非対応ブラウザは `StereoPanner` にフォールバック。

### 3-7. key_prefix（重複キー対策）

`render_radio()` の `key_prefix` 引数で全ウィジェット・セッションキーを名前空間分離。
現在ラジオは**ラジオタブ（コア・1箇所のみ）**で描画する。

```python
# ラジオタブ(コア)
render_radio(..., key_prefix="radio")
```

> 2026-06-11: 背骨決定（§1-1）に伴い、ホームの折りたたみラジオ（`key_prefix="radio_home"`）は
> 二重コアの名残として撤去。聴く体験はラジオタブに一本化。`key_prefix` 機構自体は将来の
> 再利用に備えて残置。

---

## 4. ecology.py — 共起ネットワーク

```python
guild(bird_id, birds_data) -> "insectivore" | "herbivore" | "omnivore" | "other"
climate_overlap(bird_a, bird_b, birds_data) -> float  # 0..1
diet_jaccard(bird_a, bird_b, birds_data) -> float      # 0..1
co_occurrence(bird_a, bird_b, birds_data) -> float     # 0..1
co_occurrence_matrix(bird_ids, birds_data) -> list[list[float]]
pick_lineup(candidates, birds_data, k, rng, base_weight) -> list[str]
guild_groups(bird_ids, birds_data) -> list[dict]  # {"guild","icon","label","birds"}
```

**このモジュールは UI に一切依存しない純粋計算。** `data.py` の `PLANTS` / `INSECTS` を直接参照する。

---

## 4-2. disturbance.py — 撹乱と遷移（PR #20）

**方針（交渉不能）**: 撹乱は「世界の出来事」。プレイヤーのせいにしない。低頻度。
**損失の次に必ず再生（遷移）を置く** ——倒れた跡地に *違う* 植物が芽吹き、違う鳥が来る＝ラジオに新しい顔ぶれ。罰でなく「庭が移ろう」体験にする（retention にも効く）。

```python
roll_disturbance(rng) -> dict | None          # 嵐/落雷/伐採を低頻度で抽選
apply_disturbance(planted, event, plants, rng) -> list[str]   # 倒れる植物(全滅はしない)
roll_succession(planted, biome, plants, event, rng, exclude) -> str | None  # 跡地に芽吹く別の種
disturbance_story(event, removed_names, sprout_name) -> str   # 移ろいを一文で語る
```

設計上の要点:
- **生息地の質は別の値として持たない**。撹乱は植生（plantings シート）を移ろわせるだけ。木が倒れれば食物網が縮み、`engine.py` の既存 `food_factor`／退去ロジックで**確率・種数が自然に下がる**（種数–面積関係 S=cA^z を余計な係数なしで表現＝モデルに誠実）。
- `roll_succession` は**倒れたばかりの種を `exclude` で除外**（同じ場で生え直すと「移ろい」にならない）。
- 植物の形質 `disturbance_sensitivity`（倒れやすさ）/ `successional_role`（pioneer/late）は **species_plants シートの任意列**。未設定はシードの既定値（感受性0.5・パイオニア候補）。

統合: `absence_loop.evolve_state()` が不在の各ティックで撹乱を回し、`disturbances` と `planted_final` を返す。`app.py._apply_disturbances()` が植生を session と plantings シートへ反映し、「🌿 庭の移ろい」バナーで表示。

テスト: `tests/test_disturbance.py`（pytest 不要・stdlib のみ・9ケース）。

---

## 5. sheets_client.py — あしあと修正

**問題**: `access_logs` シートがヘッダー行なしで作られた場合、`get_all_records()` が最初のデータ行をヘッダーと誤認して全キーが壊れていた。

**修正**: `_ensure_access_logs_sheet()` を追加。

```python
def _ensure_access_logs_sheet():
    # シートを取得 or 作成
    # 先頭行が数字（＝データ行）なら header を先頭に挿入
    # → 以後 get_all_records() が正常動作する
```

`log_access()` と `load_visit_calendar()` はこの関数を経由するようになった。

---

## 6. 既存ネットワーク図（tab_network）

`app.py` の `tab_network` に**食物網（trophic network）グラフ**が実装済み。

- ノード: 植物（緑）→ 昆虫（橙）→ 鳥（来訪は色付き、未訪問は淡色）
- エッジ: 「食べる」関係
- レイアウト: `engine.force_directed_layout()` による同心円シェル
- ハブ種検出、次数によるノードサイズ、ホバーでエッジハイライト
- **植えた植物に連動**（≠ 観察済み鳥には連動しない）

`ecology.py` の共起ネットワークとは**データの意味が異なる（食べる vs 一緒に見られる）**。別グラフとして追加するのは混乱を招くため推奨しない。

---

## 7. GloBI の使われ方

GloBI は鳥の種カタログではなく**種間相互作用（食物網）データベース**。

| 用途 | 使い方 |
|---|---|
| `globi_client.py` | API クライアント。`get_diet(学名)` → 「その鳥が食べるものの学名リスト」 |
| `build_globi_cache.py` | 初回のみ手動実行してディスクキャッシュ生成 |
| `centrality.py` | Sony CSL 補正済みデータセットから PageRank を読む（レア度補正に使用） |
| `engine.py` | `_try_load_centralities()` で起動時に一度だけロード |

**「GloBI から鳥の種を増やす」は用途ミスマッチ**。逆引き（`targetTaxon=Aves` + 地域 bbox）で「このバイオームに実在する鳥」を取る手法は技術的には可能だが、現状は手書きの 35 種にとどめている。

---

## 8. 確定済みの設計判断（覆すなら要確認）

| 判断 | 理由 |
|---|---|
| 競争排除則を踏まえた共起モデル | 「同じ餌を分け合う=仲間」は生態学的に誤り |
| 鳥の録音帰属テキスト（🎙この声は…）を削除 | ユーザーが不要と判断 |
| ラジオタブ + ホームへの埋め込み（2箇所） | key_prefix で分離済み |
| `st.iframe()` のみ使用（`components.v1.html` を使わない） | 2026-06-01 以降削除予定 |
| Google Sheets 永続化 | Streamlit Cloud のステートレス制約を回避 |
| 通知機能なし | 罰なし原則・継続性はテストで検証 |
| 進捗バー・警戒度数値の非表示 | 5つの設計原則（PROJECT_SPEC.md §3-3）|

---

## 9. セッション state のキー一覧（主要）

| キー | 型 | 内容 |
|---|---|---|
| `current_tester_id` | str | ログイン中のテスターID（"tester_01" 等） |
| `biome` | str | 現在のバイオーム（"kyoto" / "sydney" / "charlotte"） |
| `month` | int | アプリ内月（1–12） |
| `planted` | list[str] | 植えた植物 ID のリスト |
| `residents` | set[str] | 現在滞在中の鳥 ID |
| `discovered` | set[str] | 図鑑発見済みセット |
| `observed` | dict | `{bird_id: {count, first, last}}` 近距離観察記録 |
| `radio_ready` | bool | ラジオタブの開始状態 |
| `radio_shuffle` | int | 顔ぶれシャッフルカウンター |
| `ritual_ready` | bool | 儀式UI の遅延初期化フラグ |

---

## 10. 外部サービスと認証

| サービス | 認証方法 | ファイル |
|---|---|---|
| Google Sheets | サービスアカウント JSON | `credentials.json`（.gitignore） |
| xeno-canto API | APIキー 1行 | `xc_api_key.txt`（.gitignore） |
| Freesound API | APIキー 1行 | `freesound_api_key.txt`（.gitignore、任意） |
| GloBI API | 認証不要 | — |
| Sony CSL データセット | 手動 DL | `interaction_with_centrality_corrected.tsv.xz`（.gitignore、任意） |

Streamlit Cloud では Secrets に credentials.json の内容を設定。ローカル実行はファイル直置き。

---

## 11. 競合と差別化

| 競合 | 強み | Toris との違い |
|---|---|---|
| Merlin Bird ID（Cornell） | AI音声識別、無料 | Toris は「なぜここに来るか」。識別の土俵では戦わない |
| Birdfull（Steam, 96%好評） | 庭に鳥を呼ぶ収集 idle ゲー | 音響体験 × 生態学的正しさで差別化 |
| Birda | SNS + ゲーミフィケーション | Toris は孤独な静寂体験。コミュニティ軸ではない |

**Toris の堀（模倣困難な要素）**:

1. **音響エンジン**（AGC + 呼応 + HRTF + リバーブ + アンビエント）の再現コストが高い
2. **生態学的正しさ**（食物網 + 共起ネットワーク）に裏付けられた顔ぶれ選定
3. **早期展開によるユーザーデータの蓄積**（観察記録・足跡）

---

## 12. 未着手・次フェーズ候補

優先度の高い順:

1. **鳥種の拡充（〜50種へ）** — 手作業で xeno-canto ID を追加するだけ。GloBI 逆引きで候補を半自動抽出する手法も可能。先に「なぜ増やすか」（バイオーム追加 or 季節レア鳥）の方針を決める。
2. **Streamlit Cloud への公開デプロイ** — 現状 secrets / requirements.txt は整っており、ボタン 1 つでデプロイ可能。Google OAuth との統合でテスターID を Googleアカウント紐付けに変更できる。
3. **app.py の分割** — 2400 行超。タブごとにファイル分割（`tab_home.py`、`tab_birds.py` 等）を推奨。
4. **食物網グラフと観察データの統合** — 現在、ネットワーク図は「植えた植物」ベース、ラジオは「観察済み鳥」ベース。これを揃えると体験が一本化される。

---

## 13. やってはいけないこと

（`PROJECT_SPEC.md §7` より転記・更新）

- ランキング / 対戦 / フレンド機能
- スタミナ / 行動回数制限
- 「逃げました」罪悪感通知
- 進捗バー・距離数値・警戒度メーター表示
- 安全モード（逃げない設定）
- 「ecology.py で分け合う= 仲間」（競争排除則に反する）
- `components.v1.html()` の新規使用（廃止予定）
- 既存のネットワーク図に共起エッジを混ぜる（食べる関係と共起関係は別の意味）

---

## 14. クイックスタート（ローカル開発）

```bash
# 依存インストール
pip install -r toris_collection/requirements.txt

# credentials.json / xc_api_key.txt を toris_collection/ に配置

# 起動
streamlit run toris_collection/app.py

# 構文チェック(コミット前)
python -c "import ast; [ast.parse(open(f).read()) for f in ['app.py','radio.py','ecology.py']]"
```

---

## 改訂履歴

| 日付 | 内容 |
|---|---|
| 2026-06-11 | 初版（本ファイル）: ラジオ・ecology・sheets修正を反映した最新引き継ぎ書として作成 |
| 2026-05-26 | `PROGRESS.md` に実装ステータスを記録（旧） |
| 2026-05-20 | `PROJECT_SPEC.md` に全体設計を記録（旧） |
