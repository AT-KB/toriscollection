# TikTok Poster (inbox 下書きアップロード)

完成済みの縦動画(mp4)を、CEO の TikTok「**下書き(inbox)**」へ自動送信する
独立ツールです。SNS 運用の投稿自動化に使います。**アプリ本体(`toris_collection/`)
とは無関係**の、リポジトリ直下 `tools/tiktok_poster/` に閉じたスクリプトです。

- OAuth 2.0 (Login Kit) + Content Posting API v2 の **FILE_UPLOAD / inbox フロー**。
- 使うスコープは `user.info.basic,video.upload`。**`video.upload`=inbox は審査不要**。
- **キャプションの入力と公開は、TikTok アプリ内で人間が行います**
  (このツールは「下書きに送る」ところまで)。

---

## 前提(CEO が TikTok developer portal 側で用意しておくこと)

1. TikTok for Developers でアプリを作成済みであること。
2. そのアプリに **Content Posting API** を追加し、スコープ
   **`video.upload`** と **`user.info.basic`** を有効化していること。
3. Login Kit の **Redirect URI** に **`http://localhost:8080/callback/`**(**末尾スラッシュ付き**)
   を登録済みであること。TikTok は登録値と**完全一致**を要求し、
   末尾スラッシュ無し(`/callback`)は**拒否されます**。大文字小文字も一致させること。
4. アプリの **Client key** と **Client secret** を取得済みであること。

> 補足(制約): 審査前(unaudited)のアプリでは、
> - **inbox(`video.upload`)** … 下書きへ送るところまでは動作します。ただし
>   実際の公開はアプリ内でユーザーが行います。
> - **direct-post(その場で本番公開)** … これは別スコープ `video.publish` で、
>   **App review(審査)が必要**です。本ツールは inbox のみを使うため、審査前でも運用可能です。
> - 審査前は、動画がアップロードできるのは基本的に**アプリの所有者/テストユーザー
>   自身のアカウント**に限られます(=CEO 自身のアカウントで使う想定)。

---

## セットアップ

### 1. `.env` を作る(秘密情報。コミット厳禁)

```powershell
cd tools\tiktok_poster
Copy-Item .env.example .env
notepad .env
```

`.env` に、CEO 自身が Client key / Client secret を貼ります(**誰とも共有しない**):

```
TIKTOK_CLIENT_KEY=あなたのクライアントキー
TIKTOK_CLIENT_SECRET=あなたのクライアントシークレット
```

`.env` と、認可後に生成される `token.json` は **`.gitignore` 済み**です。

### 2. 依存関係

- Python は `py` ランチャー(Windows / Python 3.14 で確認)。
- HTTP は `requests` があれば使い、無ければ標準ライブラリ `urllib` で動きます
  (追加インストール不要)。この環境では `requests` が入っています。

---

## 使い方

### 認可(初回のみ / トークン失効時)

```powershell
py tools\tiktok_poster\post.py auth
```

- ブラウザで TikTok の認可ページが開きます。ログインして許可すると、
  `http://localhost:8080/callback/`(末尾スラッシュ付き)にリダイレクトされ、
  ツールが自動でアクセストークンを取得し `token.json` に保存します。
- `state` を検証して CSRF を防いでいます。

取得されるトークン:
- `access_token`(約 24 時間)
- `refresh_token`(約 365 日)

### アップロード(動画を下書きへ送る)

```powershell
py tools\tiktok_poster\post.py upload "C:\path\to\video.mp4"
```

- `access_token` が期限切れなら、`refresh_token` を使って**自動更新**します。
- 成功すると次のように表示されます:

  > 動画をあなたの TikTok 下書き(inbox)に送りました。
  > TikTok アプリで通知から開いて、キャプションを貼って公開してください。

- この用途の動画(数 MB)は**単一チャンク**で送ります。

---

## 動作の中身(概略)

1. `POST /v2/oauth/token/`(`authorization_code` / `refresh_token`)でトークン取得・更新。
2. `POST /v2/post/publish/inbox/video/init/` に
   `source_info: {source: FILE_UPLOAD, video_size, chunk_size, total_chunk_count}` を送り、
   `upload_url` と `publish_id` を得る。
3. `PUT <upload_url>` に動画バイト列(`Content-Type: video/mp4`,
   `Content-Range: bytes 0-<size-1>/<size>`)。
4. `POST /v2/post/publish/status/fetch/` でステータス確認(任意)。

---

## トラブルシューティング

- **「先に auth を実行してください」** … `token.json` が無い/壊れている。`auth` をやり直す。
- **`state が一致しません`** … 認可の途中で別のフローが混ざった。もう一度 `auth`。
- **`localhost:8080 を開けませんでした`** … 8080 番ポートを他プロセスが使用中。
  そのプロセスを止めるか、開発ポータルの Redirect URI とツール側のポートを合わせて変更する。
- **TikTok の error.code/message がそのまま表示される** … 権限(scope)未付与、
  Redirect URI 不一致、審査状態などが原因。ポータル設定を確認する。
