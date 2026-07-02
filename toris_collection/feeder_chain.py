"""
feeder_chain.py - 餌台 → リス → Hawk →(警戒心の高い小鳥を抑制)の連鎖。

アメリカ裏庭バードウォッチングの「餌台を置き、リスや猛禽との駆け引きで
狙った鳥を呼ぶ」を、恣意ルールでなく **GloBI の相互作用**(eats / eatenBy /
preysOn)の向きだけで表現する。中心はあくまでバイオームの食物網。

  開放型の餌台(種) --eats--> リス --eatenBy--> Hawk --preysOn--> 警戒心の高い小鳥

このモジュールは純粋計算(I/O・UI 非依存)。エンジンや UI から呼べるが、
まずは単体で検証してから配線する。data の鳥/植物プールは変更しない。
"""
from __future__ import annotations

# 庭に置く餌台。large_access = 大型動物(リス)が中身に届くか。
FEEDERS = {
    "feeder_open": {"name": "開放型の餌台", "offers": "seed", "large_access": True},
    "feeder_cage": {"name": "かご型の餌台", "offers": "seed", "large_access": False},
}

# 種子・堅果を供給する植物(GloBI: これらを various な動物が eats)。
_SEED_PLANTS  = {"sunflower"}
_ACORN_PLANTS = {"white_oak"}

# 動物(GloBI: eats = 何を食べる / eaten_by = 何に食べられる)。
ANIMALS = {
    "gray_squirrel": {
        "name": "ハイイロリス", "scientific": "Sciurus carolinensis", "role": "mammal",
        "eats": ["seed", "acorn"],       # 種と堅果(GloBI eats)
        "needs_large_access": True,      # かご型の餌台からは食べられない
        "eaten_by": ["cooper_hawk"],     # GloBI eatenBy → この動物が捕食者を呼ぶ
    },
}

# 猛禽(GloBI: preysOn)。
RAPTORS = {
    "cooper_hawk": {
        "name": "クーパーハイタカ", "scientific": "Accipiter cooperii", "role": "raptor",
        "preys_on_animals": ["gray_squirrel"],  # リスを狙って庭に来る
        # 猛禽が居るときに警戒心へ効く最大係数(wariness=1 のとき到来を最大 70% 抑制)
        "suppression": 0.7,
    },
}


def available_foods(placed_features: list[str], planted_plants: list[str]) -> set[str]:
    """庭にある「動物向けの食べ物」種別と、大型アクセス可否の集合を返す。

    Returns 例: {"seed", "acorn", "large_access"}。large_access は
    大型動物が届く供給(開放餌台)が1つでもあるとき入る。
    """
    foods: set[str] = set()
    large = False
    for f in placed_features:
        meta = FEEDERS.get(f)
        if not meta:
            continue
        foods.add(meta["offers"])
        if meta["large_access"]:
            large = True
    if any(p in _SEED_PLANTS for p in planted_plants):
        foods.add("seed")
    if any(p in _ACORN_PLANTS for p in planted_plants):
        foods.add("acorn")
        large = True   # 地面の堅果は大型動物も食べられる
    if large:
        foods.add("large_access")
    return foods


def animals_present(placed_features: list[str], planted_plants: list[str]) -> list[str]:
    """庭の供給から、来る動物(リス等)の ID リストを返す。"""
    foods = available_foods(placed_features, planted_plants)
    out = []
    for aid, a in ANIMALS.items():
        if not (set(a["eats"]) & foods):
            continue
        if a.get("needs_large_access") and "large_access" not in foods:
            continue   # かご型のみ等、大型が届かない供給しか無い
        out.append(aid)
    return out


def raptors_present(animals: list[str]) -> list[str]:
    """居る動物(獲物)から、寄ってくる猛禽の ID リストを返す(eatenBy 連鎖)。"""
    out = []
    for rid, r in RAPTORS.items():
        if set(r["preys_on_animals"]) & set(animals):
            out.append(rid)
    return out


def wary_arrival_multiplier(wariness: float, raptors: list[str]) -> float:
    """猛禽が居るとき、警戒心 wariness の鳥の到来確率にかける係数(0〜1)。

    恐怖の景観(landscape of fear): 猛禽の preysOn 圧下では、臆病な種ほど来にくい。
    猛禽が居なければ 1.0(影響なし)。
    """
    if not raptors:
        return 1.0
    strength = max(RAPTORS[r]["suppression"] for r in raptors if r in RAPTORS)
    w = max(0.0, min(1.0, float(wariness)))
    return max(0.0, 1.0 - strength * w)


def resolve(placed_features: list[str], planted_plants: list[str]) -> dict:
    """庭の状態から連鎖を一括解決。UI/エンジンからはこれを呼ぶ。"""
    animals = animals_present(placed_features, planted_plants)
    raptors = raptors_present(animals)
    return {"animals": animals, "raptors": raptors}
