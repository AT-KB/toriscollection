# Toris Collection — 基盤整備（バックエンド移行）仕様書

最終更新: 2026-06-11
対象読者: **プログラミング初心者〜中級者**、次に開発を引き継ぐ人
位置づけ: ロードマップ「②基盤整備」の設計書。背骨と機能の正典は `HANDOFF_2026-06.md`。

> **この文書のゴール**
> いまの Google Sheets ベースのアプリを **壊さずに**、将来「本格データベース」や
> 「スマホアプリ（Google Play）」へ無理なく進めるための **構成と段取り** を決める。
> この文書の段階では **コードは変えません**。まず地図を描きます。

---

## 0. 3行まとめ

1. いまアプリは、あちこちから直接 Google Sheets を触っている。これだと DB に乗り換えにくい。
2. 間に「**保管庫（Storage）という共通の窓口**」を1枚はさむ。アプリはこの窓口だけに話しかける。
3. 窓口の裏側を「Sheets版」→「DB版」と差し替えれば、**アプリ本体を書き換えずに**引っ越せる。

---

## 1. なぜやるのか（動機）

いまの構成には、将来詰まる場所が3つあります。

- **スケールの天井**: Google Sheets は API 回数の上限が厳しく、数百ユーザーが限界。
- **Google Play への段差**: Streamlit はサーバ型 Web アプリで、スマホアプリにそのまま化けない。
- **本格ソーシャルの前提**: アカウント・「みんなの庭」の本格版は、まともな DB が要る。

これら3つは**同じ1つの基盤判断（Sheets → 本格DB）に依存**しています。だから今は新機能を増やすより、この土台を「いつでも差し替えられる形」に整える方が、長い目で安い。

**ただし最優先は機能ではなく検証（①）**。この文書（②）は①と並行して進める"土台の地ならし"で、**実際の大移行は①が「ループが回る」と示してから**着手します。今やるのは「壊さずに差し替え可能にする」ところまで。

---

## 2. 初心者向け用語集（先に読むと迷わない）

| 用語 | かみくだいた意味 | このアプリでの例 |
|---|---|---|
| **レイヤー（層）** | 役割ごとに分けたコードのまとまり | 画面／計算／データ保存 の3つ |
| **純粋関数** | 同じ入力なら必ず同じ出力。外部（DB・時刻・ネット）を触らない関数。テストが楽 | `flock_size()`, `ecology.co_occurrence()` |
| **I/O** | Input/Output。ファイル・DB・ネットなど外部とのやり取り | Google Sheets 読み書き |
| **リポジトリ（Storage）パターン** | データの出し入れを「共通の窓口」に集約する設計。中身（Sheets/DB）を隠す | `Storage` インターフェース |
| **インターフェース（Protocol）** | 「こういうメソッドを持つ」という約束だけ決めた型。中身は別に作る | `Storage`（約束）と `SheetsStorage`（中身） |
| **ストラングラー・フィグ** | 古い仕組みを一気に捨てず、新しい仕組みを横に生やして、少しずつ置き換える移行手法 | Sheets版の隣にDB版を作って並走 |
| **フィーチャーフラグ** | 設定1つで新機能/新挙動をオン・オフする仕組み。問題が出たら即戻せる | `STORAGE_BACKEND=sheets`／`=sql` |
| **マイグレーション** | 古いデータを新しい入れ物へ移す作業／スクリプト | Sheets の全行を DB に流し込む |
| **冪等（べきとう）** | 何回実行しても結果が同じこと。移行スクリプトに大事 | 2回流しても重複しない |

---

## 3. いまの構成（現状の地図）

```
            ┌──────────────── 画面（Streamlit）────────────────┐
            │  app.py / radio.py / ritual.py / community.py     │
            │  daily.py                                         │
            └───────┬───────────────────────┬──────────────────┘
                    │ 直接呼ぶ               │ 直接呼ぶ
        ┌───────────▼─────────┐   ┌─────────▼───────────────────┐
        │  計算（純粋ロジック） │   │  データ保存・外部API（I/O）   │
        │  engine, ecology,    │   │  sheets_client（Sheets直結）  │
        │  disturbance, flock, │   │  species_loader, xc_client,  │
        │  daily, absence_loop,│   │  freesound_client,           │
        │  mementos            │   │  observation_log, data.py    │
        └──────────────────────┘   └──────────────────────────────┘
```

