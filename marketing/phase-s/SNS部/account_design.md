# アカウント設計書（Phase S / 元指示書 2-2 成果物A）

**担当: SNS部｜文責の最終確定・開設操作はCEO（本書は下書き）｜言語: 英語ファースト**

## 読んだ一次情報（このドキュメントの根拠）
- `toris_collection/docs/team/00_共通サマリ.md`（交渉不能の原則5つ）
- `toris_collection/docs/team/02_SNS部.md`（発信の芯・禁止事項）
- `toris_collection/CONCEPT_v2.md`（一行コンセプト・3本の柱・差別化）
- `landing/page.html`（現行公開LPのトーン・語彙。"Grow a tiny ecosystem. The birds come — and become your radio." / "Become a monitor" / "No chores, no rushing" / quiet promises / xeno-canto・GloBIクレジット）
- `toris_ceo_kettei_memo_phase_s.md`（決定3: 受け皿は「LP＋Googleフォーム」に一本化。メール方式は将来廃止予定）
- `toris_sns_setup_shijisho.md`（§0 戦略前提・§1 チャネル表・2-2 成果物A）
- 実アセット確認: `toris_collection/static/icons/icon-512.png`（緑ドット絵鳥）/ リポジトリ直下 `ヘッダー.png`（9羽グリッド）

## 未確認 / 推測（断定しないもの — 要CEO確認）
- **ハンドルの空き状況・商標衝突は一切確認できていない**（SNS部はWeb検索・商標DB照会を行えない）。本書の衝突評価はすべて一般論からの**推測**であり、各プラットフォームでの実際の空き確認・確保はCEOが行うこと。
- 各プラットフォームのbio文字数上限は一般に知られた目安（X≈160 / TikTok≈80 / Instagram≈150 / YouTube説明は長文可 / Redditはサイドバー短文）を前提にしている。仕様変更があり得るため、入力時に画面表示のカウンタで最終確認すること。
- 受け皿URL（LP・Googleフォーム）は決定3で「LP＋フォーム一本化」が方針。**フォーム配線は開発部の作業中で、確定URLは未定**。bio内リンクは開設時点の確定URLに差し替えること（下書きではプレースホルダ `[LP_URL]` を使用）。

---

## 1. 統一ハンドル案（3案）

方針: X/TikTok/Reels(Instagram)/Shorts(YouTube)/Reddit で**同一文字列**を使えることを優先。
制約の実務的な最小公倍数として、**Xの15文字上限**と**全プラットフォーム共通で安全な文字（英小文字・数字・アンダースコアのみ。ピリオド/ハイフンは一部で不可のため不使用）**に収まる案に限定した。

| 案 | ハンドル | 文字数 | 狙い | 推測される衝突リスク（※要CEO実確認） |
|---|---|---|---|---|
| **A（本命）** | `toriscollection` | 15 | ブランド名と完全一致。想起・検索一致が最も強い | 一般名詞ではなく造語寄りで**衝突は比較的低め**と推測。ただしXは15文字ちょうど＝上限ぎりぎりで余白ゼロ。既に誰かが確保している可能性は排除できない |
| **B** | `torisradio` | 10 | LPの核「集めた鳥で自分だけのラジオ」を体現。短く余白もある | "radio"は一般語のため**同名の音楽/ポッドキャスト系アカウントと部分衝突の可能性**あり。完全一致衝突は低めと推測 |
| **C** | `torisgarden` | 11 | 「手のひらの小さな庭/バイオーム」を示唆。やわらかい語感 | "garden"は一般語で**園芸系アカウントと近接**しうる。完全一致衝突は低めと推測 |

**推奨運用**: まずAを全5プラットフォームで確保トライ。1つでも取れない場合は「全プラットフォーム統一」を優先してB→Cへ全体を切り替える（バラバラのハンドルにしない=クロス導線が崩れるため）。どの案でも、確保できたら**残りの案を防衛的に確保**しておくとなりすまし予防になる（任意）。

