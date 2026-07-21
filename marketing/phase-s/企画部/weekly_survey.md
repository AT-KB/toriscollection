# 週次マイクロサーベイ — Googleフォーム文面(Phase S / 決定2b)
**根拠**: `toris_ceo_kettei_memo_phase_s.md` 決定2b(週次マイクロサーベイ=分析のサーバー基盤を作らない代替の柱)。設計=企画部、配信=CEO。
**位置づけ**: クローズドテスターへ週次で送る2問。定量ダッシュボードの代わりに、(1)PMFシグナル (2)「ユーザーの言葉」の一次ソース(→`user_language_pipeline.md`)を得る。
**運用メモ**: 件数ノルマなし・0件許容(急かさない=原則1)。回答は自動でスプレッドシートに集約。

---

## フォーム設定(CEO作成)
- forms.google.com →「空白のフォーム」。タイトル: **Toris Collection — weekly check-in**。
- 説明文(英語): *A quiet 30-second check-in. No wrong answers — we just want to hear how the garden feels.*
- 設定⚙️→「メールアドレスを収集する」は**任意**(匿名でも可。テスターの継続追跡をしたいならON)。「回答を1回に制限」OFF。
- 質問は下記2問。**送信→🔗リンク**を取得し、CEOが週1でテスターへ配布。

## 質問1(PMF / Sean Ellis テスト・単一選択・必須)
**How would you feel if you could no longer use Toris Collection?**
- Very disappointed
- Somewhat disappointed
- Not disappointed (it isn't that useful to me)

> ※判定の目安: 「Very disappointed」が回答の**40%以上**でPMFの初期シグナル(この段階では母数が小さいので"参考"扱い。決定2の通り定性重視)。

## 質問1-b(任意・記述・任意回答)
**What would you miss most?** *(one line is fine)*

## 質問2(「新しい鳥が来た瞬間」・記述・必須)
**Think of a moment a new bird arrived in your garden. Describe it — what did it feel like?**
> ※この自由記述が「ユーザーの言葉」パイプラインの主入力。delight/calm/surprise 等のタグ付け対象(→ASO文言・動画キャプション候補へ)。

## 質問3(任意・記述・任意回答)
**Anything that felt off, confusing, or like it was rushing you?**
> ※原則1(受動性)の逸脱検知に使う。「急かされた」という声が出たら要調査。

---

## 交渉不能5原則との整合
- 受動的◯(「30秒」「no wrong answers」、急かさない)/ 罰しない◯(否定回答も歓迎する文面)/ 声と癒しは無料◯(課金を問わない)/ 生態に誠実◯(誘導しない中立質問)/ かわいさ最優先◯(「how the garden feels」)。
- **要CEO確認**: メール収集ON/OFFの方針、配布チャネル(テスター向けメール/Discord等)、送信頻度の実運用。
