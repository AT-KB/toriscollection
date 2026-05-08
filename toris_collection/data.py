"""
Toris Collection - 種と相互作用のシードデータ (v3)
変更点 (v2 → v3):
  - バイオームを「世界の代表都市」モデルに変更 (kyoto / sydney / charlotte)
  - 半球(hemisphere)対応: 南半球バイオームでは季節オフセットが反転
  - 緯度・経度を保持し、将来の地図表示や位置情報連動に備える
"""

# ==========================================
# 土地(バイオーム)= 世界の代表都市
# ==========================================
BIOMES = {
    "kyoto": {
        "name": "京都",
        "lat": 35.0, "lon": 135.8,
        "temp_mean": 14,
        "precip_mean": 1500,
        "hemisphere": "north",
        "max_plants": 8,
        "description": "四季がはっきりした温帯モンスーン。里山と二次林が広がり、植物・昆虫・鳥の多様性が高い。",
    },
    "sydney": {
        "name": "シドニー",
        "lat": -33.9, "lon": 151.2,
        "temp_mean": 18,
        "precip_mean": 1200,
        "hemisphere": "south",
        "max_plants": 6,
        "description": "南半球の温帯海洋性。ユーカリ林が広がり、独自進化したオーストラリア固有の鳥が多い。",
    },
    "charlotte": {
        "name": "シャーロット",
        "lat": 35.2, "lon": -80.8,
        "temp_mean": 16,
        "precip_mean": 1100,
        "hemisphere": "north",
        "max_plants": 6,
        "description": "北米東部の温帯湿潤林。落葉広葉樹とマツが混じり、鮮やかな色彩の鳥が多い。",
    },
}

# 旧バイオームIDから新IDへのマイグレーション(既存スプレッドシート互換用)
BIOME_MIGRATION = {
    "satoyama": "kyoto",
    "temperate_forest": "kyoto",
    "evergreen_forest": "kyoto",
}


