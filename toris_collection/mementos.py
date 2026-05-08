"""
Toris Collection - 落とし物(Mementos)システム

設計(最終形):
  3カテゴリ。役割を明確に差別化:
  - twig    (小枝): 各鳥固有(全26種・入門アイテム・よく出る)
  - feather (羽根): 各鳥固有(全26種・メイン収集)
  - plume   (羽冠): 一部の鳥のみ(隠しレア・特別な鳥との出会いのご褒美)

  全カタログ: 26 + 26 + ~10 = 約62種類

  確率は「入門 → 希少」に差をつける:
  - twig 10%    (やや出やすい・入門)
  - feather 5%  (中・メイン)
  - plume 1.5%  (隠しレア)
  合計約16.5%、訪問6回に1回程度の獲得頻度。
"""


# ============================================================
# 羽冠を持つ鳥(隠しアイテム対象)
# 派手な冠羽を持つ種 + レア度の高い種が落とす
# ============================================================
PLUME_BIRDS = {
    # 派手な冠羽を持つ
    "sulphur_crested_cockatoo",  # キバタン: 黄色い冠羽
    "northern_cardinal",          # ショウジョウコウカンチョウ: 赤い冠
    "pileated_woodpecker",        # エボシクマゲラ: 赤い冠
    "blue_jay",                   # アオカケス: 青い冠羽
    # レアな鳥(レア度 0.6以上)
    "kibitaki",                   # キビタキ(夏鳥)
    "kawasemi",                   # カワセミ(水場必須)
    "ikaru",                      # イカル
    "ruby_throated_hummingbird",  # ルビーノドハチドリ
    "eastern_yellow_robin",       # キバラオーストラリアコマドリ
}


# ============================================================
# 出現確率(0〜1)
# ============================================================
DROP_PROBABILITIES = {
    "twig":    0.10,
    "feather": 0.05,
    "plume":   0.015,
}

CATEGORIES = ["twig", "feather", "plume"]


# ============================================================
# Memento ID 形式
# すべて "{kind}:{bird_id}" の形式で統一
# ============================================================
def make_id(kind, bird_id):
    return f"{kind}:{bird_id}"


def feather_id(bird_id): return make_id("feather", bird_id)
def twig_id(bird_id):    return make_id("twig", bird_id)
def plume_id(bird_id):   return make_id("plume", bird_id)


def memento_category(memento_id):
    """memento_id の頭からカテゴリを判定。
    互換性のため、旧形式(seed:xxx, nut:xxx, twig_kyoto, nut_xxx)も判定できる。
    """
    if ":" in memento_id:
        return memento_id.split(":", 1)[0]
    if memento_id.startswith("twig_"):
        return "twig"
    if memento_id.startswith("nut_"):
        return "nut"  # 旧データ用(現UIには表示しない)
    return "unknown"


def memento_target(memento_id):
    """ feather:shijukara → 'shijukara' """
    if ":" in memento_id:
        return memento_id.split(":", 1)[1]
    return memento_id


# ============================================================
# 落とし物の判定: 鳥が立ち寄った時に1回呼ぶ
# ============================================================
def roll_drop(bird_id, biome_id, bird_data, planted_plants, rng):
    """
    鳥が訪問した瞬間に、何か落とすかどうかを判定する。
    最大1個まで落とす。
    レア順(plume → feather → twig)に判定し、最初に当選したものを返す。
    """
    candidates = []
    if bird_id in PLUME_BIRDS:
        candidates.append((plume_id(bird_id), DROP_PROBABILITIES["plume"]))
    candidates.append((feather_id(bird_id), DROP_PROBABILITIES["feather"]))
    candidates.append((twig_id(bird_id), DROP_PROBABILITIES["twig"]))

    for memento_id, prob in candidates:
        if rng.random() < prob:
            return memento_id
    return None