**良い点**: 計算（コア）はすでに I/O から分かれていて、テストもある。👍
**詰まる点**: 画面や `absence_loop`/`observation_log` が **`sheets_client` を直接** import して呼んでいる。
つまり「Google Sheets」という具体に**あちこちが直結**している。ここを引っ越すと広範囲を書き換える羽目になる。

---

## 4. 目標の構成（これから目指す地図）

やることは1つだけ：**画面とコアの下に「Storage という1枚の窓口」をはさむ**。

```
            ┌──────────────── 画面（いまは Streamlit／将来 Flutter等）─┐
            └───────┬───────────────────────────────┬───────────────┘
                    │                                │
        ┌───────────▼─────────┐          ┌───────────▼───────────┐
        │  計算（純粋ロジック） │          │   Storage（窓口・約束） │ ← ★ここを新設
        │  そのまま再利用       │          │   load/save/add ...    │
        └──────────────────────┘          └───────────┬───────────┘
                                                       │ 裏で実装を差し替え
                                  ┌────────────────────┼────────────────────┐
                                  ▼                    ▼                    ▼
                         ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                         │ SheetsStorage│    │  SqlStorage  │    │FirebaseStorage│
                         │ (いまの中身) │    │ (将来・本命) │    │  (選択肢)     │
                         └──────────────┘    └──────────────┘    └──────────────┘
```

ポイント:

- **画面とコアは「Storage」という約束にだけ話しかける**。Sheets という言葉を直接知らなくなる。
- `SheetsStorage` は **いまの `sheets_client.py` をそのまま包むだけ**（挙動ゼロ変更）。
- 将来 `SqlStorage` を足して、設定（フィーチャーフラグ）で切り替える。**画面もコアも書き換え不要**。

これが Google Play への布石でもあります。スマホアプリは「画面」を別物（Flutter 等）に差し替え、`Storage` の裏を API 越しの DB にするだけ。**コアは一切書き直さない**。

---

## 5. Storage インターフェース（窓口の"約束"）

ドメイン（意味のまとまり）ごとにメソッドを並べます。中身はまだ書かず、**形だけ**先に決めます。
（実装時は `storage/base.py` に `typing.Protocol` で定義する想定。）

```python
class Storage(Protocol):
    # --- テスター ---
    def list_testers(self) -> list[tuple[str, str]]: ...
    def reset_tester(self, tester_id: str) -> None: ...

    # --- 庭の状態 ---
    def load_field_state(self, tester_id: str) -> dict | None: ...
    def save_field_state(self, tester_id, biome, temp, season, birds: list) -> None: ...

    # --- 植栽 ---
    def load_active_plantings(self, tester_id: str) -> list[str]: ...
    def load_active_plantings_with_time(self, tester_id) -> list[tuple[str, str]]: ...
    def add_planting(self, tester_id, plant_id) -> None: ...
    def remove_planting(self, tester_id, plant_id) -> bool: ...
    def remove_all_plantings(self, tester_id) -> None: ...

    # --- 訪問・コレクション ---
    def add_visit(self, tester_id, bird_id, visit_type, **meta) -> None: ...
    def load_collection_set(self, tester_id) -> set[str]: ...
    def upsert_collection(self, tester_id, bird_id) -> None: ...
    def load_all_collection(self) -> list[dict]: ...   # みんなの庭（匿名集計の素材）

    # --- 落とし物・メモ・ログ・あしあと ---
    def add_memento(self, tester_id, memento_id, kind, target_id, biome, via_bird_id) -> None: ...
    def load_mementos(self, tester_id) -> list[dict]: ...
    def load_bird_notes(self, tester_id) -> dict: ...
    def save_bird_note(self, tester_id, bird_id, location, note_text) -> None: ...
    def load_visit_calendar(self, tester_id) -> dict: ...
    def log_access(self, tester_id, screen, action, details="") -> None: ...
```