# ==========================================
# 植物
# ==========================================
PLANTS = {
    # ----- 京都 -----
    "sakura":    {"name": "サクラ",       "scientific": "Prunus serrulata", "english": "Japanese Cherry",
                  "icon": "🌸", "temp_fit": (5, 22),  "biome": ["kyoto"]},
    "kunugi":    {"name": "クヌギ",       "scientific": "Quercus acutissima", "english": "Sawtooth Oak",
                  "icon": "🌳", "temp_fit": (8, 22),  "biome": ["kyoto"]},
    "enoki":     {"name": "エノキ",       "scientific": "Celtis sinensis", "english": "Chinese Hackberry",
                  "icon": "🌳", "temp_fit": (8, 24),  "biome": ["kyoto"]},
    "camellia":  {"name": "ヤブツバキ",   "scientific": "Camellia japonica", "english": "Japanese Camellia",
                  "icon": "🌺", "temp_fit": (10, 24), "biome": ["kyoto"]},
    "nanten":    {"name": "ナンテン",     "scientific": "Nandina domestica", "english": "Heavenly Bamboo",
                  "icon": "🌿", "temp_fit": (8, 24),  "biome": ["kyoto"]},
    "pine":      {"name": "アカマツ",     "scientific": "Pinus densiflora", "english": "Japanese Red Pine",
                  "icon": "🌲", "temp_fit": (3, 22),  "biome": ["kyoto"]},
    "kaki":      {"name": "カキ",         "scientific": "Diospyros kaki", "english": "Japanese Persimmon",
                  "icon": "🍂", "temp_fit": (8, 24),  "biome": ["kyoto"]},
    "rice":      {"name": "イネ(水田)",   "scientific": "Oryza sativa", "english": "Rice",
                  "icon": "🌾", "temp_fit": (15, 28), "biome": ["kyoto"]},
    "ume":       {"name": "ウメ",         "scientific": "Prunus mume", "english": "Japanese Apricot",
                  "icon": "🌸", "temp_fit": (3, 22),  "biome": ["kyoto"]},
    "sazanka":   {"name": "サザンカ",     "scientific": "Camellia sasanqua", "english": "Sasanqua Camellia",
                  "icon": "🌺", "temp_fit": (5, 22),  "biome": ["kyoto"]},
    "momiji":    {"name": "イロハモミジ", "scientific": "Acer palmatum", "english": "Japanese Maple",
                  "icon": "🍁", "temp_fit": (5, 24),  "biome": ["kyoto"]},
    "susuki":    {"name": "ススキ",       "scientific": "Miscanthus sinensis", "english": "Japanese Silver Grass",
                  "icon": "🌾", "temp_fit": (5, 28),  "biome": ["kyoto"]},
    "kobushi":   {"name": "コブシ",       "scientific": "Magnolia kobus", "english": "Kobushi Magnolia",
                  "icon": "🌼", "temp_fit": (3, 22),  "biome": ["kyoto"]},

    # ----- シドニー -----
    "eucalyptus": {"name": "ユーカリ",      "scientific": "Eucalyptus globulus", "english": "Tasmanian Blue Gum",
                   "icon": "🌳", "temp_fit": (8, 26),  "biome": ["sydney"]},
    "banksia":    {"name": "バンクシア",    "scientific": "Banksia integrifolia", "english": "Coast Banksia",
                   "icon": "🌼", "temp_fit": (10, 26), "biome": ["sydney"]},
    "waratah":    {"name": "ワラタ",        "scientific": "Telopea speciosissima", "english": "New South Wales Waratah",
                   "icon": "🌺", "temp_fit": (10, 24), "biome": ["sydney"]},
    "jacaranda":  {"name": "ジャカランダ",  "scientific": "Jacaranda mimosifolia", "english": "Blue Jacaranda",
                   "icon": "🌸", "temp_fit": (12, 28), "biome": ["sydney"]},
    "bottlebrush":{"name": "ブラシノキ",    "scientific": "Callistemon citrinus", "english": "Crimson Bottlebrush",
                   "icon": "🌺", "temp_fit": (12, 28), "biome": ["sydney"]},
    "wattle":     {"name": "ゴールデンワトル", "scientific": "Acacia pycnantha", "english": "Golden Wattle",
                   "icon": "🌼", "temp_fit": (8, 26),  "biome": ["sydney"]},
    "tea_tree":   {"name": "ティーツリー",     "scientific": "Leptospermum scoparium", "english": "Tea Tree",
                   "icon": "🌼", "temp_fit": (8, 26),  "biome": ["sydney"]},
    "grevillea":  {"name": "グレヴィレア",     "scientific": "Grevillea robusta", "english": "Silky Oak",
                   "icon": "🌺", "temp_fit": (10, 28), "biome": ["sydney"]},
    "lemon_myrtle":{"name": "レモンマートル",  "scientific": "Backhousia citriodora", "english": "Lemon Myrtle",
                   "icon": "🌿", "temp_fit": (12, 28), "biome": ["sydney"]},
    "kangaroo_paw":{"name": "カンガルーポー",  "scientific": "Anigozanthos flavidus", "english": "Kangaroo Paw",
                   "icon": "🌺", "temp_fit": (10, 26), "biome": ["sydney"]},
    "boronia":    {"name": "ボロニア",         "scientific": "Boronia megastigma", "english": "Brown Boronia",
                   "icon": "🌸", "temp_fit": (8, 22),  "biome": ["sydney"]},

    # ----- シャーロット(NC) -----
    "dogwood":      {"name": "アメリカハナミズキ", "scientific": "Cornus florida", "english": "Flowering Dogwood",
                     "icon": "🌸", "temp_fit": (5, 26),  "biome": ["charlotte"]},
    "red_maple":    {"name": "アメリカハナノキ",   "scientific": "Acer rubrum", "english": "Red Maple",
                     "icon": "🍁", "temp_fit": (3, 26),  "biome": ["charlotte"]},
    "loblolly":     {"name": "テーダマツ",         "scientific": "Pinus taeda", "english": "Loblolly Pine",
                     "icon": "🌲", "temp_fit": (5, 28),  "biome": ["charlotte"]},
    "magnolia":     {"name": "タイサンボク",       "scientific": "Magnolia grandiflora", "english": "Southern Magnolia",
                     "icon": "🌼", "temp_fit": (8, 28),  "biome": ["charlotte"]},
    "redbud":       {"name": "アメリカハナズオウ", "scientific": "Cercis canadensis", "english": "Eastern Redbud",
                     "icon": "🌸", "temp_fit": (5, 26),  "biome": ["charlotte"]},
    "tulip_tree":   {"name": "ユリノキ",           "scientific": "Liriodendron tulipifera", "english": "Tulip Tree",
                     "icon": "🌳", "temp_fit": (5, 26),  "biome": ["charlotte"]},
    "white_oak":    {"name": "アメリカホワイトオーク", "scientific": "Quercus alba", "english": "White Oak",
                     "icon": "🌳", "temp_fit": (3, 26),  "biome": ["charlotte"]},
    "sourwood":     {"name": "サワーウッド",       "scientific": "Oxydendrum arboreum", "english": "Sourwood",
                     "icon": "🌼", "temp_fit": (5, 26),  "biome": ["charlotte"]},
    "sweetbay":     {"name": "ヒメタイサンボク",   "scientific": "Magnolia virginiana", "english": "Sweetbay Magnolia",
                     "icon": "🌼", "temp_fit": (8, 28),  "biome": ["charlotte"]},
    "buttonbush":   {"name": "アメリカタニワタリノキ", "scientific": "Cephalanthus occidentalis", "english": "Buttonbush",
                     "icon": "🌸", "temp_fit": (8, 28),  "biome": ["charlotte"]},
    "service_berry":{"name": "サービスベリー",     "scientific": "Amelanchier arborea", "english": "Serviceberry",
                     "icon": "🍒", "temp_fit": (3, 24),  "biome": ["charlotte"]},
}


