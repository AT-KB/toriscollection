# TikTok App Review — 提出用 説明文(そのまま貼れる英語・1000字以内)

**用途**: developer portal の「Explain how each product and scope works...」欄(最大1000字)に貼る。
**方針**: 実装(`tools/tiktok_poster/post.py`)に忠実。誇張せず、inbox(下書き)専用・自分の1アカウントのみ・direct-post不使用を明記。

---

## 貼り付け用(英語・約990字)

```
Toris Collection is a quiet Android app for collecting birds by real recorded song. This developer app is a small internal command-line tool the app's creator uses to upload their OWN short promotional videos to their OWN TikTok account's drafts. It runs locally on the creator's computer; there is no public-facing website feature for other users.

Login Kit (scope: user.info.basic): The creator runs the tool, which opens TikTok's OAuth authorization page in a browser. The creator signs in and authorizes with their own TikTok account. user.info.basic is used only to complete OAuth and confirm the authorized account; no profile data is displayed, stored, or shared.

Content Posting API (scope: video.upload): After authorization, the tool uploads a finished vertical .mp4 to the creator's TikTok inbox using the FILE_UPLOAD "upload to inbox" flow (PUT to the returned upload_url). The video appears in the creator's TikTok drafts. The creator then reviews it, writes the caption, and publishes it manually inside the TikTok app.

We do NOT use Direct Post and nothing is auto-published. The tool posts only to the app owner's single account. No other users' accounts or data are accessed. End-to-end: run tool -> browser OAuth (Login Kit) -> authorize -> tool uploads mp4 to inbox (Content Posting API / video.upload) -> creator finalizes and posts in the TikTok app.
```

## 補足(審査を早く通すコツ)
- 選択中のProduct/Scopeは**Login Kit(user.info.basic)とContent Posting API(video.upload)のみ**にする。不要なスコープが残っていると審査が遅れる(TikTok注記)。
- デモ動画は**この文章と一致する流れ**を映す: ツール実行 → ブラウザのTikTok許可画面 → 許可 → ターミナルで「下書きに送信」表示 → TikTokアプリの下書きに動画が現れる。
- ドメインは `torriscollection.com`(登録済URLと一致)。