**表記の統一（ハンドルと別に固定するもの）**
- 表示名（Display name）: `Toris Collection`（LPのブランド表記に一致。`#`記号はハンドル/表示名には入れない=検索とメンションの妨げになるため）
- Reddit: ユーザー名は `u/toriscollection` 等。将来サブレディットを作る場合は別途CEO判断（Phase Sではsubreddit運用はしない=指示書§1「宣伝はまだしない」）。

---

## 2. 英語bio（長短2〜3版・LPと受け皿への導線込み）

すべて**静か・誠実・非煽り**（原則1・SNS部トーン）。数値/煽り/絵文字乱用なし。
リンク導線の文言はLPのCTA「**Become a monitor**」に合わせて統一する。

### 2-1. ショート版（TikTok ≈80字目安。Reddit短文欄にも流用可）
> Grow a tiny ecosystem. Real birds arrive — and become your own radio.

（68字。TikTokは別途「リンク欄」があるためbio本文に生URLを入れない。プロフィールのリンク枠へ `[LP_URL]`）

代替（癒し文脈を前面に）:
> A quiet bird game. Real recordings, real ecology. No rushing.

### 2-2. ミディアム版（Instagram / X ≈150–160字目安）
> A quiet, passive bird game. Grow a tiny ecosystem and real birds arrive to sing — every one you meet joins a radio that's yours alone. Android closed test ↓

（157字前後。末尾「↓」はIG/Xのリンク枠を指す。Xはbio内に生URLを置くとリンク枠と重複するため、URLは**プロフィールのwebsite欄**に `[LP_URL]` を入れ、bio末尾は「Android closed test ↓」で受ける）

X用の別案（build in public 人格を少し出す）:
> Grow a tiny ecosystem; real birds arrive and become your own radio. Real songs (xeno-canto), real food web (GloBI). Building it quietly. Android closed test ↓

### 2-3. ロング版（YouTube チャンネル説明 / Instagramの補助文 / Reddit自己紹介用）
> **Toris Collection** is a quiet, passive app about tending a tiny ecosystem in the palm of your hand. Plant a little, let time pass, and real birds arrive to sing — every bird you meet joins a gentle radio that's yours alone, fuller each time you meet a new one. No chores, no rushing; you just listen.
>
> The songs are real field recordings from **xeno-canto** (with recordist credits). Which bird comes, and why, follows a real food web built from open interaction data (**GloBI**). The birdsong and the calm are always free.
>
> It's in Android closed testing now, and we're looking for a few gentle monitors. If you'd like a garden of your own, you can join here → **[LP_URL]**

**導線の使い分け（決定3準拠）**
- 現行LPは「Become a monitor」→ メール下書き方式。**将来Googleフォームに差し替わる**（開発部作業中）。bioリンクは常に**LPトップ `[LP_URL]`** を指す（LP側の受け皿がメール→フォームに変わってもbioは触らずに済む）。bio内に `rokkyofarm@gmail.com` の生アドレスは載せない（将来廃止予定＝決定3、かつスパム収集を避けるため）。
- 「pre-register」等の表現は使わない: 現段階はPlay事前登録ページが存在しない（決定3の指摘）。実態に合わせ **"Android closed test" / "Become a monitor"** に統一する（原則4 生態/事実に誠実の精神をSNS表記にも適用）。

---

## 3. プロフィール画像・ヘッダーの仕様指定

既存アセットを活用（新規制作を$0前提で避ける）。配色は #7ba87b / #5a7a5a 系＝LPのfoliage green（`--moss #5f7d55` / `--moss-deep #3f5c37`）に整合。