# ==========================================
# 昆虫・小動物
# ==========================================
INSECTS = {
    # ----- 京都 -----
    "abura_zemi": {
        "name": "アブラゼミ", "scientific": "Graptopsaltria nigrofuscata", "english": "Large Brown Cicada",
        "temp_fit": (20, 30), "eats_plants": ["sakura", "kunugi", "enoki"]
    },
    "kabuto_mushi": {
        "name": "カブトムシ", "scientific": "Trypoxylus dichotomus", "english": "Japanese Rhinoceros Beetle",
        "temp_fit": (18, 30), "eats_plants": ["kunugi"]
    },
    "ao_imo_mushi": {
        "name": "アオムシ(モンシロチョウ幼虫)", "scientific": "Pieris rapae", "english": "Cabbage White Caterpillar",
        "temp_fit": (10, 26), "eats_plants": ["sakura", "enoki"]
    },
    "kara_imo_mushi": {
        "name": "シャクトリムシ類", "scientific": "Geometridae", "english": "Inchworm",
        "temp_fit": (8, 25), "eats_plants": ["sakura", "kunugi", "kaki"]
    },
    "nihon_mitsubachi": {
        "name": "ニホンミツバチ", "scientific": "Apis cerana japonica", "english": "Japanese Honeybee",
        "temp_fit": (10, 28), "eats_plants": ["sakura", "camellia", "kaki"]
    },
    "shio_kara_tonbo": {
        "name": "シオカラトンボ", "scientific": "Orthetrum albistylum", "english": "White-tailed Skimmer",
        "temp_fit": (15, 30), "eats_plants": ["rice"]
    },
    "ama_gaeru": {
        "name": "ニホンアマガエル", "scientific": "Hyla japonica", "english": "Japanese Tree Frog",
        "temp_fit": (10, 28), "eats_plants": ["rice"]
    },

    # ----- シドニー -----
    "blue_banded_bee": {
        "name": "アオスジハナバチ", "scientific": "Amegilla cingulata", "english": "Blue-banded Bee",
        "temp_fit": (14, 30), "eats_plants": ["banksia", "waratah", "bottlebrush", "wattle"]
    },
    "christmas_beetle": {
        "name": "クリスマスビートル", "scientific": "Anoplognathus pallidicollis", "english": "Christmas Beetle",
        "temp_fit": (16, 30), "eats_plants": ["eucalyptus"]
    },
    "bogong_moth": {
        "name": "ボゴンガ", "scientific": "Agrotis infusa", "english": "Bogong Moth",
        "temp_fit": (10, 24), "eats_plants": ["wattle", "eucalyptus"]
    },
    "australian_cicada": {
        "name": "グリーングローサー", "scientific": "Cyclochila australasiae", "english": "Green Grocer Cicada",
        "temp_fit": (18, 32), "eats_plants": ["eucalyptus", "jacaranda"]
    },

    # ----- シャーロット -----
    "monarch": {
        "name": "オオカバマダラ", "scientific": "Danaus plexippus", "english": "Monarch Butterfly",
        "temp_fit": (12, 28), "eats_plants": ["dogwood", "redbud", "magnolia"]
    },
    "carpenter_bee": {
        "name": "アメリカクマバチ", "scientific": "Xylocopa virginica", "english": "Eastern Carpenter Bee",
        "temp_fit": (12, 28), "eats_plants": ["redbud", "magnolia", "tulip_tree", "dogwood"]
    },
    "june_beetle": {
        "name": "ジューンビートル", "scientific": "Phyllophaga sp.", "english": "June Beetle",
        "temp_fit": (15, 28), "eats_plants": ["red_maple", "tulip_tree"]
    },
    "tent_caterpillar": {
        "name": "アメリカマイマイガ幼虫", "scientific": "Malacosoma americanum", "english": "Eastern Tent Caterpillar",
        "temp_fit": (8, 25), "eats_plants": ["dogwood", "red_maple", "tulip_tree"]
    },
    "fireflies": {
        "name": "アメリカホタル", "scientific": "Photinus pyralis", "english": "Common Eastern Firefly",
        "temp_fit": (16, 28), "eats_plants": ["loblolly", "red_maple"]
    },

    # ----- 京都(追加) -----
    "ageha_chou": {
        "name": "アゲハチョウ", "scientific": "Papilio xuthus", "english": "Asian Swallowtail",
        "temp_fit": (12, 28), "eats_plants": ["sakura", "ume", "sazanka", "kobushi"]
    },
    "kuwagata": {
        "name": "クワガタムシ", "scientific": "Lucanidae", "english": "Stag Beetle",
        "temp_fit": (15, 28), "eats_plants": ["kunugi", "enoki", "momiji"]
    },

    # ----- シドニー(追加) -----
    "sugar_glider_insect": {
        "name": "オーストラリアハチノスツヅリガ", "scientific": "Galleria mellonella", "english": "Wax Moth",
        "temp_fit": (14, 28), "eats_plants": ["eucalyptus", "tea_tree"]
    },
    "lacewing_au": {
        "name": "オーストラリアクサカゲロウ", "scientific": "Mallada signatus", "english": "Green Lacewing",
        "temp_fit": (10, 28), "eats_plants": ["grevillea", "lemon_myrtle", "boronia"]
    },

    # ----- シャーロット(追加) -----
    "katydid": {
        "name": "アメリカキリギリス", "scientific": "Tettigoniidae", "english": "Katydid",
        "temp_fit": (14, 28), "eats_plants": ["white_oak", "tulip_tree", "sourwood"]
    },
    "ruby_tiger_moth": {
        "name": "ルビートラガ", "scientific": "Phragmatobia fuliginosa", "english": "Ruby Tiger Moth",
        "temp_fit": (10, 25), "eats_plants": ["service_berry", "buttonbush", "sweetbay"]
    },
    "hoverfly_us": {
        "name": "アメリカハナアブ", "scientific": "Toxomerus marginatus", "english": "Calligrapher Fly",
        "temp_fit": (10, 28), "eats_plants": ["sourwood", "sweetbay", "buttonbush", "service_berry"]
    },
}


