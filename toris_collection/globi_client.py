"""
Toris Collection - GloBI APIクライアント

GloBI (Global Biotic Interactions) から種間相互作用を取得する。
https://api.globalbioticinteractions.org/

主要なエンドポイント:
  /interaction?sourceTaxon=X&interactionType=Y&field=...

主要な interactionType:
  eats, preysOn, pollinates, hasHost, parasiteOf, visits, visitsFlowersOf, etc.
  完全なリスト: /interactionTypes

実運用では SQLite/Parquet でディスクキャッシュするが、
プロトタイプでは JSON ファイルでキャッシュする。
"""
from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


GLOBI_API_BASE = "https://api.globalbioticinteractions.org"

# インメモリキャッシュ
_CACHE: dict[tuple, list[dict]] = {}

# ディスクキャッシュ(JSON形式、学名別)
CACHE_DIR = Path(__file__).parent / ".globi_cache"
CACHE_DIR.mkdir(exist_ok=True)

# 日本周辺のbbox (west, south, east, north)
JAPAN_BBOX = (122.0, 24.0, 146.0, 46.0)


def _build_url(source_taxon: str, interaction_type: Optional[str] = None,
               target_taxon: Optional[str] = None, bbox: Optional[tuple] = None,
               limit: int = 100) -> str:
    """GloBI APIのURLを組み立てる"""
    params = [
        ("sourceTaxon", source_taxon),
        ("field", "source_taxon_name"),
        ("field", "source_taxon_path"),
        ("field", "interaction_type"),
        ("field", "target_taxon_name"),
        ("field", "target_taxon_path"),
        ("limit", str(limit)),
        ("type", "json"),
    ]
    if interaction_type:
        params.append(("interactionType", interaction_type))
    if target_taxon:
        params.append(("targetTaxon", target_taxon))
    if bbox:
        # bbox = (west, south, east, north)
        params.append(("bbox", ",".join(str(x) for x in bbox)))

    query = urllib.parse.urlencode(params)
    return f"{GLOBI_API_BASE}/interaction?{query}"


def _cache_path(cache_key: tuple) -> Path:
    """キャッシュキーからファイルパスを生成"""
    # tuple を文字列に
    key_str = "_".join(str(x) if x is not None else "_" for x in cache_key)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key_str)
    return CACHE_DIR / f"{safe[:150]}.json"


def _load_disk_cache(cache_key: tuple) -> Optional[list[dict]]:
    path = _cache_path(cache_key)
    if path.exists():
        try:
            with path.open() as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _save_disk_cache(cache_key: tuple, data: list[dict]) -> None:
    path = _cache_path(cache_key)
    try:
        with path.open("w") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"[GloBI] キャッシュ保存失敗: {e}")


