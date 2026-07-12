"""
save_code.py - セーブコード(ローカル保存 MVP)

個人の進行データ(バイオーム・植えた植物・図鑑・落とし物・メモなど)を
1本の文字列(セーブコード)として書き出し・読み込みするための純粋関数群。

- サーバー(Google Sheets 等)には一切送らない。ユーザーが手元で保管する前提。
- 壊れたコード・不正な JSON・未知のバージョンは例外を投げず None を返す
  (`sheets_client.py` の「失敗時にも例外を投げない」流儀を踏襲)。
- 将来のフォーマット変更に備えて、セーブコードにはバージョン番号を含める。

依存は標準ライブラリのみ(base64 / json / zlib)。Streamlit にも依存しないため、
`app.py` から独立してユニットテストできる。

2026-07-11追記(自動継続バグ調査・実装): 自動継続(`app._inject_local_restore_check()`)は
ブラウザの localStorage に保存されたセーブコードを、Python 側に渡すために
`?local_restore=<コード>` という **URLクエリパラメータ** に載せてトップウィンドウごと
リロードする(Streamlitはサーバー型のためこれ以外に軽量な橋渡し手段がない)。
実際にプレイが進んだ状態(図鑑・会った日数・落とし物・生態ログ等)を圧縮なしで
base64化すると、長時間プレイ後には**数万文字規模**のセーブコードになりうることが
判明した(実測: discovered=全37種+mementos全カタログ+eco_log多数などを想定した
サンプルで約54,000文字)。これは一般的なリバースプロキシ/Webサーバーの
URL・ヘッダ長上限(多くは8KB前後)を大きく超え、Android実機(Capacitor版、
`server.url`でRender.com上のURLを直接ロード)で「自動継続がうまく動いていない」と
いう報告の実体である可能性が高い(URLが長すぎてサーバー側でリクエスト自体が
拒否される、またはブラウザ側の実装差でリロードが失敗する)。
手動の「セーブコードを貼り付けて再開」はURLを経由しない(通常のStreamlitウィジェット
経由)ため、この上限の影響を受けない。「自動継続だけ」が壊れて見えるという報告の
症状と整合する。

対策として、`encode_save`/`decode_save` の内部表現に **zlib 圧縮** を挟んだ
(JSON→zlib圧縮→base64、の順)。テキストデータ(日本語の理由文・日付・キー名の
繰り返し)は圧縮率が高く、上記の約54,000文字のサンプルは圧縮後 約3,300文字まで
縮む(実測、約1/16)。セーブコードは元々「人が読んで編集する」形式ではなく
不透明な文字列として貼り付けるだけの運用のため、圧縮を挟んでも既存の使い勝手
(コピー&ペースト)には影響しない。

後方互換性: 圧縮前に書き出された(=zlib圧縮されていない生のJSON)旧セーブコードも
引き続き読み込めるよう、`decode_save` はまず伸長を試み、失敗したら「圧縮されて
いない生のJSON」として扱うフォールバックを行う(壊さない方針)。
"""
from __future__ import annotations

import base64
import json
import zlib
from datetime import datetime

# セーブコードのフォーマットバージョン。将来キー構成を変えるときはこれを上げ、
# 旧バージョンのコードは decode_save が None を返して静かに拒否する。
SAVE_FORMAT_VERSION = 1

# セット型(JSON非対応)で保存されるキー。保存時は sorted list に変換し、
# 復元時に再び set() へ戻す。
SET_KEYS = ("residents", "discovered", "mementos_set")

# セーブコードに含めることを許可するキー。ここにないキーは
# encode_save で無視され、decode_save でも無視される(将来の混入対策)。
SAVE_KEYS = (
    "biome",
    "planted",
    "planted_at_map",
    "residents",
    "discovered",
    "bird_days",
    "mementos",
    "mementos_set",
    "bird_notes",
    "observed",
    # 生態ログ(「なぜ来たか」の蓄積・重複除去、eco_log.py)。撹乱で植物が
    # 失われても消さない記録なので、ローカル保存でも復元できるようにする。
    "eco_log",
    "current_tester_id",
    # セーブした瞬間の時刻(ISO文字列)。復元時に「離れていた時間」を
    # 計算し、不在中ループ(absence_loop)を再現するために使う。
    "saved_at",
)


