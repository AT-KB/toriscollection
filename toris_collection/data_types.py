"""
data_types.py - 種データのスキーマ定義

TypedDict で定義したスキーマが、そのまま
  - Python コードの型チェック
  - Google Sheets / Excel の列仕様
  - API レスポンスの期待形
の3つを兼ねる。

【Excel / Sheets で鳥を追加する場合の列仕様】
  species_birds シート:
    id            : str  鳥の内部ID (snake_case, 例: shijukara)
    name          : str  日本語名
    scientific    : str  学名 (例: Parus minor)
    english       : str  英語名
    color         : str  16進カラーコード (例: #2a2a2a)
    biome_pref    : str  カンマ区切りのバイオームID (例: kyoto,sydney)
    rarity        : float 0.0〜1.0 (高いほどレア)
    wariness      : float 0.0〜1.0 (高いほど近づきにくい)
    description   : str  図鑑の説明文
    eats_plants   : str  カンマ区切りの植物ID (なければ空)
    eats_insects  : str  カンマ区切りの昆虫ID (なければ空)
    temp_fit_min  : int  好む気温の下限 (°C)
    temp_fit_max  : int  好む気温の上限 (°C)
    seasons       : str  出現季節のカンマ区切り spring/summer/autumn/winter
                         空 = 年中 (year-round)

  species_plants シート:
    id, name, scientific, english, icon, biome, temp_fit_min, temp_fit_max

  species_insects シート:
    id, name, scientific, english, temp_fit_min, temp_fit_max, eats_plants
"""
from __future__ import annotations
from typing import TypedDict


class BirdData(TypedDict):
    name: str
    scientific: str
    english: str
    color: str
    biome_pref: list[str]
    rarity: float
    wariness: float
    description: str
    eats_plants: list[str]
    eats_insects: list[str]
    temp_fit: tuple[int, int]


class PlantData(TypedDict):
    name: str
    scientific: str
    english: str
    icon: str
    biome: list[str]
    temp_fit: tuple[int, int]


class InsectData(TypedDict):
    name: str
    scientific: str
    english: str
    temp_fit: tuple[int, int]
    eats_plants: list[str]


class BiomeData(TypedDict):
    name: str
    lat: float
    lon: float
    temp_mean: int
    precip_mean: int
    hemisphere: str
    max_plants: int
    description: str
