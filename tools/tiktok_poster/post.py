#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TikTok Content Posting API — inbox(下書き)アップロード用ツール.

用途: 完成済みの縦動画(mp4)を CEO の TikTok「下書き(inbox)」へ自動送信する。
- OAuth 2.0 (Login Kit) + Content Posting API v2 の FILE_UPLOAD / inbox フロー。
- 審査不要の video.upload スコープ(=inbox)。キャプション貼付と公開は
  TikTok アプリ内でユーザーが行う。

CLI:
    py tools/tiktok_poster/post.py auth
        OAuth 認可フロー(ブラウザを開き token.json を作成)。
    py tools/tiktok_poster/post.py upload <path-to-mp4>
        動画を inbox へアップロード。access_token 期限切れなら自動更新。

秘密情報は同ディレクトリの .env(gitignore 対象)から読む:
    TIKTOK_CLIENT_KEY=...
    TIKTOK_CLIENT_SECRET=...

このツールはアプリ本体(toris_collection/)には一切依存しない独立スクリプト。
標準ライブラリ中心。HTTP は requests があれば使い、無ければ urllib で実装する。
"""

import hashlib
import json
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# ---- HTTP バックエンド(requests 優先、無ければ urllib フォールバック) --------
try:
    import requests  # type: ignore

    _HAS_REQUESTS = True
except Exception:  # pragma: no cover - 環境依存
    import urllib.error
    import urllib.request

    _HAS_REQUESTS = False


# ---- 定数 --------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
TOKEN_PATH = os.path.join(HERE, "token.json")

# TikTok は登録済み Redirect URI と完全一致を要求する。
# 末尾スラッシュ付き(/callback/)でないと拒否されるため、必ず付ける。
REDIRECT_URI = "http://localhost:8080/callback/"
REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8080

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
STATUS_FETCH_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

SCOPE = "user.info.basic,video.upload"

# access_token の期限切れ判定に使う安全マージン(秒)
TOKEN_EXPIRY_MARGIN = 120


# ---- 小さなユーティリティ ----------------------------------------------------
class ToolError(Exception):
    """握りつぶさず、CLI 上で分かりやすく表示するためのエラー."""


def _load_env():
    """.env を最小パーサで読み、必須キーを返す.

    python-dotenv には依存しない(標準ライブラリのみ)。
    KEY=VALUE 形式。# 始まりの行と空行は無視。値の前後の空白/引用符は除去。
    """
    if not os.path.exists(ENV_PATH):
        raise ToolError(
            ".env が見つかりません。\n"
            f"  {ENV_PATH}\n"
            "同ディレクトリの .env.example をコピーして .env を作り、\n"
            "TIKTOK_CLIENT_KEY と TIKTOK_CLIENT_SECRET を記入してください。"
        )
    data = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            data[key] = val

    client_key = data.get("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = data.get("TIKTOK_CLIENT_SECRET", "").strip()
    if not client_key or not client_secret:
        raise ToolError(
            ".env に TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET が未設定です。\n"
            "TikTok developer portal のアプリから Client key / Client secret を取得し、\n"
            f"{ENV_PATH} に記入してください(値は共有しないでください)。"
        )
    return client_key, client_secret


def _http_post_form(url, form):
    """application/x-www-form-urlencoded な POST。JSON dict を返す."""
    body = urllib.parse.urlencode(form).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if _HAS_REQUESTS:
        resp = requests.post(url, data=form, headers=headers, timeout=60)
        return resp.status_code, _safe_json(resp.text)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return _urllib_send(req)


def _http_post_json(url, obj, access_token):
    """application/json な POST(Bearer 認証)。JSON dict を返す."""
    body = json.dumps(obj).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json; charset=UTF-8",
    }
    if _HAS_REQUESTS:
        resp = requests.post(url, data=body, headers=headers, timeout=60)
        return resp.status_code, _safe_json(resp.text)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return _urllib_send(req)


def _http_put_bytes(url, data_bytes, content_type, content_range):
    """アップロード URL への PUT(バイナリ)。(status, text) を返す."""
    headers = {
        "Content-Type": content_type,
        "Content-Range": content_range,
        "Content-Length": str(len(data_bytes)),
    }
    if _HAS_REQUESTS:
        resp = requests.put(url, data=data_bytes, headers=headers, timeout=300)
        return resp.status_code, resp.text
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # pragma: no cover - ネットワーク依存
        return e.code, e.read().decode("utf-8", "replace")


def _urllib_send(req):  # pragma: no cover - ネットワーク依存
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, _safe_json(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, _safe_json(e.read().decode("utf-8", "replace"))


def _safe_json(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": text}


def _raise_api_error(prefix, status, payload):
    """TikTok のエラーレスポンスを握りつぶさず整形して投げる."""
    err = {}
    if isinstance(payload, dict):
        err = payload.get("error") or {}
    code = err.get("code")
    message = err.get("message")
    log_id = err.get("log_id")
    detail = []
    if code:
        detail.append("code=%s" % code)
    if message:
        detail.append("message=%s" % message)
    if log_id:
        detail.append("log_id=%s" % log_id)
    if not detail:
        detail.append("HTTP %s / %s" % (status, json.dumps(payload, ensure_ascii=False)))
    raise ToolError("%s: %s" % (prefix, " / ".join(detail)))


def _is_ok_error(payload):
    """TikTok は成功時も error.code == 'ok' を返す。ok 判定を共通化."""
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    if err is None:
        return True
    return err.get("code") in (None, "ok")


# ---- トークン管理 ------------------------------------------------------------
def _load_token():
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_token(tok):
    # 取得時刻を刻んで、後から期限切れを判定できるようにする。
    tok = dict(tok)
    tok.setdefault("obtained_at", int(time.time()))
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(tok, f, ensure_ascii=False, indent=2)
    # トークンファイルは他人に読まれないよう控えめな権限に(POSIX のみ有効)。
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except Exception:
        pass


def _token_is_expired(tok):
    obtained = tok.get("obtained_at", 0)
    expires_in = tok.get("expires_in", 0)
    return time.time() >= (obtained + expires_in - TOKEN_EXPIRY_MARGIN)


def _refresh_token(client_key, client_secret, tok):
    refresh = tok.get("refresh_token")
    if not refresh:
        raise ToolError(
            "refresh_token がありません。もう一度 `auth` を実行してください。"
        )
    print("access_token を更新しています...")
    status, payload = _http_post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        },
    )
    if not isinstance(payload, dict) or "access_token" not in payload:
        _raise_api_error("トークン更新に失敗", status, payload)
    _save_token(payload)
    return payload


def _get_valid_access_token(client_key, client_secret):
    tok = _load_token()
    if not tok:
        raise ToolError(
            "まだ認可されていません。先に次を実行してください:\n"
            "    py tools/tiktok_poster/post.py auth"
        )
    if _token_is_expired(tok):
        tok = _refresh_token(client_key, client_secret, tok)
    access = tok.get("access_token")
    if not access:
        raise ToolError(
            "access_token が空です。もう一度 `auth` を実行してください。"
        )
    return access


# ---- OAuth 認可フロー --------------------------------------------------------
class _CallbackHandler(BaseHTTPRequestHandler):
    # クラス変数に受信結果を格納(1リクエストで停止するため十分)。
    received = {}

    def do_GET(self):  # noqa: N802 (http.server の規約)
        parsed = urllib.parse.urlparse(self.path)
        # 登録 Redirect URI は末尾スラッシュ付き(/callback/)。
        # ブラウザ実装差を吸収するため両方を受け付ける。
        if parsed.path not in ("/callback/", "/callback"):
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.received = {
            "code": (qs.get("code") or [None])[0],
            "state": (qs.get("state") or [None])[0],
            "error": (qs.get("error") or [None])[0],
            "error_description": (qs.get("error_description") or [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = _CallbackHandler.received.get("code") and not _CallbackHandler.received.get("error")
        msg = (
            "<h2>認可が完了しました。</h2><p>このタブを閉じて、ターミナルに戻ってください。</p>"
            if ok
            else "<h2>認可に失敗しました。</h2><p>ターミナルのメッセージを確認してください。</p>"
        )
        html = "<!doctype html><meta charset='utf-8'><body style='font-family:sans-serif'>" + msg + "</body>"
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, *args):  # サーバのアクセスログを抑制
        return


def cmd_auth(client_key, client_secret):
    state = secrets.token_urlsafe(24)
    # TikTok は desktop 認可に PKCE を必須とする。
    # 重要: TikTok は code_challenge を「SHA256 の hex エンコード」で要求する
    # (標準 PKCE の base64url ではない)。code_challenge_method は S256 のみ対応。
    # code_verifier は毎回新規生成([A-Za-z0-9-_]・43-128字)。
    code_verifier = secrets.token_urlsafe(60)
    code_challenge = hashlib.sha256(code_verifier.encode("ascii")).hexdigest()
    params = {
        "client_key": client_key,
        "scope": SCOPE,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)

    # コールバックを待つローカルサーバを先に立てる。
    _CallbackHandler.received = {}
    try:
        httpd = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler)
    except OSError as e:
        raise ToolError(
            "localhost:%d を開けませんでした(%s)。\n"
            "他のプロセスがポートを使っていないか確認してください。" % (REDIRECT_PORT, e)
        )

    print("ブラウザで TikTok の認可ページを開きます。")
    print("開かない場合は次の URL を手動で開いてください:\n" + url + "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("ブラウザでログイン・許可すると、ここに自動で戻ります(待機中)...")
    # 1リクエスト(=callback)だけ処理する。
    httpd.handle_request()
    httpd.server_close()

    got = _CallbackHandler.received or {}
    if got.get("error"):
        raise ToolError(
            "認可が拒否/失敗しました: %s / %s"
            % (got.get("error"), got.get("error_description"))
        )
    if got.get("state") != state:
        raise ToolError(
            "state が一致しません(CSRF 検証失敗)。もう一度 `auth` を実行してください。"
        )
    code = got.get("code")
    if not code:
        raise ToolError("認可コード(code)を取得できませんでした。")

    print("認可コードを取得しました。アクセストークンと交換しています...")
    status, payload = _http_post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    if not isinstance(payload, dict) or "access_token" not in payload:
        _raise_api_error("トークン交換に失敗", status, payload)

    _save_token(payload)
    print("\n認可に成功しました。トークンを保存しました:")
    print("  " + TOKEN_PATH)
    print("有効期限(access_token): 約 %s 秒。以後 upload 時に自動更新します。"
          % payload.get("expires_in", "?"))


# ---- inbox アップロード ------------------------------------------------------
def cmd_upload(client_key, client_secret, video_path):
    if not os.path.exists(video_path):
        raise ToolError("動画ファイルが見つかりません: %s" % video_path)
    if not video_path.lower().endswith(".mp4"):
        print("警告: 拡張子が .mp4 ではありません。TikTok は mp4/webm を推奨します。")

    video_size = os.path.getsize(video_path)
    if video_size <= 0:
        raise ToolError("動画ファイルが空です: %s" % video_path)

    access_token = _get_valid_access_token(client_key, client_secret)

    # この用途の動画は数MB。単一チャンクで確実に送る。
    chunk_size = video_size
    total_chunk_count = 1

    print("inbox 初期化中(video_size=%d bytes, 1 チャンク)..." % video_size)
    status, payload = _http_post_json(
        INBOX_INIT_URL,
        {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            }
        },
        access_token,
    )
    if not _is_ok_error(payload) or not isinstance(payload, dict):
        _raise_api_error("inbox 初期化に失敗", status, payload)
    data = payload.get("data") or {}
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url or not publish_id:
        _raise_api_error("upload_url/publish_id を取得できませんでした", status, payload)

    print("動画をアップロード中...")
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    content_range = "bytes 0-%d/%d" % (video_size - 1, video_size)
    put_status, put_text = _http_put_bytes(
        upload_url, video_bytes, "video/mp4", content_range
    )
    # PUT は 201 Created(全チャンク完了) / 206 Partial(継続) 等を返す。
    if put_status not in (200, 201, 206):
        raise ToolError(
            "動画アップロードに失敗しました(HTTP %s):\n%s" % (put_status, put_text)
        )

    # ステータス確認(任意・失敗しても致命ではない)。
    try:
        s_status, s_payload = _http_post_json(
            STATUS_FETCH_URL, {"publish_id": publish_id}, access_token
        )
        if isinstance(s_payload, dict) and _is_ok_error(s_payload):
            st = (s_payload.get("data") or {}).get("status")
            if st:
                print("現在のステータス: %s" % st)
    except Exception:
        pass  # ステータス確認の失敗はアップロード成否に影響しない

    print("\n================ 完了 ================")
    print("動画をあなたの TikTok 下書き(inbox)に送りました。")
    print("TikTok アプリで通知から開いて、キャプションを貼って公開してください。")
    print("publish_id: %s" % publish_id)
    print("=====================================")


# ---- エントリポイント --------------------------------------------------------
USAGE = (
    "使い方:\n"
    "  py tools/tiktok_poster/post.py auth\n"
    "  py tools/tiktok_poster/post.py upload <path-to-mp4>\n"
)


def main(argv):
    if len(argv) < 2:
        print(USAGE)
        return 2
    command = argv[1].lower()

    try:
        client_key, client_secret = _load_env()
    except ToolError as e:
        print("エラー: " + str(e))
        return 1

    try:
        if command == "auth":
            cmd_auth(client_key, client_secret)
            return 0
        if command == "upload":
            if len(argv) < 3:
                print("エラー: アップロードする mp4 のパスを指定してください。")
                print(USAGE)
                return 2
            cmd_upload(client_key, client_secret, argv[2])
            return 0
        print("不明なコマンド: %s" % command)
        print(USAGE)
        return 2
    except ToolError as e:
        print("エラー: " + str(e))
        return 1
    except KeyboardInterrupt:
        print("\n中断しました。")
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv))
