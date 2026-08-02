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

【シードとの関係(オール・オア・ナッシング)】
  - 起動時、species_birds / species_plants / species_insects の3枚を並列取得する。
  - **3枚すべてが取得できたときだけ** Sheets のデータを採用する
    (シードを上書きするのではなくシードを置き換える)。
  - **1枚でも欠けた場合(未作成・空・タイムアウト・エラー)は、混在を避けるため
    3種すべてをシードにフォールバックする**。これは「新しい鳥(Sheets)+古い植物/昆虫
    (シード)」のような非整合な生態系(食物経路が繋がらず鳥が来にくい)を防ぐため。
    一部だけ成功した場合は警告ログを出す。
  - シードに戻したい場合はシートを削除するかシートを空にする。

【起動時のロード手順(_load_all)】
  1. プリウォーム: 認証+spreadsheetオープンを一度だけ直列で温める(authorizeの多重化=
     429リスクを回避)。sheets_client 側の Lock と合わせて1回に収める。
  2. ファンアウト: 温め後、3枚のワークシート読み出しだけを並列取得する。
  3. 合計待ち時間に上限(既定6秒, 環境変数 SPECIES_SHEETS_TIMEOUT)。超過分はシードへ。
"""
from __future__ import annotations

import os
import time

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
                bird = BirdData(
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
                # 群れサイズの形質(任意列。空なら入れず flock.py の rarity 推定に委ねる)
                _fmax = row.get("flock_max")
                if _fmax not in (None, ""):
                    bird["flock_max"] = int(_fmax)
                # 英語の説明文(任意列。列が無い/空なら入れず、表示側で description に
                # フォールバックする。既存シートには列が無いため absent-safe に読む)
                _den = str(row.get("description_en", "")).strip()
                if _den:
                    bird["description_en"] = _den
                birds[bid] = bird
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
    # 起動高速化(2026-08-01): 従来は Sheets を鳥→植物→昆虫の順に**直列**取得しており、
    # プロセス起動のたびに 3 回のネットワーク往復が積み上がっていた(コールド起動が重い一因)。
    #
    # 構成(2026-08-02 改修):
    #   1. プリウォーム: 認証(authorize)+ spreadsheet オープン(open_by_key)を
    #      **一度だけ直列**で温める。従来はファンアウトした 3 スレッドが各々これを
    #      走らせうる遅延初期化で、起動直後に authorize が最大 3 重化(429リスク・
    #      並列化の効果を相殺)していた。sheets_client 側の Lock と合わせて 1 回に収める。
    #   2. ファンアウト: 温め後、**3 枚のワークシート読み出しだけ**を並列取得する。
    #   3. 合計待ち時間に**上限(既定6秒)**。超過分はシードにフォールバックし起動を止めない。
    #      上限は環境変数 SPECIES_SHEETS_TIMEOUT で調整可(0 で Sheets を完全スキップ)。
    #   4. オール・オア・ナッシング: 3 枚すべて成功したときだけ Sheets を採用する。
    #      1 枚でも欠けたら「新しい鳥(Sheets)+古い植物/昆虫(シード)」のような
    #      非整合な生態系(食物経路が繋がらず鳥が来にくい)を避けるため、全体をシードへ。
    t0 = time.time()
    birds = plants = insects = None
    try:
        deadline_s = float(os.environ.get("SPECIES_SHEETS_TIMEOUT", "6"))
    except (TypeError, ValueError):
        deadline_s = 6.0

    if deadline_s > 0:
        from concurrent.futures import ThreadPoolExecutor
        end = time.time() + deadline_s
        # with を使うと __exit__ が全スレッド完了まで待つ(=タイムアウトが無意味になる)ため、
        # 明示的に生成し、最後に wait=False で切り離す(遅い Sheets 呼び出しは裏で終わり破棄)。
        ex = ThreadPoolExecutor(max_workers=3)
        try:
            # --- プリウォーム(認証+spreadsheet オープンを一度だけ) ---
            # 認証がハングしても残り予算(deadline)を超えないよう、ワーカーで実行して
            # タイムアウト付きで待つ。温まらなければ Sheets は諦めてシードへ。
            def _prewarm():
                import sheets_client
                sheets_client.get_spreadsheet()
                return True

            warmed = False
            try:
                fw = ex.submit(_prewarm)
                warmed = bool(fw.result(timeout=max(0.0, end - time.time())))
            except Exception:
                warmed = False

            if warmed:
                # --- ファンアウト: 3 枚のワークシート読みだけを並列化 ---
                fb = ex.submit(_load_birds_from_sheets)
                fp = ex.submit(_load_plants_from_sheets)
                fi = ex.submit(_load_insects_from_sheets)

                def _get(fut):
                    remaining = end - time.time()
                    if remaining <= 0:
                        return None
                    try:
                        return fut.result(timeout=remaining)
                    except Exception:
                        return None

                birds = _get(fb)
                plants = _get(fp)
                insects = _get(fi)
        finally:
            ex.shutdown(wait=False)

    # --- オール・オア・ナッシング判定 ---
    if birds and plants and insects:
        print(f"[species_loader] Sheets から鳥データをロード: {len(birds)} 種")
        print(f"[species_loader] Sheets から植物データをロード: {len(plants)} 種")
        print(f"[species_loader] Sheets から昆虫データをロード: {len(insects)} 種")
    else:
        if birds or plants or insects:
            # 一部だけ成功 = 混在しかけた。警告して全体をシードへ揃える。
            print(
                "[species_loader] 警告: Sheets が3枚揃わず "
                f"(birds={bool(birds)} plants={bool(plants)} insects={bool(insects)})、"
                "生態系の混在を避けるため全体をシードにフォールバック"
            )
        birds = dict(_SEED_BIRDS)
        plants = dict(_SEED_PLANTS)
        insects = dict(_SEED_INSECTS)
        print(f"[species_loader] シードデータを使用: {len(birds)} 種")

    # 起動コストの可視化: Render のログでこの秒数を見れば、Sheets 取得が起動を
    # どれだけ食っているかが一目で分かる(上限は SPECIES_SHEETS_TIMEOUT)。
    print(f"[species_loader] _load_all 完了: {time.time() - t0:.2f}s (上限 {deadline_s:.0f}s)")
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