> これは**いまの `sheets_client.py` の関数一覧とほぼ同じ**。だから `SheetsStorage` は
> 「self を足して既存関数へ受け流す」だけで完成し、**挙動は1ミリも変わりません**。

---

## 6. DB スキーマ案（将来 `SqlStorage` 用）

Sheets の各タブ＝DB の各テーブルに、ほぼ1対1で対応します。`tester_id` に索引を張るのが肝。

```sql
-- 鳥・植物・昆虫は species_* シードと同じ。種データは別テーブル or 設定ファイル。

CREATE TABLE testers (
  tester_id     TEXT PRIMARY KEY,
  display_name  TEXT,
  created_at    TIMESTAMP DEFAULT now()
);

CREATE TABLE field_state (
  tester_id        TEXT PRIMARY KEY REFERENCES testers,
  biome            TEXT,
  current_temp     REAL,
  current_season   TEXT,
  current_birds    JSONB,          -- 滞在中の鳥IDの配列
  last_access_at   TIMESTAMP,
  updated_at       TIMESTAMP DEFAULT now()
);

CREATE TABLE plantings (
  id          BIGSERIAL PRIMARY KEY,
  tester_id   TEXT REFERENCES testers,
  plant_id    TEXT,
  planted_at  TIMESTAMP DEFAULT now(),
  status      TEXT DEFAULT 'active'   -- 'active' | 'removed'
);
CREATE INDEX ON plantings (tester_id, status);

CREATE TABLE bird_visits (
  id            BIGSERIAL PRIMARY KEY,
  tester_id     TEXT REFERENCES testers,
  bird_id       TEXT,
  visit_type    TEXT,                 -- 'live' | 'absence' | 'ritual'
  reason_text   TEXT,
  related_plant_id  TEXT,
  related_insect_id TEXT,
  arrived_at    TIMESTAMP
);
CREATE INDEX ON bird_visits (tester_id);

CREATE TABLE collection (
  tester_id     TEXT REFERENCES testers,
  bird_id       TEXT,
  first_seen_at TIMESTAMP,
  last_seen_at  TIMESTAMP,
  visit_count   INTEGER DEFAULT 1,
  PRIMARY KEY (tester_id, bird_id)
);
CREATE INDEX ON collection (bird_id);   -- みんなの庭の集計用

CREATE TABLE mementos (
  id          BIGSERIAL PRIMARY KEY,
  tester_id   TEXT REFERENCES testers,
  memento_id  TEXT,                   -- 'feather:shijukara' 形式
  kind        TEXT,
  target_id   TEXT,
  biome       TEXT,
  via_bird_id TEXT,
  found_at    TIMESTAMP DEFAULT now(),
  notes       TEXT
);
CREATE INDEX ON mementos (tester_id);

CREATE TABLE bird_notes (
  tester_id      TEXT REFERENCES testers,
  bird_id        TEXT,
  location       TEXT,
  note_text      TEXT,
  first_saved_at TIMESTAMP,
  updated_at     TIMESTAMP,
  PRIMARY KEY (tester_id, bird_id)
);

CREATE TABLE access_logs (
  id         BIGSERIAL PRIMARY KEY,
  tester_id  TEXT,
  screen     TEXT,
  action     TEXT,
  details    TEXT,
  timestamp  TIMESTAMP DEFAULT now()
);
CREATE INDEX ON access_logs (tester_id, timestamp);
```

DB の候補:
- **Postgres（推奨）**: SQL で堅い。Supabase 等を使えば認証・ホスティング込みで安い。
- **Firebase/Firestore**: スマホとの相性が良く、リアルタイム同期が楽。SQL ではない点に注意。

---

## 7. 壊さない移行手順（ストラングラー・フィグ）

