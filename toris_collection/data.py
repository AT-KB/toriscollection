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
        "name_en": "Kyoto",
        "lat": 35.0, "lon": 135.8,
        "temp_mean": 14,
        "precip_mean": 1500,
        "hemisphere": "north",
        "max_plants": 4,
        "description": "四季がはっきりした温帯モンスーン。里山と二次林が広がり、植物・昆虫・鳥の多様性が高い。",
        "description_en": "A temperate monsoon land of four distinct seasons. Its satoyama foothills and secondary woods teem with plants, insects, and birds.",
    },
    "charlotte": {
        "name": "シャーロット",
        "name_en": "Charlotte",
        "lat": 35.2, "lon": -80.8,
        "temp_mean": 16,
        "precip_mean": 1100,
        "hemisphere": "north",
        "max_plants": 4,
        "description": "北米東部の温帯湿潤林。落葉広葉樹とマツが混じり、鮮やかな色彩の鳥が多い。",
        "description_en": "The humid temperate forest of the eastern United States. Broadleaf trees mingle with pines, home to many brightly colored birds.",
    },
}

# 旧バイオームIDから新IDへのマイグレーション(既存スプレッドシート互換用)
BIOME_MIGRATION = {
    "satoyama": "kyoto",
    "temperate_forest": "kyoto",
    "evergreen_forest": "kyoto",
    "sydney": "kyoto",  # シドニーバイオーム削除(2026-07-08)。旧セーブはkyotoへ安全に移行。
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
    # ── シャーロット追加(種子・液果を増やして種食/果実食の鳥を呼ぶ) ──
    "sunflower":    {"name": "ヒマワリ",           "scientific": "Helianthus annuus", "english": "Common Sunflower",
                     "icon": "🌻", "temp_fit": (12, 32), "biome": ["charlotte"]},
    "red_cedar":    {"name": "エンピツビャクシン", "scientific": "Juniperus virginiana", "english": "Eastern Red Cedar",
                     "icon": "🌲", "temp_fit": (-10, 28), "biome": ["charlotte"]},
    "beautyberry":  {"name": "アメリカムラサキシキブ", "scientific": "Callicarpa americana", "english": "American Beautyberry",
                     "icon": "🟣", "temp_fit": (5, 32),  "biome": ["charlotte"]},
    "pokeweed":     {"name": "ヨウシュヤマゴボウ",  "scientific": "Phytolacca americana", "english": "American Pokeweed",
                     "icon": "🍇", "temp_fit": (5, 32),  "biome": ["charlotte"]},
    # ── 京都追加(里山の液果・種子を増やして冬鳥・果実食を呼ぶ) ──
    "kuwa":         {"name": "クワ",               "scientific": "Morus australis", "english": "Mulberry",
                     "icon": "🌿", "temp_fit": (6, 30),  "biome": ["kyoto"]},
    "murasaki_shikibu": {"name": "ムラサキシキブ", "scientific": "Callicarpa japonica", "english": "Japanese Beautyberry",
                     "icon": "🟣", "temp_fit": (3, 28),  "biome": ["kyoto"]},
    "egonoki":      {"name": "エゴノキ",           "scientific": "Styrax japonica", "english": "Japanese Snowbell",
                     "icon": "🤍", "temp_fit": (2, 26),  "biome": ["kyoto"]},
    "noibara":      {"name": "ノイバラ",           "scientific": "Rosa multiflora", "english": "Multiflora Rose",
                     "icon": "🌹", "temp_fit": (-2, 26), "biome": ["kyoto"]},
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
        "description_en": "Known for its black necktie marking. A familiar visitor, at home everywhere from city parks to deep woods.",
    },
    "suzume": {
        "name": "スズメ", "scientific": "Passer montanus", "english": "Eurasian Tree Sparrow", "color": "#a07040",
        "eats_plants": ["rice"], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (0, 30), "biome_pref": ["kyoto"],
        "rarity": 0.2,
        "description": "人里の代表種。イネ科植物と人の営みに密接に結びついている。",
        "description_en": "The classic bird of villages, its life woven closely into rice fields and the ways of people.",
    },
    "mejiro": {
        "name": "メジロ", "scientific": "Zosterops japonicus", "english": "Japanese White-eye", "color": "#9ab846",
        "eats_plants": ["sakura", "camellia", "enoki", "nanten", "kaki"],
        "eats_insects": [],
        "temp_fit": (5, 28), "biome_pref": ["kyoto"],
        "rarity": 0.35,
        "description": "目の周りの白いリングが特徴。花の蜜と果実を好む。",
        "description_en": "Named for the white ring around each eye. It loves flower nectar and ripe fruit.",
    },
    "hiyodori": {
        "name": "ヒヨドリ", "scientific": "Hypsipetes amaurotis", "english": "Brown-eared Bulbul", "color": "#7a7a7a",
        "eats_plants": ["sakura", "camellia", "enoki", "nanten", "kaki"],
        "eats_insects": [],
        "temp_fit": (0, 28), "biome_pref": ["kyoto"],
        "rarity": 0.3,
        "description": "大声で賑やか。果実を好み、種子散布者として重要。",
        "description_en": "Loud and lively. A lover of fruit, and an important spreader of seeds.",
    },
    "uguisu": {
        "name": "ウグイス", "scientific": "Horornis diphone", "english": "Japanese Bush Warbler", "color": "#8a9452",
        "eats_plants": [], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (5, 28), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "春告鳥。藪の中で美しく囀るが姿を見せることは少ない。",
        "description_en": "The herald of spring. It sings beautifully from the thickets, yet rarely shows itself.",
    },
    "kogera": {
        "name": "コゲラ", "scientific": "Dendrocopos kizuki", "english": "Japanese Pygmy Woodpecker", "color": "#6a5a4a",
        "eats_plants": [], "eats_insects": ["kabuto_mushi", "ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 25), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "日本最小のキツツキ。枯れ木を叩いて虫を探す。",
        "description_en": "Japan's smallest woodpecker. It taps at dead wood in search of insects.",
    },
    "yamagara": {
        "name": "ヤマガラ", "scientific": "Sittiparus varius", "english": "Varied Tit", "color": "#b06030",
        "eats_plants": ["kunugi", "egonoki"],
        "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-2, 25), "biome_pref": ["kyoto"],
        "rarity": 0.4,
        "description": "ドングリやエゴノキの実を蓄える習性。人懐っこい性格で知られる。",
        "description_en": "It stores away acorns and snowbell seeds, and is known for its friendly, trusting nature.",
    },
    "kibitaki": {
        "name": "キビタキ", "scientific": "Ficedula narcissina", "english": "Narcissus Flycatcher", "color": "#e8b820",
        "eats_plants": [], "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (12, 24), "biome_pref": ["kyoto"],
        "rarity": 0.75,
        "description": "黄色と黒の夏鳥。林冠で朗らかに囀る。冬は南方へ渡る。",
        "description_en": "A yellow-and-black summer visitor. It sings brightly in the canopy, then heads south for winter.",
    },
    "tsubame": {
        "name": "ツバメ", "scientific": "Hirundo rustica", "english": "Barn Swallow", "color": "#1a2a4a",
        "eats_plants": [], "eats_insects": ["nihon_mitsubachi", "shio_kara_tonbo"],
        "temp_fit": (14, 28), "biome_pref": ["kyoto"],
        "rarity": 0.45,
        "description": "春に渡来する夏鳥。飛翔しながら空中の昆虫を捕食する。",
        "description_en": "A summer visitor arriving in spring. It catches insects on the wing as it flies.",
    },
    "kawasemi": {
        "name": "カワセミ", "scientific": "Alcedo atthis", "english": "Common Kingfisher", "color": "#1a7ac8",
        "eats_plants": [], "eats_insects": ["shio_kara_tonbo", "ama_gaeru"],
        "temp_fit": (0, 28), "biome_pref": ["kyoto"],
        "rarity": 0.65,
        "description": "宝石のような青い背。水場が必須。飛び込んで魚や水生昆虫を捕る。",
        "description_en": "A back of jewel-like blue. It needs water close by, diving in to catch fish and water insects.",
    },
    "ikaru": {
        "name": "イカル", "scientific": "Eophona personata", "english": "Japanese Grosbeak", "color": "#c0a040",
        "eats_plants": ["kunugi", "nanten", "pine"],
        "eats_insects": [],
        "temp_fit": (-2, 22), "biome_pref": ["kyoto"],
        "rarity": 0.65,
        "description": "太い黄色いくちばしで堅い種子を割る。",
        "description_en": "It cracks hard seeds with its thick yellow bill.",
    },
    "kawarahiwa": {
        "name": "カワラヒワ", "scientific": "Chloris sinica", "english": "Oriental Greenfinch", "color": "#b8a040",
        "eats_plants": ["susuki", "rice", "pine"],
        "eats_insects": [],
        "temp_fit": (-2, 28), "biome_pref": ["kyoto"],
        "rarity": 0.4,
        "description": "黄色い翼斑が目立つ。種子食でススキ原や河川敷を好む。",
        "description_en": "Marked by bright yellow wing patches. A seed-eater fond of silver-grass fields and riverbanks.",
    },
    "enaga": {
        "name": "エナガ", "scientific": "Aegithalos caudatus", "english": "Long-tailed Tit", "color": "#d4d4d4",
        "eats_plants": [],
        "eats_insects": ["ao_imo_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 24), "biome_pref": ["kyoto"],
        "rarity": 0.55,
        "description": "丸い体に長い尾。雪だるまのような姿で群れで動く。",
        "description_en": "A round little body with a long tail. Snowman-like, it moves about in busy flocks.",
    },
    "kakesu": {
        "name": "カケス", "scientific": "Garrulus glandarius", "english": "Eurasian Jay", "color": "#a87878",
        "eats_plants": ["kunugi", "kaki"],
        "eats_insects": ["kabuto_mushi", "kara_imo_mushi"],
        "temp_fit": (-5, 24), "biome_pref": ["kyoto"],
        "rarity": 0.55,
        "description": "ドングリを地面に隠す習性で、ナラ類の森を育てる賢い鳥。",
        "description_en": "A clever bird that buries acorns in the ground, and so helps the oak woods grow.",
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
        "description_en": "The state bird of North Carolina. Striking, with brilliant red plumage and a black face.",
    },
    "blue_jay": {
        "name": "アオカケス", "scientific": "Cyanocitta cristata", "english": "Blue Jay",
        "color": "#3a78c8",
        "eats_plants": ["loblolly", "red_maple", "magnolia"],
        "eats_insects": ["june_beetle", "tent_caterpillar"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.35,
        "description": "鮮やかな青と白の羽。賢く、ドングリを蓄える習性で知られる。",
        "description_en": "Vivid blue and white. A clever bird, known for hoarding acorns.",
    },
    "eastern_bluebird": {
        "name": "ルリツグミ", "scientific": "Sialia sialis", "english": "Eastern Bluebird",
        "color": "#3858b8",
        "eats_plants": ["dogwood", "redbud"],
        "eats_insects": ["tent_caterpillar", "june_beetle"],
        "temp_fit": (0, 28), "biome_pref": ["charlotte"],
        "rarity": 0.5,
        "description": "深い青と橙の羽。開けた草地で昆虫を狙う。",
        "description_en": "Deep blue with an orange breast. It watches for insects over open meadows.",
    },
    "american_robin": {
        "name": "コマツグミ", "scientific": "Turdus migratorius", "english": "American Robin",
        "color": "#a06030",
        "eats_plants": ["dogwood", "magnolia", "redbud"],
        "eats_insects": ["june_beetle", "tent_caterpillar"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.3,
        "description": "胸の橙が特徴。北米で最もよく見られるツグミ類。",
        "description_en": "Known for its orange breast. The most familiar thrush across North America.",
    },
    "carolina_wren": {
        "name": "カロライナミソサザイ", "scientific": "Thryothorus ludovicianus", "english": "Carolina Wren",
        "color": "#a87038",
        "eats_plants": [], "eats_insects": ["tent_caterpillar", "fireflies", "carpenter_bee"],
        "temp_fit": (0, 30), "biome_pref": ["charlotte"],
        "rarity": 0.45,
        "description": "「ティーケトル」と聞こえる元気な囀り。藪を好み、年中見られる。",
        "description_en": "Its lively song sounds like 'tea-kettle, tea-kettle.' Fond of thickets, and seen all year round.",
    },
    "pileated_woodpecker": {
        "name": "エボシクマゲラ", "scientific": "Dryocopus pileatus", "english": "Pileated Woodpecker",
        "color": "#c01818",
        "eats_plants": [], "eats_insects": ["june_beetle", "carpenter_bee"],
        "temp_fit": (-5, 26), "biome_pref": ["charlotte"],
        "rarity": 0.7,
        "description": "鮮やかな赤い冠羽の大型キツツキ。森の古木で大きな穴を開ける。",
        "description_en": "A large woodpecker with a bright red crest. It carves great holes in the forest's old trees.",
    },
    "ruby_throated_hummingbird": {
        "name": "ルビーノドハチドリ", "scientific": "Archilochus colubris", "english": "Ruby-throated Hummingbird",
        "color": "#3a8a3a",
        "eats_plants": ["redbud", "tulip_tree", "magnolia"],
        "eats_insects": [],
        "temp_fit": (12, 28), "biome_pref": ["charlotte"],
        "rarity": 0.7,
        "description": "翼を毎秒50回以上はばたかせる小さなハチドリ。夏に北米東部で繁殖する。",
        "description_en": "A tiny hummingbird whose wings beat over fifty times a second. It breeds in the eastern woods each summer.",
    },
    "mourning_dove": {
        "name": "ナゲキバト", "scientific": "Zenaida macroura", "english": "Mourning Dove",
        "color": "#a89878",
        "eats_plants": ["loblolly", "red_maple"],
        "eats_insects": [],
        "temp_fit": (-2, 30), "biome_pref": ["charlotte"],
        "rarity": 0.35,
        "description": "ベージュ色の落ち着いた羽。「クー」という哀しげな鳴き声で知られる。",
        "description_en": "Soft, muted beige plumage. Known for its low, mournful coo.",
    },
    "tufted_titmouse": {
        "name": "エボシガラ", "scientific": "Baeolophus bicolor", "english": "Tufted Titmouse",
        "color": "#9aa8b8",
        "eats_plants": ["red_maple", "tulip_tree"],
        "eats_insects": ["tent_caterpillar", "june_beetle"],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.4,
        "description": "灰色の冠羽が特徴。シジュウカラ科の北米代表種。",
        "description_en": "Marked by a small grey crest. North America's signature member of the tit family.",
    },
    "american_goldfinch": {
        "name": "オウゴンヒワ", "scientific": "Spinus tristis", "english": "American Goldfinch",
        "color": "#f0d040",
        "eats_plants": ["dogwood", "redbud"],
        "eats_insects": [],
        "temp_fit": (-5, 28), "biome_pref": ["charlotte"],
        "rarity": 0.5,
        "description": "夏は鮮やかな黄色。種子食で、果実樹の周辺で群れる。",
        "description_en": "Brilliant yellow in summer. A seed-eater that gathers around fruiting trees.",
    },
    "downy_woodpecker": {
        "name": "セジロコゲラ", "scientific": "Dryobates pubescens", "english": "Downy Woodpecker",
        "color": "#1a1a1a",
        "eats_plants": [],
        "eats_insects": ["june_beetle", "carpenter_bee", "tent_caterpillar"],
        "temp_fit": (-8, 28), "biome_pref": ["charlotte"],
        "rarity": 0.45,
        "description": "北米最小のキツツキ。住宅街の餌台にもよく現れる。",
        "description_en": "North America's smallest woodpecker. A frequent guest at backyard feeders.",
    },
    # ── シャーロット追加(スプライトは既存を流用、後追いで補充) ──
    "carolina_chickadee": {
        "name": "カロライナコガラ", "scientific": "Poecile carolinensis", "english": "Carolina Chickadee",
        "color": "#8a8a80",
        "eats_plants": ["sunflower"],
        "eats_insects": ["tent_caterpillar", "june_beetle"],
        "temp_fit": (-8, 30), "biome_pref": ["charlotte"],
        "rarity": 0.3,
        "description": "小さく人なつこいコガラ。餌台の常連で、ヒマワリの種を好む。",
        "description_en": "A tiny, friendly chickadee. A feeder regular with a taste for sunflower seeds.",
    },
    "house_finch": {
        "name": "メキシコマシコ", "scientific": "Haemorhous mexicanus", "english": "House Finch",
        "color": "#c65a52",
        "eats_plants": ["sunflower", "service_berry", "beautyberry"],
        "eats_insects": [],
        "temp_fit": (-4, 34), "biome_pref": ["charlotte"],
        "rarity": 0.3,
        "description": "住宅街に多い赤みがかった小鳥。種子と果実を好み、群れで来る。",
        "description_en": "A rosy little bird common around homes. It loves seeds and fruit, and comes in flocks.",
    },
    "red_bellied_woodpecker": {
        "name": "ズアカアメリカコゲラ", "scientific": "Melanerpes carolinus", "english": "Red-bellied Woodpecker",
        "color": "#c04a3a",
        "eats_plants": ["white_oak", "sunflower"],
        "eats_insects": ["katydid", "carpenter_bee", "june_beetle"],
        "temp_fit": (-6, 32), "biome_pref": ["charlotte"],
        "rarity": 0.45,
        "description": "頭の赤いキツツキ。ドングリや樹皮の虫、餌台の種まで幅広く食べる。",
        "description_en": "A red-capped woodpecker. It eats widely — acorns, bark insects, even feeder seed.",
    },
    "brown_thrasher": {
        "name": "チャイロツグミモドキ", "scientific": "Toxostoma rufum", "english": "Brown Thrasher",
        "color": "#9c5a2a",
        "eats_plants": ["beautyberry", "pokeweed", "service_berry"],
        "eats_insects": ["june_beetle", "katydid"],
        "temp_fit": (-4, 33), "biome_pref": ["charlotte"],
        "rarity": 0.55,
        "description": "茂みで落ち葉をかき分け虫を探す。警戒心が強く、姿を見せると珍しい。",
        "description_en": "It rummages through leaf litter in the brush for insects. Wary by nature, so a rare sight.",
        "wariness": 0.6,
    },
    "song_sparrow": {
        "name": "ウタスズメ", "scientific": "Melospiza melodia", "english": "Song Sparrow",
        "color": "#8a6a4a",
        "eats_plants": ["sunflower", "pokeweed"],
        "eats_insects": ["hoverfly_us"],
        "temp_fit": (-8, 30), "biome_pref": ["charlotte"],
        "rarity": 0.35,
        "description": "やぶ際でよくさえずるスズメの仲間。種子と小さな虫を食べる。",
        "description_en": "A sparrow that sings often at the edge of thickets. It eats seeds and small insects.",
        "wariness": 0.45,
    },
    "cedar_waxwing": {
        "name": "ヒメレンジャク", "scientific": "Bombycilla cedrorum", "english": "Cedar Waxwing",
        "color": "#b9a06a",
        "eats_plants": ["red_cedar", "service_berry", "dogwood", "beautyberry"],
        "eats_insects": [],
        "temp_fit": (-8, 28), "biome_pref": ["charlotte"],
        "rarity": 0.6,
        "description": "液果を追って群れで移動する。エンピツビャクシンの実を特に好む。",
        "description_en": "It travels in flocks in search of berries, with a special love for red cedar fruit.",
        "wariness": 0.5,
    },
    # ── 京都追加(里山の常連・冬鳥。スプライトは既存を流用、後追いで補充) ──
    "kijibato": {
        "name": "キジバト", "scientific": "Streptopelia orientalis", "english": "Oriental Turtle Dove",
        "color": "#9a7a6a",
        "eats_plants": ["rice", "kunugi", "egonoki"],
        "eats_insects": [],
        "temp_fit": (-4, 30), "biome_pref": ["kyoto"],
        "rarity": 0.3,
        "description": "「デデッポッポー」と鳴く里のハト。地面で種子や木の実を拾う。",
        "description_en": "A country dove with a soft, rolling coo. It gathers seeds and nuts from the ground.",
        "wariness": 0.35,
    },
    "hibari": {
        "name": "ヒバリ", "scientific": "Alauda arvensis", "english": "Eurasian Skylark",
        "color": "#b09a6a",
        "eats_plants": ["rice", "susuki"],
        "eats_insects": ["ao_imo_mushi"],
        "temp_fit": (-2, 30), "biome_pref": ["kyoto"],
        "rarity": 0.45,
        "description": "草地から舞い上がりさえずる。田畑の種子と虫を食べる。",
        "description_en": "It rises singing from the grasslands. It feeds on the seeds and insects of the fields.",
        "wariness": 0.45,
    },
    "mozu": {
        "name": "モズ", "scientific": "Lanius bucephalus", "english": "Bull-headed Shrike",
        "color": "#a5713a",
        "eats_plants": [],
        "eats_insects": ["kuwagata", "abura_zemi", "kara_imo_mushi"],
        "temp_fit": (-4, 28), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "小さな猛禽のような小鳥。大きな虫を捕らえ、はやにえを作る。",
        "description_en": "A small bird with the air of a little raptor. It catches large insects and leaves them impaled as a larder.",
        "wariness": 0.55,
    },
    "jou_bitaki": {
        "name": "ジョウビタキ", "scientific": "Phoenicurus auroreus", "english": "Daurian Redstart",
        "color": "#d07a3a",
        "eats_plants": ["nanten", "murasaki_shikibu", "noibara"],
        "eats_insects": ["ao_imo_mushi"],
        "temp_fit": (-8, 18), "biome_pref": ["kyoto"],
        "rarity": 0.45,
        "description": "冬に渡ってくるオレンジ色の小鳥。「ヒッ、ヒッ」と鳴き人を恐れない。",
        "description_en": "An orange little bird that arrives for winter. It calls a soft 'hit, hit' and shows little fear of people.",
        "wariness": 0.25,
    },
    "shirohara": {
        "name": "シロハラ", "scientific": "Turdus pallidus", "english": "Pale Thrush",
        "color": "#6a5a4a",
        "eats_plants": ["nanten", "murasaki_shikibu", "kuwa", "kaki"],
        "eats_insects": ["ao_imo_mushi"],
        "temp_fit": (-8, 18), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "冬の林床で落ち葉をかき分ける地味なツグミ。木の実と虫を食べる。",
        "description_en": "A quiet thrush that turns over leaves on the winter forest floor. It eats berries and insects.",
        "wariness": 0.55,
    },
    "aoji": {
        "name": "アオジ", "scientific": "Emberiza spodocephala", "english": "Black-faced Bunting",
        "color": "#8a9a5a",
        "eats_plants": ["susuki", "rice", "noibara"],
        "eats_insects": [],
        "temp_fit": (-8, 20), "biome_pref": ["kyoto"],
        "rarity": 0.5,
        "description": "冬にやぶ際で種子をついばむ。緑がかった地味なホオジロの仲間。",
        "description_en": "It pecks at seeds along the thicket's edge in winter. A quiet, greenish member of the bunting family.",
        "wariness": 0.5,
    },
}


# ── スプライト流用(新種は当面、既存のドット絵を借りる。後追いで専用絵に差し替え) ──
SPRITE_ALIASES = {
    "carolina_chickadee":     "shijukara",
    "house_finch":            "kawarahiwa",
    "red_bellied_woodpecker": "kogera",
    "brown_thrasher":         "hiyodori",
    "song_sparrow":           "suzume",
    "cedar_waxwing":          "mejiro",
    # 京都の追加種
    "kijibato":               "mourning_dove",
    "hibari":                 "suzume",
    "mozu":                   "hiyodori",
    "jou_bitaki":             "kibitaki",
    "shirohara":              "american_robin",
    "aoji":                   "kawarahiwa",
}


# ==========================================
# 警戒度 wariness(0=近づきやすい 〜 1=警戒心が強い)
# 距離メカニクス(鳥たちのキャスト)で「中→近」の接近確率に使う。
# 生態(身近さ・生息環境)に基づく設計値。あとからチューニング可能。
# ==========================================
_WARINESS = {
    # 京都
    "shijukara": 0.30, "suzume": 0.20, "mejiro": 0.40, "hiyodori": 0.35,
    "uguisu": 0.70, "kogera": 0.50, "yamagara": 0.30, "kibitaki": 0.65,
    "tsubame": 0.40, "kawasemi": 0.70, "ikaru": 0.55, "kawarahiwa": 0.45,
    "enaga": 0.50, "kakesu": 0.60,
    # シャーロット
    "northern_cardinal": 0.35, "blue_jay": 0.35, "eastern_bluebird": 0.45,
    "american_robin": 0.30, "carolina_wren": 0.45, "pileated_woodpecker": 0.80,
    "ruby_throated_hummingbird": 0.60, "mourning_dove": 0.35,
    "tufted_titmouse": 0.40, "american_goldfinch": 0.45, "downy_woodpecker": 0.45,
}
for _bid, _w in _WARINESS.items():
    if _bid in BIRDS:
        BIRDS[_bid]["wariness"] = _w


# ==========================================
# 季節モデル(月→気温オフセット、北半球基準)
# 南半球バイオームでは engine.current_temperature が6ヶ月反転して適用する
# ==========================================
SEASON_TEMP_OFFSET = {
    1: -6, 2: -5, 3: -2, 4: 1, 5: 4, 6: 6,
    7: 8, 8: 8, 9: 5, 10: 1, 11: -2, 12: -5,
}
