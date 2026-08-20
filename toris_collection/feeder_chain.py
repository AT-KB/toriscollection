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
#
# draws = **どちらの気質の鳥を強く引くか**。'bold' は警戒心の低い鳥、
# 'shy' は警戒心の高い鳥。bonus_max はその効きの上限(pp)。
#
# ## なぜ気質で分けるのか(2026-08-20 CEO承認)
# このモジュールは冒頭のとおり「餌台を置き、**リスや猛禽との駆け引き**で
# 狙った鳥を呼ぶ」ためのものだが、**代償(リス→鷹→抑制)だけが実装されて
# いて、利点が一度も配線されていなかった。** 実測すると:
#
#   開放型  空の庭 11% / 平均 1.74羽   ← 一方的に損
#   かご型  空の庭  5% / 平均 2.15羽   ← 「置かない」と1ビットも同じ
#
# 選択肢が「無意味」か「自傷」の二択で、原則2「罰しない」に触れていた。
#
# ## 量ではなく**顔ぶれ**で分ける
# 最初は加点の大小で差をつけようとしたが(開放+3/かご+2 など)、鷹が来ない
# ぶんかご型が常に勝ってしまい、「安全な方が正解」で駆け引きにならなかった。
#
# そこで**引く鳥の気質**を変えた:
#   開放型 — 開けっぴろげで食べやすい。**大胆な鳥**が寄る。
#            ただしリスが来て鷹を呼ぶので、**臆病な鳥は二重に遠のく**。
#   かご型 — 囲われていて安全。**臆病な鳥**が安心して来る。鷹も来ない。
#
# 実測(同じ庭。平均滞在数はほぼ並ぶ = どちらが得かではなく誰が来るかの差):
#   開放型 2.75羽  robin.30 / cardinal.35 / jay.35 / dove.35
#   かご型 2.78羽  finch.50 / thrasher.60 / wren.45 / waxwing.50
#   置かない 2.25羽
#
# ⚠️ 体格では分けない。`data.py` に体長・体重が無く、宣伝のために体格表を
# でっち上げるのは恣意的な指標になる(原則4。CEO 2026-08-20「今更体長の
# ラベリングは違うな」)。**wariness は元からあるデータ。**
#
# ⚠️ **到来にだけ効く。退去には効かない**(garden_items の加点と同じ扱い)。
FEEDERS = {
    "feeder_open": {"name": "開放型の餌台", "offers": "seed",
                    "large_access": True, "draws": "bold", "bonus_max": 0.20},
    "feeder_cage": {"name": "かご型の餌台", "offers": "seed",
                    "large_access": False, "draws": "shy", "bonus_max": 0.20},
}

# 気質の効きが立ち上がる下限。ここを引いてから掛けるので、逆側の気質の鳥は
# ほとんど加点されない(0.2 未満は 0)。
_LEAN_FLOOR = 0.2

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


def feeder_arrival_bonus(placed_features: list[str], bird: dict) -> float:
    """餌台が、この鳥の到来確率に足す値(pp)。

    種・実を食べる鳥(`eats_plants` が空でない)にだけ効く。虫だけを食べる鳥に
    種を撒いても意味が無いので加点しない(原則4)。
    置いていなければ 0.0 — **今までと1ビットも変わらない。**

    効き方は餌台の draws と鳥の wariness で決まる:
      開放型(bold) — 警戒心が**低い**ほど大きい
      かご型(shy)  — 警戒心が**高い**ほど大きい

    複数置いた場合はいちばん大きいものを採る(足し合わせない)。
    """
    if not placed_features:
        return 0.0
    if not (bird.get("eats_plants") or []):
        return 0.0
    # ⚠️ `or 0.5` と書いてはいけない。**警戒心 0.0 が偽と見なされて 0.5 に
    # 化ける**。Dart の `?? 0.5` は null のときだけなので、そこで食い違う
    # (2026-08-20、fixture の突き合わせで発覚)。
    raw = bird.get("wariness")
    w = 0.5 if raw is None else float(raw)
    w = max(0.0, min(1.0, w))
    best = 0.0
    for f in placed_features:
        meta = FEEDERS.get(f)
        if not meta:
            continue
        lean = (1.0 - w) if meta["draws"] == "bold" else w
        best = max(best, meta["bonus_max"] * max(0.0, lean - _LEAN_FLOOR))
    return best


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
