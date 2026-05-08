"""
Toris Collection - xeno-canto クライアント (キー必須版)

xeno-canto API は2024以降、無認証アクセス不可。
プロジェクト直下に xc_api_key.txt があれば API を使用、なければ静かに無効化。

【APIキーの取り方】
  1. https://xeno-canto.org/account/register で登録(無料)
  2. https://xeno-canto.org/account/api-key からキーを取得
  3. xc_api_key.txt にキーだけ1行で保存
  4. アプリ再起動
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


XC_API_BASE = "https://xeno-canto.org/api/3/recordings"
KEY_FILE = Path(__file__).parent / "xc_api_key.txt"


def _load_api_key() -> Optional[str]:
    if KEY_FILE.exists():
        try:
            key = KEY_FILE.read_text(encoding="utf-8").strip().lstrip("\ufeff")
            if key:
                return key
        except Exception:
            pass
    return None


_API_KEY = _load_api_key()


def is_enabled() -> bool:
    return _API_KEY is not None


CACHE_DIR = Path(__file__).parent / ".xeno_canto_cache"
AUDIO_DIR = CACHE_DIR / "audio"
META_DIR = CACHE_DIR / "meta"
if is_enabled():
    CACHE_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)
    META_DIR.mkdir(exist_ok=True)
    print(f"[xeno-canto] APIキー読み込み済み(末尾4文字: ...{_API_KEY[-4:]})")
else:
    print(f"[xeno-canto] APIキー未設定。音声機能は無効です。"
          f"有効化するには {KEY_FILE.name} にキーを保存してください。")


def _safe_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)


def search_recordings(scientific_name: str, quality: str = "A",
                      sound_type: str = "song") -> list[dict]:
    if not is_enabled():
        return []

    cache_key = _safe_filename(f"{scientific_name}_{quality}_{sound_type}")
    meta_path = META_DIR / f"{cache_key}.json"
    if meta_path.exists():
        try:
            with meta_path.open(encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    parts = scientific_name.split()
    if len(parts) == 2:
        query = f'gen:{parts[0]} sp:{parts[1]} q:{quality} type:{sound_type} len:5-45'
    else:
        query = f'{scientific_name} q:{quality} type:{sound_type} len:5-45'

    url = f"{XC_API_BASE}?query={urllib.parse.quote(query)}&key={_API_KEY}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TorisCollection/0.1"})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[xeno-canto] HTTP {e.code} {scientific_name} q={quality} t={sound_type}")
        return []
    except Exception as e:
        print(f"[xeno-canto] {scientific_name}: {type(e).__name__}: {e}")
        return []

    recordings = raw.get("recordings", [])
    print(f"[xeno-canto] {scientific_name} q={quality} t={sound_type} → {len(recordings)}件")
    try:
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(recordings, f, ensure_ascii=False)
    except Exception:
        pass
    return recordings


def get_audio_url(scientific_name: str) -> Optional[str]:
    if not is_enabled():
        return None
    for sound_type in ["song", "call"]:
        for q in ["A", "B", "C"]:
            recs = search_recordings(scientific_name, quality=q, sound_type=sound_type)
            for r in recs:
                url = r.get("file")
                if url and url.startswith(("http://", "https://")):
                    return url
    return None


def download_audio(scientific_name: str) -> Optional[Path]:
    if not is_enabled():
        return None
    safe_name = _safe_filename(scientific_name)
    audio_path = AUDIO_DIR / f"{safe_name}.mp3"
    if audio_path.exists() and audio_path.stat().st_size > 1000:
        return audio_path
    url = get_audio_url(scientific_name)
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TorisCollection/0.1"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
        with audio_path.open("wb") as f:
            f.write(content)
        return audio_path
    except Exception as e:
        print(f"[xeno-canto] DL失敗 {scientific_name}: {e}")
        return None


def get_citation(scientific_name: str) -> Optional[dict]:
    if not is_enabled():
        return None
    for sound_type in ["song", "call"]:
        for q in ["A", "B", "C"]:
            recs = search_recordings(scientific_name, quality=q, sound_type=sound_type)
            if recs:
                r = recs[0]
                return {
                    "recordist": r.get("rec", "Unknown"),
                    "country": r.get("cnt", "Unknown"),
                    "xc_id": r.get("id", ""),
                    "url": f"https://xeno-canto.org/{r.get('id')}" if r.get("id") else "",
                }
    return None


def clear_failed_cache():
    pass


if __name__ == "__main__":
    if is_enabled():
        print(f"\nテスト: シジュウカラ録音検索")
        recs = search_recordings("Parus minor")
        print(f"取得: {len(recs)}件")
        if recs:
            r = recs[0]
            print(f"  例: XC{r.get('id')} by {r.get('rec')} ({r.get('cnt')})")
    else:
        print(f"\nAPIキーがないので動作しません。")