# ============================================================
# 表示用ヘルパー
# ============================================================
_CAT_META = {
    "twig": {
        "icon": "🌿",
        "label": "小枝",
        "name_template": "{bird}の止まり木の枝",
        "desc_template": "{bird} が一休みしていた小枝。",
        "tone": "brown",
    },
    "feather": {
        "icon": "🪶",
        "label": "羽根",
        "name_template": "{bird}の羽根",
        "desc_template": "{bird} ({sci}) の美しい羽根。",
        "tone": "bird",
    },
    "plume": {
        "icon": "✨",
        "label": "羽冠",
        "name_template": "{bird}の冠羽",
        "desc_template": "{bird} の特に鮮やかな羽。とても珍しい。",
        "tone": "bird_gold",
    },
}

_TONE_COLORS = {
    "brown":     "#8a6a4a",
}


def memento_display(memento_id, BIRDS, PLANTS, BIOMES):
    """落とし物の (icon, name, description, color) を返す。
    旧形式(seed:xxx, nut:xxx, twig_kyoto, nut_xxx)も互換的に表示する(過去ログ閲覧用)。
    """
    cat = memento_category(memento_id)

    # 旧形式: twig_kyoto / nut_sydney など(バイオーム名が末尾)
    if ":" not in memento_id and (
        memento_id.startswith("twig_") or memento_id.startswith("nut_")
    ):
        biome_id = memento_id.split("_", 1)[1]
        biome = BIOMES.get(biome_id, {})
        biome_name = biome.get("name", biome_id).split("(")[0]
        if cat == "twig":
            return ("🌿", f"{biome_name}の小枝(旧)", "古い形式の記録", "#8a6a4a")
        if cat == "nut":
            return ("🌰", f"{biome_name}の木の実(旧)", "古い形式の記録", "#8a5a3a")

    # 旧形式: seed:bird_id / nut:bird_id (廃止カテゴリ)
    if cat == "seed":
        bird_id = memento_target(memento_id)
        bird = BIRDS.get(bird_id)
        if bird:
            return ("🌱", f"{bird['name']}の種(旧)", "現在は廃止された形式", "#7a9a4a")
        return ("🌱", "種(旧)", "", "#7a9a4a")
    if cat == "nut":
        bird_id = memento_target(memento_id)
        bird = BIRDS.get(bird_id)
        if bird:
            return ("🌰", f"{bird['name']}の木の実(旧)", "現在は廃止された形式", "#8a5a3a")
        return ("🌰", "木の実(旧)", "", "#8a5a3a")

    # 新形式: kind:bird_id
    if cat in _CAT_META:
        meta = _CAT_META[cat]
        bird_id = memento_target(memento_id)
        bird = BIRDS.get(bird_id)
        if not bird:
            return (meta["icon"], f"未知の{meta['label']}", "", "#888")
        bird_name = bird["name"]
        sci = bird.get("scientific", "")
        bird_color = bird.get("color", "#888")
        if meta["tone"] in ("bird", "bird_gold"):
            color = bird_color
        else:
            color = _TONE_COLORS.get(meta["tone"], "#888")
        return (
            meta["icon"],
            meta["name_template"].format(bird=bird_name),
            meta["desc_template"].format(bird=bird_name, sci=sci),
            color,
        )

    return ("?", memento_id, "", "#888")


# ============================================================
# 全カタログ(コレクション画面用)
# ============================================================
def all_possible_mementos(BIRDS, PLANTS):
    """各カテゴリの全候補を [{id, category}, ...] で返す。
    twig: 全鳥固有(26)
    feather: 全鳥固有(26)
    plume: PLUME_BIRDS のみ(約9種)
    """
    out = []
    # twig: 全鳥
    for b in BIRDS:
        out.append({"id": twig_id(b), "category": "twig"})
    # feather: 全鳥
    for b in BIRDS:
        out.append({"id": feather_id(b), "category": "feather"})
    # plume: 対象鳥のみ
    for b in PLUME_BIRDS:
        if b in BIRDS:
            out.append({"id": plume_id(b), "category": "plume"})
    return out


def possible_mementos_from_bird(bird_id, BIRDS):
    """その鳥の落とし物候補。
    全鳥が twig + feather の2種、PLUME_BIRDS なら +plume の3種。
    """
    if bird_id not in BIRDS:
        return []
    out = [twig_id(bird_id), feather_id(bird_id)]
    if bird_id in PLUME_BIRDS:
        out.append(plume_id(bird_id))
    return out