def _fetch_json(url: str, timeout: int = 20) -> dict:
    """HTTPで取得してJSONにデコード"""
    req = urllib.request.Request(url, headers={"User-Agent": "TorisCollection/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_interactions(source_taxon: str, interaction_type: Optional[str] = None,
                     target_taxon: Optional[str] = None, bbox: Optional[tuple] = None,
                     limit: int = 100, use_cache: bool = True) -> list[dict]:
    """
    ある分類群を起点に、相互作用を取得する。

    Args:
      source_taxon: 学名 (例: "Parus minor", "Aves")
      interaction_type: 相互作用タイプ (例: "eats", "preysOn", "pollinates")
      target_taxon: 相手の分類群で絞り込み
      bbox: (west, south, east, north)
      limit: 取得上限

    Returns:
      辞書のリスト。各辞書は source_taxon_name, interaction_type, target_taxon_name を含む
    """
    cache_key = (source_taxon, interaction_type, target_taxon, bbox, limit)

    # 1) インメモリキャッシュ
    if use_cache and cache_key in _CACHE:
        return _CACHE[cache_key]

    # 2) ディスクキャッシュ
    if use_cache:
        disk = _load_disk_cache(cache_key)
        if disk is not None:
            _CACHE[cache_key] = disk
            return disk

    # 3) API呼び出し
    url = _build_url(source_taxon, interaction_type, target_taxon, bbox, limit)

    try:
        raw = _fetch_json(url)
    except urllib.error.HTTPError as e:
        print(f"[GloBI] HTTP {e.code} for {source_taxon}/{interaction_type}")
        print(f"        URL: {url}")
        return []
    except Exception as e:
        print(f"[GloBI] {type(e).__name__}: {e} -- {source_taxon}/{interaction_type}")
        print(f"        URL: {url}")
        return []

    columns = raw.get("columns", [])
    data = raw.get("data", [])
    results = [dict(zip(columns, row)) for row in data]
    print(f"[GloBI] OK {source_taxon}/{interaction_type} → {len(results)} 件")

    if use_cache:
        _CACHE[cache_key] = results
        _save_disk_cache(cache_key, results)

    return results


def get_diet(bird_scientific_name: str, bbox: Optional[tuple] = None) -> list[str]:
    """
    ある鳥が食べるものの学名リストを取得する。
    interactionType=eats と preysOn の両方を合算する。
    """
    diet: set[str] = set()
    for itype in ("eats", "preysOn"):
        for rec in get_interactions(bird_scientific_name, itype, bbox=bbox):
            target = rec.get("target_taxon_name")
            if target:
                diet.add(target)
    return sorted(diet)


def get_diet_japan(bird_scientific_name: str) -> list[str]:
    """日本周辺(JAPAN_BBOX)に限定した diet"""
    return get_diet(bird_scientific_name, bbox=JAPAN_BBOX)


# ==========================================
# シードデータ検証ユーティリティ
# ==========================================

def enrich_seed_with_globi(birds_seed: dict, verbose: bool = False) -> dict:
    """
    シードの鳥データそれぞれについて GloBI に問い合わせ、
    発見された diet を付加した拡張データを返す。

    返り値: {bird_id: {"name": ..., "scientific": ..., "globi_diet": [...]}}

    注意: 起動時に全鳥問い合わせると遅いので、通常は初回のみ実行して
    ディスクキャッシュに保存する形で運用する。
    """
    result = {}
    for b_id, bird in birds_seed.items():
        sci = bird.get("scientific")
        if not sci:
            continue
        if verbose:
            print(f"[GloBI] querying: {bird['name']} ({sci})")
        diet = get_diet(sci)
        result[b_id] = {
            "name": bird["name"],
            "scientific": sci,
            "globi_diet_count": len(diet),
            "globi_diet_sample": diet[:20],
        }
        # レート制限対策で少し待つ
        time.sleep(0.5)
    return result


def compare_with_seed(bird_id: str, birds_seed: dict) -> dict:
    """単一の鳥について、シードとGloBIの diet を比較"""
    bird = birds_seed.get(bird_id)
    if not bird:
        return {"error": f"bird {bird_id} not in seed"}
    sci_name = bird.get("scientific")
    if not sci_name:
        return {"error": f"no scientific name for {bird_id}"}

    globi_diet = get_diet(sci_name)
    return {
        "bird": bird["name"],
        "scientific": sci_name,
        "globi_diet_count": len(globi_diet),
        "globi_diet_sample": globi_diet[:30],
    }


if __name__ == "__main__":
    # 動作確認: シジュウカラの相互作用を GloBI に聞く
    print("=" * 60)
    print("シジュウカラ (Parus minor) の GloBI 相互作用を取得")
    print("=" * 60)
    print("※ サンドボックス環境ではネットワーク制限で失敗することがあります。")
    print("  ローカル環境では globalbioticinteractions.org への接続が必要です。\n")

    diet = get_diet("Parus minor")
    if diet:
        print(f"取得件数: {len(diet)}")
        for t in diet[:15]:
            print(f"  - {t}")
    else:
        print("取得できませんでした(ネットワーク不可 or データなし)")

    print("\n" + "=" * 60)
    print("オオルリ (Cyanoptila cyanomelana) の diet")
    print("=" * 60)
    diet = get_diet("Cyanoptila cyanomelana")
    if diet:
        print(f"取得件数: {len(diet)}")
        for t in diet[:15]:
            print(f"  - {t}")
    else:
        print("取得できませんでした")
