"""
Toris Collection - Freesound クライアント (森の環境音)

Freesound API を使って森の環境音(ループ可能なアンビエント)をキャッシュする。
プロジェクト直下に freesound_api_key.txt があれば API を使用、なければ無効化。

【APIキーの取り方】
  1. https://freesound.org/apiv2/apply で登録(無料)
  2. Client credentials の「Client secret / API key」をコピー
  3. freesound_api_key.txt にキーだけ1行で保存
  4. アプリ再起動
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

FS_API_BASE = "https://freesound.org/apiv2"
KEY_FILE = Path(__file__).parent / "freesound_api_key.txt"
CACHE_DIR = Path(__file__).parent / ".freesound_cache"

_MAX_B64_BYTES = 700_000  # base64 上限 ≈ 525KB MP3: 約35秒@128kbps


def _load_key() -> Optional[str]:
    if KEY_FILE.exists():
        try:
            k = KEY_FILE.read_text(encoding="utf-8").strip().lstrip("﻿")
            if k:
                return k
        except Exception:
            pass
    return None


_KEY = _load_key()


def is_enabled() -> bool:
    return _KEY is not None


if is_enabled():
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"[freesound] APIキー読み込み済み(末尾4文字: ...{_KEY[-4:]})")
else:
    print(f"[freesound] APIキー未設定。環境音はシンセ合成にフォールバックします。"
          f"有効化するには {KEY_FILE.name} にキーを保存してください。")


def _api_get(path: str, params: dict) -> Optional[dict]:
    """Freesound API の GET リクエスト。JSON を返す。"""
    params["token"] = _KEY
    url = f"{FS_API_BASE}{path}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TorisCollection/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[freesound] HTTP {e.code}: {path}")
    except Exception as e:
        print(f"[freesound] {type(e).__name__}: {e}")
    return None


def get_ambient_path(query: str = "forest morning birds ambient loop",
                     min_dur: int = 25,
                     max_dur: int = 75) -> Optional[Path]:
    """
    森の環境音 MP3 をキャッシュして返す。
    - CC0 ライセンスを優先して検索
    - Freesound の HQ プレビュー(128kbps)を取得・キャッシュ
    - ファイルサイズが _MAX_B64_BYTES を超えそうなら後回し
    """
    if not is_enabled():
        return None

    cache_path = CACHE_DIR / "forest_ambient.mp3"
    if cache_path.exists() and cache_path.stat().st_size > 30_000:
        return cache_path

    data = _api_get("/search/text/", {
        "query": query,
        "fields": "id,name,previews,duration,license",
        "filter": f'duration:[{min_dur} TO {max_dur}] license:"Creative Commons 0"',
        "sort": "rating_desc",
        "page_size": 8,
    })
    if not data:
        return None

    results = data.get("results", [])
    if not results:
        # CC0 が見つからなければ Attribution も試す
        data2 = _api_get("/search/text/", {
            "query": query,
            "fields": "id,name,previews,duration,license",
            "filter": f"duration:[{min_dur} TO {max_dur}]",
            "sort": "rating_desc",
            "page_size": 8,
        })
        results = (data2 or {}).get("results", [])

    for r in results:
        preview_url = (r.get("previews") or {}).get("preview-hq-mp3")
        if not preview_url:
            continue
        try:
            req = urllib.request.Request(
                preview_url, headers={"User-Agent": "TorisCollection/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
            # 小さすぎる・大きすぎるファイルはスキップ
            if len(content) < 30_000:
                continue
            if len(content) * 4 // 3 > _MAX_B64_BYTES:
                print(f"[freesound] '{r['name']}' はサイズ超過({len(content)//1024}KB)→スキップ")
                continue
            cache_path.write_bytes(content)
            license_short = r.get("license", "")[:40]
            print(f"[freesound] ambient cached: '{r['name']}' "
                  f"({len(content)//1024}KB, {license_short})")
            return cache_path
        except Exception as e:
            print(f"[freesound] DL失敗 '{r.get('name', '?')}': {e}")
            continue

    print("[freesound] 適切な環境音が見つかりませんでした")
    return None


def clear_cache() -> None:
    """キャッシュをクリアして次回起動時に再取得させる。"""
    if (CACHE_DIR / "forest_ambient.mp3").exists():
        (CACHE_DIR / "forest_ambient.mp3").unlink()
