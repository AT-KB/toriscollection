"""
species_loader.py - 種データのロード窓口

すべてのモジュールはここから BIRDS / PLANTS / INSECTS / BIOMES をインポートする。
data.py は直接インポートしない。

【ロードの優先順位】
  1. Google Sheets の species_birds / species_plants / species_insects シート
     → シートが存在し、行が1件以上あればこちらを使う
     → Excel で編集して Sheets に貼り付ければ次回起動時に反映される
  2. なければ data.py のシードデータにフォールバック
     → ネットワーク不可・Sheets 未設定のローカル開発でも動く

【Sheets での種の追加手順】
  1. Google Sheets の対象スプレッドシートに以下のシートを追加:
       species_birds / species_plants / species_insects
  2. data_types.py の列仕様に従いヘッダー行を書く
  3. 鳥/植物/昆虫を1行1種で追記する
  4. アプリを再起動すると新しい種が反映される
  5. シードの35種 (data.py) はシートが空の場合のフォールバックとして残る

【シードとの関係】
  - Sheets にシートが存在しない場合 → data.py のシードをそのまま使う
  - Sheets にシートが存在しデータがある場合 → Sheets のデータのみを使う
    (シードを上書きするのではなくシードを置き換える。
     シードに戻したい場合はシートを削除するかシートを空にする)
"""
from __future__ import annotations

from data_types import BirdData, PlantData, InsectData, BiomeData

# ── シードデータ(フォールバック) ──────────────────────────────────
from data import (
    BIRDS as _SEED_BIRDS,
    PLANTS as _SEED_PLANTS,
    INSECTS as _SEED_INSECTS,
    BIOMES as _SEED_BIOMES,
    BIOME_MIGRATION,
    SEASON_TEMP_OFFSET,
)


# ── Sheets ローダー ────────────────────────────────────────────────

def _csv_field(value: str | None) -> list[str]:
    """カンマ区切り文字列 → list。空文字・None は空リストに。"""
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _load_birds_from_sheets() -> dict[str, BirdData] | None:
    """
    Google Sheets の species_birds シートから鳥データをロード。
    シートが存在しない・データが0行・エラーのいずれかで None を返す。
    """
    try:
        import sheets_client as sc
        ss = sc.get_spreadsheet()
        try:
            ws = ss.worksheet("species_birds")
        except Exception:
            return None

        rows = ws.get_all_records()
        if not rows:
            return None

        birds: dict[str, BirdData] = {}
        for row in rows:
            bid = str(row.get("id", "")).strip()
            if not bid:
                continue
            try:
                tmin = int(row.get("temp_fit_min", 0))
                tmax = int(row.get("temp_fit_max", 30))
                birds[bid] = BirdData(
                    name=str(row.get("name", bid)),
                    scientific=str(row.get("scientific", "")),
                    english=str(row.get("english", "")),
                    color=str(row.get("color", "#888888")),
                    biome_pref=_csv_field(row.get("biome_pref")),
                    rarity=float(row.get("rarity", 0.5)),
                    wariness=float(row.get("wariness", 0.5)),
                    description=str(row.get("description", "")),
                    eats_plants=_csv_field(row.get("eats_plants")),
                    eats_insects=_csv_field(row.get("eats_insects")),
                    temp_fit=(tmin, tmax),
                )
            except Exception as e:
                print(f"[species_loader] birds row '{bid}' skip: {e}")
        return birds if birds else None
    except Exception:
        return None


def _load_plants_from_sheets() -> dict[str, PlantData] | None:
    try:
        import sheets_client as sc
        ss = sc.get_spreadsheet()
        try:
            ws = ss.worksheet("species_plants")
        except Exception:
            return None

        rows = ws.get_all_records()
        if not rows:
            return None

        plants: dict[str, PlantData] = {}
        for row in rows:
            pid = str(row.get("id", "")).strip()
            if not pid:
                continue
            try:
                tmin = int(row.get("temp_fit_min", 0))
                tmax = int(row.get("temp_fit_max", 30))
                plant: PlantData = PlantData(
                    name=str(row.get("name", pid)),
                    scientific=str(row.get("scientific", "")),
                    english=str(row.get("english", "")),
                    icon=str(row.get("icon", "🌿")),
                    biome=_csv_field(row.get("biome")),
                    temp_fit=(tmin, tmax),
                )
                # 撹乱・遷移の形質(任意列。空なら入れず disturbance.py の既定に委ねる)
                _sens = row.get("disturbance_sensitivity")
                if _sens not in (None, ""):
                    plant["disturbance_sensitivity"] = float(_sens)
                _role = str(row.get("successional_role", "")).strip()
                if _role:
                    plant["successional_role"] = _role
                plants[pid] = plant
            except Exception as e:
                print(f"[species_loader] plants row '{pid}' skip: {e}")
        return plants if plants else None
    except Exception:
        return None


def _load_insects_from_sheets() -> dict[str, InsectData] | None:
    try:
        import sheets_client as sc
        ss = sc.get_spreadsheet()
        try:
            ws = ss.worksheet("species_insects")
        except Exception:
            return None

        rows = ws.get_all_records()
        if not rows:
            return None

        insects: dict[str, InsectData] = {}
        for row in rows:
            iid = str(row.get("id", "")).strip()
            if not iid:
                continue
            try:
                tmin = int(row.get("temp_fit_min", 0))
                tmax = int(row.get("temp_fit_max", 30))
                insects[iid] = InsectData(
                    name=str(row.get("name", iid)),
                    scientific=str(row.get("scientific", "")),
                    english=str(row.get("english", "")),
                    temp_fit=(tmin, tmax),
                    eats_plants=_csv_field(row.get("eats_plants")),
                )
            except Exception as e:
                print(f"[species_loader] insects row '{iid}' skip: {e}")
        return insects if insects else None
    except Exception:
        return None


# ── 公開インターフェース ────────────────────────────────────────────
# 起動時に一度だけ評価される。Sheets が使えればそちら、なければシード。

def _load_all() -> tuple[dict, dict, dict, dict]:
    birds   = _load_birds_from_sheets()
    plants  = _load_plants_from_sheets()
    insects = _load_insects_from_sheets()

    if birds:
        print(f"[species_loader] Sheets から鳥データをロード: {len(birds)} 種")
    else:
        birds = dict(_SEED_BIRDS)
        print(f"[species_loader] シードデータを使用: {len(birds)} 種")

    if plants:
        print(f"[species_loader] Sheets から植物データをロード: {len(plants)} 種")
    else:
        plants = dict(_SEED_PLANTS)

    if insects:
        print(f"[species_loader] Sheets から昆虫データをロード: {len(insects)} 種")
    else:
        insects = dict(_SEED_INSECTS)

    return birds, plants, insects, dict(_SEED_BIOMES)


BIRDS:   dict[str, BirdData]
PLANTS:  dict[str, PlantData]
INSECTS: dict[str, InsectData]
BIOMES:  dict[str, BiomeData]

BIRDS, PLANTS, INSECTS, BIOMES = _load_all()

# data.py と互換のため再エクスポート
__all__ = [
    "BIRDS", "PLANTS", "INSECTS", "BIOMES",
    "BIOME_MIGRATION", "SEASON_TEMP_OFFSET",
]
