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
    biome_pref    : str  カンマ区切りのバイオームID (例: kyoto,charlotte)
    rarity        : float 0.0〜1.0 (高いほどレア)
    wariness      : float 0.0〜1.0 (高いほど近づきにくい)
    description   : str  図鑑の説明文(日本語)
    description_en: str  図鑑の説明文(英語・任意。無ければ description にフォールバック)
    eats_plants   : str  カンマ区切りの植物ID (なければ空)
    eats_insects  : str  カンマ区切りの昆虫ID (なければ空)
    temp_fit_min  : int  好む気温の下限 (°C)
    temp_fit_max  : int  好む気温の上限 (°C)
    seasons       : str  出現季節のカンマ区切り spring/summer/autumn/winter
                         空 = 年中 (year-round)
    flock_max     : int  群れの最大サイズ 1〜3 (任意・未設定は rarity から推定)
                         1=単独 / 3=群れやすい。ラジオで同種が複数で鳴く厚みになる

  species_plants シート:
    id, name, scientific, english, icon, biome, temp_fit_min, temp_fit_max
    disturbance_sensitivity : float 0.0〜1.0 撹乱で倒れやすさ(任意・既定0.5)
    successional_role       : str  'pioneer'(跡地に芽吹く) / 'late'(極相種)
                                   任意・未設定はパイオニア候補として扱う

  species_insects シート:
    id, name, scientific, english, temp_fit_min, temp_fit_max, eats_plants
"""
from __future__ import annotations
from typing import TypedDict, NotRequired


class BirdData(TypedDict):
    name: str
    scientific: str
    english: str
    color: str
    biome_pref: list[str]
    rarity: float
    wariness: float
    description: str
    # 図鑑の説明文(英語)。任意。i18n.describe() が無ければ description にフォールバック。
    description_en: NotRequired[str]
    eats_plants: list[str]
    eats_insects: list[str]
    temp_fit: tuple[int, int]
    # 群れの最大サイズ(任意。未設定は flock.py が rarity から推定)
    flock_max: NotRequired[int]


class PlantData(TypedDict, total=False):
    name: str
    scientific: str
    english: str
    icon: str
    biome: list[str]
    temp_fit: tuple[int, int]
    # 撹乱・遷移の形質(任意。未設定なら disturbance.py の既定値を使う)
    disturbance_sensitivity: float          # 0..1 倒れやすさ
    successional_role: str                  # 'pioneer' / 'late'


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
    # 説明文(英語)。任意。i18n.describe() が無ければ description にフォールバック。
    description_en: NotRequired[str]
