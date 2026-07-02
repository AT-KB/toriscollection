"""
Toris Collection - xeno-canto クライアント (キー必須版)

xeno-canto API は2024以降、無認証アクセス不可。
APIキーが見つかれば API を使用、なければ静かに無効化。

キーの解決順(sheets_client と同じ方針):
  1. Streamlit Cloud secrets … st.secrets["xc_api_key"]
  2. 環境変数 … XC_API_KEY
  3. ローカルファイル … xc_api_key.txt(プロジェクト直下)

【APIキーの取り方】
  1. https://xeno-canto.org/account/register で登録(無料)
  2. https://xeno-canto.org/account/api-key からキーを取得
  3. 次のいずれかで設定:
       - ローカル開発     : xc_api_key.txt にキーだけ1行で保存
       - 環境変数         : XC_API_KEY=<キー>
       - Streamlit Cloud  : secrets に  xc_api_key = "<キー>"  を追加
  4. アプリ再起動
"""
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


XC_API_BASE = "https://xeno-canto.org/api/3/recordings"
KEY_FILE = Path(__file__).parent / "xc_api_key.txt"


def _load_api_key() -> Optional[str]:
    # 1. Streamlit Cloud secrets を優先(Cloud ではキーファイルを置けないため)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "xc_api_key" in st.secrets:
            key = str(st.secrets["xc_api_key"]).strip()
            if key:
                return key
    except Exception:
        pass
    # 2. 環境変数
    env_key = (os.environ.get("XC_API_KEY") or "").strip()
    if env_key:
        return env_key
    # 3. ローカルファイル
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


# ── 商用ライセンス・モード ──────────────────────────────────────────
# 広告つき=商用アプリでは、CC BY-NC(非商用)録音は使えない。
# COMMERCIAL_ONLY=True のとき、鳴き声は商用可(CC0 / CC BY / BY-SA / BY-ND /
# パブリックドメイン)の録音だけに絞る。まずは監査(license_audit.py)で
# 影響範囲を見てから有効化する想定で、既定は False。
# secrets の commercial_only / 環境変数 XC_COMMERCIAL_ONLY でも切り替え可。
def _load_commercial_only() -> bool:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "commercial_only" in st.secrets:
            return bool(st.secrets["commercial_only"])
    except Exception:
        pass
    return os.environ.get("XC_COMMERCIAL_ONLY", "").strip().lower() in ("1", "true", "yes")


COMMERCIAL_ONLY = _load_commercial_only()


def license_class(lic: str) -> str:
    """録音のライセンス文字列を分類する。

    Returns "commercial"(商用可) / "noncommercial"(NC=不可) / "unknown"。
    xeno-canto の 'lic' は "//creativecommons.org/licenses/by-nc-sa/4.0/" のような値。
    """
    if not lic:
        return "unknown"
    s = str(lic).lower()
    if "-nc" in s or "/nc" in s:      # by-nc, by-nc-sa, by-nc-nd など
        return "noncommercial"
    if ("creativecommons" in s or "publicdomain" in s or "zero" in s
            or "/by" in s):           # by, by-sa, by-nd, cc0
        return "commercial"
    return "unknown"


def _license_ok(rec: dict) -> bool:
    """COMMERCIAL_ONLY のとき、この録音を使ってよいか。"""
    if not COMMERCIAL_ONLY:
        return True
    lic = rec.get("lic") or rec.get("license") or ""
    return license_class(lic) == "commercial"


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
                if not _license_ok(r):
                    continue
                url = r.get("file")
                if url and url.startswith(("http://", "https://")):
                    return url
    return None


def get_audio_urls(scientific_name: str, max_n: int = 3) -> list[tuple[str, str]]:
    """同一種の異なる録音を最大 max_n 件、(url, 鳴き方) のタプルで返す。
    鳴き方は "song"(さえずり) / "call"(地鳴き)。品質はA優先で交互に混ぜる。
    「1羽がいろんな鳴き方をする」のバリエーション用。
    """
    if not is_enabled():
        return []

    def _collect(sound_type: str) -> list[str]:
        urls = []
        for q in ["A", "B"]:
            for r in search_recordings(scientific_name, quality=q,
                                       sound_type=sound_type):
                if not _license_ok(r):
                    continue
                url = r.get("file")
                if url and url.startswith(("http://", "https://")):
                    urls.append(url)
            if len(urls) >= max_n:
                break
        return urls

    songs = _collect("song")
    calls = _collect("call")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    # song → call → song → call … の順で重複なく混ぜる
    for s, c in zip(songs, calls):
        for url, t in ((s, "song"), (c, "call")):
            if url not in seen:
                seen.add(url)
                out.append((url, t))
    for url, t in ([(u, "song") for u in songs] + [(u, "call") for u in calls]):
        if url not in seen:
            seen.add(url)
            out.append((url, t))
    return out[:max_n]


def download_audio_variants(scientific_name: str,
                            max_n: int = 3) -> list[tuple[Path, str]]:
    """同一種の録音を最大 max_n 件ダウンロードし (Path, 鳴き方) のリストを返す。
    1件目は download_audio() と同じキャッシュファイルを共有する。
    """
    if not is_enabled():
        return []
    safe_name = _safe_filename(scientific_name)
    urls = get_audio_urls(scientific_name, max_n=max_n)

    paths: list[tuple[Path, str]] = []
    first = download_audio(scientific_name)
    if first:
        # 既存キャッシュの1件目: 取得順は song 優先なので先頭のラベルを流用
        first_type = urls[0][1] if urls else "song"
        paths.append((first, first_type))
    if max_n <= 1:
        return paths

    for i, (url, sound_type) in enumerate(urls[1:], start=1):
        vp = AUDIO_DIR / f"{safe_name}_v{i}.mp3"
        if vp.exists() and vp.stat().st_size > 1000:
            paths.append((vp, sound_type))
            continue
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "TorisCollection/0.1"})
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()
            with vp.open("wb") as f:
                f.write(content)
            paths.append((vp, sound_type))
        except Exception as e:
            print(f"[xeno-canto] バリエーションDL失敗 {scientific_name} v{i}: {e}")
        if len(paths) >= max_n:
            break
    return paths


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