### 3-1. プロフィール画像（アイコン）
- **元素材**: `toris_collection/static/icons/icon-512.png`（緑のドット絵鳥）。
- **構図**: 鳥を中央に、四辺に十分な余白。**全プラットフォームが円形にクロップする**前提で、鳥の輪郭が円の内側に完全に収まるよう安全域を確保（外周約15%は背景のみ）。
- **背景**: 単色のセージ系。ライト基調 `#ecf1e3`（LPの `--paper`）を基準色に、鳥の緑が沈む場合はわずかに明るい `#f6f8ee`（LPの `--plate`）も可。グラデ・影・文字は入れない（静かなトーン維持）。
- **ドット感**: `image-rendering: pixelated` 相当のクッキリ感を保つため、**整数倍リサイズ**（512→1024等）で書き出し、アンチエイリアスでぼかさない。
- **書き出しサイズ**: 各プラットフォームの推奨に合わせるが、元は正方形1枚（例1024×1024）を用意し、各所でアップロード。X/IG/TikTok/YouTube/Redditすべて正方形1枚で兼用可。
- 開発部への依頼事項（素材書き出しが必要な場合のみ）: 「icon-512を背景 `#ecf1e3` 上に中央配置し、外周余白15%・整数倍で1024pxに」。**新規イラスト制作は不要**。

### 3-2. ヘッダー / バナー
- **元素材**: リポジトリ直下 `ヘッダー.png`（9羽グリッド）。
- **狙い**: 「集めるほど増える仲間（the cast）」をひと目で伝える。LPの Plate I（9羽グリッド）と同じ世界観で一貫させる。
- **配色/背景**: セージ〜foliage green（#7ba87b / #5a7a5a）を基調。9羽グリッドの周囲に同系の余白を足してアスペクト比を合わせる（グリッド自体は引き伸ばさない=ドット絵を歪めない）。
- **プラットフォーム別アスペクト比（目安。入力時に実画面で最終確認）**:
  | 用途 | 目安比率 | 注意 |
  |---|---|---|
  | X ヘッダー | 横長（約3:1, 1500×500） | 左下にアイコンが重なる。9羽グリッドは**中央〜右寄せ**で被り回避 |
  | YouTube バナー | 超横長（2048×1152、安全域中央1235×338） | 重要要素は**中央安全域**に集約。端は見切れ前提 |
  | Instagram | ヘッダー画像枠なし | 不要（プロフ画像のみ） |
  | TikTok | 縦寄りの狭い帯 | 9羽を1〜2列に切り出す等、簡素に |
  | Reddit プロフィールバナー | 横長 | Xに準拠で流用可 |
- **文字入れ**: 原則なし。入れる場合も1行まで（例: "Grow a tiny ecosystem — the birds become your radio."）。LP同様セリフ体の雰囲気に寄せ、煽り語・絵文字は不可。
- 開発部への依頼事項（必要時のみ）: 「`ヘッダー.png` の9羽グリッドを歪めず、背景 #7ba87b〜#5a7a5a の帯に中央配置して各アスペクト比へパディング書き出し」。

---

## 4. 完了定義に対する自己チェック
- CEOが承認後そのまま開設作業に使えるか: ハンドル3案・bio長短3版・画像/ヘッダー仕様が揃っており可。**ただしハンドル空き確認と確定URL差し替えの2点はCEO作業として残る**（本書で明示済み）。
- 交渉不能の原則との整合:
  - 原則1（受動的）: 「No chores, no rushing」「quiet/passive」で一貫。時間圧・CTA連呼なし。
  - 原則3（声と癒しは無料）: ロング版bioに "The birdsong and the calm are always free"。課金誘導を主役にしていない。
  - 原則4（生態に誠実）: xeno-canto（要クレジット）・GloBIを事実として記載。「pre-register」等の実在しない導線語を排し "closed test" に統一。
  - 原則5（かわいさ最優先）: ドット絵鳥アイコン・9羽グリッドを訴求の中心に据えた。
  - SNS部禁止事項: 他アプリ比較なし、ランキング表現なし、募金・課金の押し付けなし。