**各フェーズの終わりで「アプリは今まで通り動く／テストは緑」を必ず確認**します。

### フェーズ0 — 地図を描く（＝この文書。コード変更なし）✅ 今ここ
現状と目標、Storage の約束、DB スキーマを文章で確定する。

### フェーズ1 — 窓口を"追加"する（挙動ゼロ変更）
- `storage/base.py` に `Storage`（Protocol）を定義。
- `storage/sheets_storage.py` に `SheetsStorage` を作り、**中身は既存 `sheets_client` の関数へ受け流すだけ**。
- 既存コードはまだ触らない（`sheets_client` も残す）。
- ✔ 確認: 既存テスト緑＋`SheetsStorage` の薄いテスト追加。アプリ挙動は不変。

### フェーズ2 — 呼び出しを窓口経由に少しずつ寄せる
- 画面・`absence_loop`・`observation_log` の `import sheets_client` を、**1ファイルずつ** `Storage` 経由に置換。
- 1ファイル替えるたびに動作確認。全部終わると「直接 Sheets を触る場所」が `SheetsStorage` だけになる。
- ✔ 確認: 各差し替え後にアプリが起動し、保存/読込が今まで通り。

### フェーズ3 — DB 版を"横に"生やす（フラグでオフのまま）
- `storage/sql_storage.py` に `SqlStorage` を実装（フェーズ6 のスキーマに対応）。
- 環境変数 `STORAGE_BACKEND`（既定 `sheets`）で選べるようにする。**既定は Sheets のまま**。
- ✔ 確認: フラグ `sheets` では完全に従来通り。`sql` でローカル検証だけ可能。

### フェーズ4 — データ移行スクリプト（冪等）
- `scripts/migrate_sheets_to_sql.py`：Sheets 全行を読み、DB に流し込む。**2回流しても重複しない**よう upsert。
- ✔ 確認: 移行後、件数とサンプルが一致。

### フェーズ5 — 切り替え（保険つき）
- 検証 OK なら本番フラグを `sql` に。Sheets は**しばらく読み取り保険として残す**。
- 問題が出たらフラグを `sheets` に戻すだけで即ロールバック。
- ✔ 確認: 本番で1〜2週間、両睨み。

> **大事**: フェーズ1〜2 は①の検証と**並行して今でも安全**にできる地ならし。
> フェーズ3〜5（実DB）は**①が「ループが回る」と示してから**で十分。

---

## 8. 壊さないためのガードレール

- **テストが安全網**: 純粋ロジックの既存テスト（disturbance/flock/daily/community）は常に緑に保つ。`SheetsStorage`/`SqlStorage` には「同じ入力で同じ結果」を比べる契約テストを足す。
- **フィーチャーフラグ**: 新バックエンドは常に設定でオフにできる。即ロールバック可能に。
- **1回1ファイル**: フェーズ2 は小さな差し替えを積む。大きな一括変更をしない。
- **Sheets を急に消さない**: 切替後も一定期間は保険として残す。
- **秘密情報**: `credentials.json`・各 API キー・DB 接続文字列は `.gitignore` と Secrets 管理を厳守。

---

## 9. この文書のスコープ外（今はやらない）

- 画面の Flutter/React Native 書き直し（Play 本番化の段階で別途）。
- ログイン認証・課金（Play Billing）の実装。
- `app.py`（約2,600行）の機能的なリファクタ。**今回は層の地図と窓口の設計だけ**。

---

## 10. 次の一歩（この文書のあと）

1. この設計でよければ、**フェーズ1**（`storage/` パッケージ新設＋`SheetsStorage` で既存を包む・挙動ゼロ変更）を小さな PR で出す。
2. 続けて**フェーズ2**を1ファイルずつ。
3. ①の検証結果を見て、フェーズ3以降（実DB）に進むか判断する。

> まとめ: **いまは「窓口を1枚はさむ設計」を確定しただけ**。コードは無傷。
> ここから先は、テストを緑に保ちながら、小さく安全に積んでいく。