# ==========================================
# 鳥
# ==========================================
BIRDS = {
    # ----- 京都 -----
    "shijukara": {
        "name": "シジュウカラ", "scientific": "Parus minor", "english": "Japanese Tit", "color": "#2a2a2a",
        "eats_plants": ["pine"], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi", "kabuto_mushi"],
        "temp_fit": (0, 28), "biome_pref": ["kyoto"],
        "rarity": 0.3,
        "description": "白黒ネクタイ模様が特徴。都市部から森まで幅広く生息する身近な鳥。",
    },
    "suzume": {
        "name": "スズメ", "scientific": "Passer montanus", "english": "Eurasian Tree Sparrow", "color": "#a07040",
        "eats_plants": ["rice"], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (0, 30), "biome_pref": ["kyoto"],
        "rarity": 0.2,
        "description": "人里の代表種。イネ科植物と人の営みに密接に結びついている。",
    },
    "mejiro": {
        "name": "メジロ", "scientific": "Zosterops japonicus", "english": "Japanese White-eye", "color": "#9ab846",
        "eats_plants": ["sakura", "camellia", "enoki", "nanten", "kaki"],
        "eats_insects": [],
        "temp_fit": (5, 28), "biome_pref": ["kyoto"],
        "rarity": 0.35,
        "description": "目の周りの白いリングが特徴。花の蜜と果実を好む。",
    },
    "hiyodori": {
        "name": "ヒヨドリ", "scientific": "Hypsipetes amaurotis", "english": "Brown-eared Bulbul", "color": "#7a7a7a",
        "eats_plants": ["sakura", "camellia", "enoki", "nanten", "kaki"],
        "eats_insects": [],
        "temp_fit": (0, 28), "biome_pref": ["kyoto"],
        "rarity": 0.3,
        "description": "大声で賑やか。果実を好み、種子散布者として重要。",
    },
    "uguisu": {
        "name": "ウグイス", "scientific": "Horornis diphone", "english": "Japanese Bush Warbler", "color": "#8a9452",
        "eats_plants": [], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (5, 28), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "春告鳥。藪の中で美しく囀るが姿を見せることは少ない。",
    },
    "kogera": {
        "name": "コゲラ", "scientific": "Dendrocopos kizuki", "english": "Japanese Pygmy Woodpecker", "color": "#6a5a4a",
        "eats_plants": [], "eats_insects": ["kabuto_mushi", "ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 25), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "日本最小のキツツキ。枯れ木を叩いて虫を探す。",
    },
    "yamagara": {
        "name": "ヤマガラ", "scientific": "Sittiparus varius", "english": "Varied Tit", "color": "#b06030",
        "eats_plants": ["kunugi"],
        "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-2, 25), "biome_pref": ["kyoto"],
        "rarity": 0.4,
        "description": "ドングリを蓄える習性。人懐っこい性格で知られる。",
    },
    "kibitaki": {
        "name": "キビタキ", "scientific": "Ficedula narcissina", "english": "Narcissus Flycatcher", "color": "#e8b820",
        "eats_plants": [], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (12, 24), "biome_pref": ["kyoto"],
        "rarity": 0.75,
        "description": "黄色と黒の夏鳥。林冠で朗らかに囀る。冬は南方へ渡る。",
    },
    "tsubame": {
        "name": "ツバメ", "scientific": "Hirundo rustica", "english": "Barn Swallow", "color": "#1a2a4a",
        "eats_plants": [], "eats_insects": ["nihon_mitsubachi", "shio_kara_tonbo"],
        "temp_fit": (14, 28), "biome_pref": ["kyoto"],
        "rarity": 0.45,
        "description": "春に渡来する夏鳥。飛翔しながら空中の昆虫を捕食する。",
    },
    "kawasemi": {
        "name": "カワセミ", "scientific": "Alcedo atthis", "english": "Common Kingfisher", "color": "#1a7ac8",
        "eats_plants": [], "eats_insects": ["shio_kara_tonbo", "ama_gaeru"],
        "temp_fit": (0, 28), "biome_pref": ["kyoto"],
        "rarity": 0.65,
        "description": "宝石のような青い背。水場が必須。飛び込んで魚や水生昆虫を捕る。",
    },
    "ikaru": {
        "name": "イカル", "scientific": "Eophona personata", "english": "Japanese Grosbeak", "color": "#c0a040",
        "eats_plants": ["kunugi", "nanten", "pine"],
        "eats_insects": [],
        "temp_fit": (-2, 22), "biome_pref": ["kyoto"],
        "rarity": 0.65,
        "description": "太い黄色いくちばしで堅い種子を割る。",
    },
    "kawarahiwa": {
        "name": "カワラヒワ", "scientific": "Chloris sinica", "english": "Oriental Greenfinch", "color": "#b8a040",
        "eats_plants": ["susuki", "rice", "pine"],
        "eats_insects": [],
        "temp_fit": (-2, 28), "biome_pref": ["kyoto"],
        "rarity": 0.4,
        "description": "黄色い翼斑が目立つ。種子食でススキ原や河川敷を好む。",
    },
    "enaga": {
        "name": "エナガ", "scientific": "Aegithalos caudatus", "english": "Long-tailed Tit", "color": "#d4d4d4",
        "eats_plants": [],
        "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 24), "biome_pref": ["kyoto"],
        "rarity": 0.55,
        "description": "丸い体に長い尾。雪だるまのような姿で群れで動く。",
    },
    "kakesu": {
        "name": "カケス", "scientific": "Garrulus glandarius", "english": "Eurasian Jay", "color": "#a87878",
        "eats_plants": ["kunugi", "kaki"],
        "eats_insects": ["kabuto_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 24), "biome_pref": ["kyoto"],
        "rarity": 0.55,
        "description": "ドングリを地面に隠す習性で、ナラ類の森を育てる賢い鳥。",
    },

    # ----- シドニー -----
    "rainbow_lorikeet": {
        "name": "ゴシキセイガイインコ", "scientific": "Trichoglossus moluccanus", "english": "Rainbow Lorikeet",
        "color": "#1a8a4a",
        "eats_plants": ["banksia", "waratah", "bottlebrush", "eucalyptus", "jacaranda"],
        "eats_insects": [],
        "temp_fit": (10, 30), "biome_pref": ["sydney"],
        "rarity": 0.3,
        "description": "鮮やかな七色の羽。花の蜜を好み、群れで賑やかに飛び回る。",
    },
    "kookaburra": {
        "name": "ワライカワセミ", "scientific": "Dacelo novaeguineae", "english": "Laughing Kookaburra",
        "color": "#a08040",
        "eats_plants": [], "eats_insects": ["christmas_beetle", "australian_cicada"],
        "temp_fit": (8, 28), "biome_pref": ["sydney"],
        "rarity": 0.5,
        "description": "笑い声のような鳴き声で有名。世界最大のカワセミ科の鳥。",
    },
    "australian_magpie": {
        "name": "カササギフエガラス", "scientific": "Gymnorhina tibicen", "english": "Australian Magpie",
        "color": "#1a1a1a",
        "eats_plants": [], "eats_insects": ["christmas_beetle", "june_beetle", "bogong_moth"],
        "temp_fit": (5, 28), "biome_pref": ["sydney"],
        "rarity": 0.35,
        "description": "美しいフルートのような囀り。賢く、人の顔を覚えると言われる。",
    },
    "sulphur_crested_cockatoo": {
        "name": "キバタン", "scientific": "Cacatua galerita", "english": "Sulphur-crested Cockatoo",
        "color": "#f0e090",
        "eats_plants": ["eucalyptus", "wattle", "banksia"],
        "eats_insects": [],
        "temp_fit": (8, 30), "biome_pref": ["sydney"],
        "rarity": 0.55,
        "description": "黄色い冠羽が印象的な大型のオウム。長寿で、80年以上生きる個体もいる。",
    },
    "eastern_yellow_robin": {
        "name": "キバラオーストラリアコマドリ", "scientific": "Eopsaltria australis", "english": "Eastern Yellow Robin",
        "color": "#e8d048",
        "eats_plants": [], "eats_insects": ["bogong_moth", "christmas_beetle"],
        "temp_fit": (8, 24), "biome_pref": ["sydney"],
        "rarity": 0.65,
        "description": "鮮やかな黄色いお腹。森の縁で昆虫を狙う。",
    },
    "superb_fairywren": {
        "name": "ルリオーストラリアムシクイ", "scientific": "Malurus cyaneus", "english": "Superb Fairywren",
        "color": "#3a4ac8",
        "eats_plants": [], "eats_insects": ["bogong_moth", "blue_banded_bee"],
        "temp_fit": (5, 26), "biome_pref": ["sydney"],
        "rarity": 0.55,
        "description": "繁殖期の雄は鮮やかな青。家族群で藪の中を移動する。",
    },
    "noisy_miner": {
        "name": "クロガオミツスイ", "scientific": "Manorina melanocephala", "english": "Noisy Miner",
        "color": "#a8b0a0",
        "eats_plants": ["banksia", "bottlebrush", "eucalyptus"],
        "eats_insects": ["blue_banded_bee"],
        "temp_fit": (8, 30), "biome_pref": ["sydney"],
        "rarity": 0.4,
        "description": "賑やかで攻撃的。ユーカリ林の蜜を巡って群れで縄張りを守る。",
    },
    "galah": {
        "name": "モモイロインコ", "scientific": "Eolophus roseicapilla", "english": "Galah",
        "color": "#e89aa8",
        "eats_plants": ["wattle", "eucalyptus", "grevillea"],
        "eats_insects": [],
        "temp_fit": (8, 30), "biome_pref": ["sydney"],
        "rarity": 0.5,
        "description": "ピンクとグレーの羽が美しい。芝生で種を食べる姿が見られる。",
    },
    "willie_wagtail": {
        "name": "オウギビタキ", "scientific": "Rhipidura leucophrys", "english": "Willie Wagtail",
        "color": "#1a1a1a",
        "eats_plants": [],
        "eats_insects": ["blue_banded_bee", "australian_cicada", "bogong_moth"],
        "temp_fit": (10, 30), "biome_pref": ["sydney"],
        "rarity": 0.45,
        "description": "尾を扇状に広げて昆虫を追う。庭でも見られる人懐っこい鳥。",
    },
    "satin_bowerbird": {
        "name": "アオアズマヤドリ", "scientific": "Ptilonorhynchus violaceus", "english": "Satin Bowerbird",
        "color": "#2a2050",
        "eats_plants": ["banksia", "jacaranda", "lemon_myrtle"],
        "eats_insects": ["christmas_beetle"],
        "temp_fit": (8, 28), "biome_pref": ["sydney"],
        "rarity": 0.7,
        "description": "雄が青い物を集めて求愛舞台(あずまや)を作る、知性的な鳥。",
    },

    # ----- シャーロット -----
    "northern_cardinal": {
        "name": "ショウジョウコウカンチョウ", "scientific": "Cardinalis cardinalis", "english": "Northern Cardinal",
        "color": "#c83020",
        "eats_plants": ["dogwood", "redbud", "tulip_tree"],
        "eats_insects": ["tent_caterpillar"],
        "temp_fit": (-5, 30), "biome_pref": ["charlotte"],
        "rarity": 0.3,
        "description": "ノースカロライナ州の州鳥。鮮やかな赤い羽と黒い顔が印象的。",
    },
    "blue_jay": {
        "name": "アオカケス", "scientific": "Cyanocitta cristata", "english": "Blue Jay",
        "color": "#3a78c8",
        "eats_plants": ["loblolly", "red_maple", "magnolia"],
        "eats_insects": ["june_beetle", "tent_caterpillar"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.35,
        "description": "鮮やかな青と白の羽。賢く、ドングリを蓄える習性で知られる。",
    },
    "eastern_bluebird": {
        "name": "ルリツグミ", "scientific": "Sialia sialis", "english": "Eastern Bluebird",
        "color": "#3858b8",
        "eats_plants": ["dogwood", "redbud"],
        "eats_insects": ["tent_caterpillar", "june_beetle"],
        "temp_fit": (0, 28), "biome_pref": ["charlotte"],
        "rarity": 0.5,
        "description": "深い青と橙の羽。開けた草地で昆虫を狙う。",
    },
    "american_robin": {
        "name": "コマツグミ", "scientific": "Turdus migratorius", "english": "American Robin",
        "color": "#a06030",
        "eats_plants": ["dogwood", "magnolia", "redbud"],
        "eats_insects": ["june_beetle", "tent_caterpillar"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.3,
        "description": "胸の橙が特徴。北米で最もよく見られるツグミ類。",
    },
    "carolina_wren": {
        "name": "カロライナミソサザイ", "scientific": "Thryothorus ludovicianus", "english": "Carolina Wren",
        "color": "#a87038",
        "eats_plants": [], "eats_insects": ["tent_caterpillar", "fireflies", "carpenter_bee"],
        "temp_fit": (0, 30), "biome_pref": ["charlotte"],
        "rarity": 0.45,
        "description": "「ティーケトル」と聞こえる元気な囀り。藪を好み、年中見られる。",
    },
    "pileated_woodpecker": {
        "name": "エボシクマゲラ", "scientific": "Dryocopus pileatus", "english": "Pileated Woodpecker",
        "color": "#c01818",
        "eats_plants": [], "eats_insects": ["june_beetle", "carpenter_bee"],
        "temp_fit": (-5, 26), "biome_pref": ["charlotte"],
        "rarity": 0.7,
        "description": "鮮やかな赤い冠羽の大型キツツキ。森の古木で大きな穴を開ける。",
    },
    "ruby_throated_hummingbird": {
        "name": "ルビーノドハチドリ", "scientific": "Archilochus colubris", "english": "Ruby-throated Hummingbird",
        "color": "#3a8a3a",
        "eats_plants": ["redbud", "tulip_tree", "magnolia"],
        "eats_insects": [],
        "temp_fit": (12, 28), "biome_pref": ["charlotte"],
        "rarity": 0.7,
        "description": "翼を毎秒50回以上はばたかせる小さなハチドリ。夏に北米東部で繁殖する。",
    },
    "mourning_dove": {
        "name": "ナゲキバト", "scientific": "Zenaida macroura", "english": "Mourning Dove",
        "color": "#a89878",
        "eats_plants": ["loblolly", "red_maple"],
        "eats_insects": [],
        "temp_fit": (-2, 30), "biome_pref": ["charlotte"],
        "rarity": 0.35,
        "description": "ベージュ色の落ち着いた羽。「クー」という哀しげな鳴き声で知られる。",
    },
    "tufted_titmouse": {
        "name": "エボシガラ", "scientific": "Baeolophus bicolor", "english": "Tufted Titmouse",
        "color": "#9aa8b8",
        "eats_plants": ["red_maple", "tulip_tree"],
        "eats_insects": ["tent_caterpillar", "june_beetle"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.4,
        "description": "灰色の冠羽が特徴。シジュウカラ科の北米代表種。",
    },
    "american_goldfinch": {
        "name": "オウゴンヒワ", "scientific": "Spinus tristis", "english": "American Goldfinch",
        "color": "#f0d040",
        "eats_plants": ["dogwood", "redbud"],
        "eats_insects": [],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.5,
        "description": "夏は鮮やかな黄色。種子食で、果実樹の周辺で群れる。",
    },
    "downy_woodpecker": {
        "name": "セジロコゲラ", "scientific": "Dryobates pubescens", "english": "Downy Woodpecker",
        "color": "#1a1a1a",
        "eats_plants": [],
        "eats_insects": ["june_beetle", "carpenter_bee", "tent_caterpillar"],
        "temp_fit": (-8, 28), "biome_pref": ["charlotte"],
        "rarity": 0.45,
        "description": "北米最小のキツツキ。住宅街の餌台にもよく現れる。",
    },
}


# ==========================================
# 季節モデル(月→気温オフセット、北半球基準)
# 南半球バイオームでは engine.current_temperature が6ヶ月反転して適用する
# ==========================================
SEASON_TEMP_OFFSET = {
    1: -6, 2: -5, 3: -2, 4: 1, 5: 4, 6: 6,
    7: 8, 8: 8, 9: 5, 10: 1, 11: -2, 12: -5,
}