def _build_payload(state: dict) -> dict:
    """dict(通常は session_state 相当)から、セーブ対象キーだけを抜き出す。
    set 型は JSON化のため list(ソート済)に変換する。
    """
    payload = {}
    for key in SAVE_KEYS:
        if key not in state:
            continue
        value = state[key]
        if key in SET_KEYS and isinstance(value, set):
            try:
                value = sorted(value)
            except TypeError:
                value = list(value)
        payload[key] = value
    return payload


def _restore_payload(data: dict) -> dict:
    """decode 済みの dict を、そのまま session_state に代入できる形に戻す
    (set 型キーを list -> set に戻す)。未知キーは呼び出し側で既に除去済みの前提。
    """
    restored = dict(data)
    for key in SET_KEYS:
        if key in restored and not isinstance(restored[key], set):
            try:
                restored[key] = set(restored[key])
            except TypeError:
                restored[key] = set()
    return restored


def encode_save(state: dict) -> str:
    """進行データ(dict)をセーブコード(1本の文字列)にエンコードする。

    Args:
        state: session_state 相当の dict。SAVE_KEYS に含まれるキーだけが保存される。

    Returns:
        base64(urlsafe) 文字列。サーバーには送らず、ユーザーが手元で保管する想定。
        内部では zlib 圧縮してから base64化する(自動継続のURL長対策、
        モジュールdocstring参照)。
    """
    payload = _build_payload(state or {})
    envelope = {"v": SAVE_FORMAT_VERSION, "data": payload}
    raw = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, 9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def decode_save(code: str) -> dict | None:
    """セーブコードを復元する。

    壊れたコード・不正な JSON・バージョン不一致・想定外の型は、例外を投げず
    None を返す(sheets_client.py の「失敗時にも例外を投げない」流儀を踏襲)。
    未知キーが混ざっていても、既知キー(SAVE_KEYS)だけを通して安全に無視する。

    Returns:
        dict: 復元されたデータ(set 型キーは list -> set に戻し済み)。
        None: 読み込みに失敗した場合。
    """
    if not code or not isinstance(code, str):
        return None
    try:
        decoded = base64.urlsafe_b64decode(code.strip().encode("ascii"))
    except Exception:
        return None

    # 新形式(zlib圧縮済み)を優先して伸長を試み、失敗したら旧形式
    # (圧縮なしの生JSON、2026-07-11のこの変更より前に書き出されたコード)として
    # 扱う。壊れたコードは例外を投げず None を返す方針は変えない。
    try:
        raw = zlib.decompress(decoded)
    except Exception:
        raw = decoded

    try:
        envelope = json.loads(raw.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(envelope, dict):
        return None
    if envelope.get("v") != SAVE_FORMAT_VERSION:
        return None

    data = envelope.get("data")
    if not isinstance(data, dict):
        return None

    # 未知キーは無視して既知キーだけ通す(将来のフォーマット変更・改ざんへの安全弁)
    cleaned = {k: v for k, v in data.items() if k in SAVE_KEYS}
    return _restore_payload(cleaned)


def build_current_snapshot(state: dict, now: datetime | None = None) -> dict:
    """session_state 相当の dict から、現在時刻(saved_at)付きのスナップショットを作る。

    サイドバーの「セーブコードを書き出す」(手動バックアップ)と、自動保存
    (`app._inject_local_save_write()`、ブラウザの localStorage への書き込み)の
    両方が同じロジックを使うための共通ヘルパー(ロジックの重複を避ける)。
    """
    snapshot = {k: state.get(k) for k in SAVE_KEYS if k in state}
    snapshot["saved_at"] = (now or datetime.now()).isoformat(timespec="seconds")
    return snapshot


def encode_current_state(state: dict, now: datetime | None = None) -> str:
    """`build_current_snapshot` + `encode_save` をまとめた便利関数。"""
    return encode_save(build_current_snapshot(state, now))
