"""
Toris Collection - ネットワーク構築と確率計算エンジン (v3)

v3:
  - ENVIRONMENTS を廃止(GloBIは種ペア相互作用のみなので、ため池などの
    「種ではない環境」はネットワークから除外)
  - ノードは PLANTS / INSECTS / BIRDS の3種類のみ
  - Sony CSL の補正済みPageRankが利用可能なら、レア度係数に活用(オプション)
"""
import math
import networkx as nx
from data import PLANTS, INSECTS, BIRDS, BIOMES, SEASON_TEMP_OFFSET

# Sony CSL 中心性データ(任意)
_CENTRALITIES = None
_CENTRALITY_LOADED = False


def _try_load_centralities():
    """起動時に一度だけ中心性データの読み込みを試みる。失敗したら None のまま。"""
    global _CENTRALITIES, _CENTRALITY_LOADED
    if _CENTRALITY_LOADED:
        return _CENTRALITIES
    _CENTRALITY_LOADED = True

    try:
        from centrality import is_available, load_centralities
        if not is_available():
            return None
        taxa = {b["scientific"].upper() for b in BIRDS.values() if b.get("scientific")}
        _CENTRALITIES = load_centralities(taxon_filter=taxa)
        print(f"[engine] Sony CSL centrality loaded: {len(_CENTRALITIES)} taxa")
        return _CENTRALITIES
    except Exception as e:
        print(f"[engine] centrality load skipped: {e}")
        return None


def current_temperature(biome_id: str, month: int) -> float:
    """その土地・月における気温。
    南半球バイオームでは季節オフセットを反転させる(N月とS月で6ヶ月ずれる)。
    """
    biome = BIOMES[biome_id]
    hemisphere = biome.get("hemisphere", "north")
    if hemisphere == "south":
        # 北半球の対応する月のオフセットを使う(N月の暑さがS月の寒さ等になる)
        opp_month = ((month - 1 + 6) % 12) + 1
        offset = SEASON_TEMP_OFFSET[opp_month]
    else:
        offset = SEASON_TEMP_OFFSET[month]
    return biome["temp_mean"] + offset


def temperature_fit(temp: float, fit_range: tuple) -> float:
    """気温適合度を 0.0-1.0 で返す"""
    lo, hi = fit_range
    center = (lo + hi) / 2
    half = (hi - lo) / 2
    if half <= 0:
        return 0.0
    distance = abs(temp - center)
    if distance <= half:
        return 1.0 - 0.5 * (distance / half)
    else:
        overshoot = distance - half
        return max(0.0, 0.5 * (0.9 ** overshoot))


def network_stats(G):
    """
    ネットワークの複雑性指標を返す。
    Returns: dict with
      - n_plants, n_insects, n_birds_active(エサ経路がある鳥の数),
      - n_edges(相互作用の数),
      - hub_node(最も次数の大きいノード id, kind, label, degree),
    """
    n_plants = sum(1 for n, d in G.nodes(data=True) if d.get("kind") == "plant")
    n_insects = sum(1 for n, d in G.nodes(data=True) if d.get("kind") == "insect")
    n_birds_active = sum(
        1 for n, d in G.nodes(data=True)
        if d.get("kind") == "bird" and G.in_degree(n) > 0
    )
    n_edges = G.number_of_edges()

    hub = None
    max_deg = 0
    for n, d in G.nodes(data=True):
        if d.get("kind") == "bird" and G.in_degree(n) == 0:
            continue
        deg = G.in_degree(n) + G.out_degree(n)
        if deg > max_deg:
            max_deg = deg
            hub = (n, d.get("kind"), d.get("label"), deg)

    return {
        "n_plants": n_plants,
        "n_insects": n_insects,
        "n_birds_active": n_birds_active,
        "n_edges": n_edges,
        "hub": hub,
    }


def suggest_for_bird(target_bird_id, planted_plants, biome_id, month):
    """
    目標の鳥を呼ぶために、現状で「足りないもの」を提案する。
    不適合判定は確率(0%等)で表現するので、ここでは植物の提案のみを返す。

    Returns: dict with
      - "current_prob": 現状の出現確率
      - "suggestions": [{"plant_id", "reason", "directness"}] のリスト
      - "has_food_path": 既に食物経路があるか
    """
    if target_bird_id not in BIRDS:
        return None
    bird = BIRDS[target_bird_id]
    temp = current_temperature(biome_id, month)

    G, _ = build_network(planted_plants, biome_id, month)
    info = calculate_arrival_probability(target_bird_id, G, biome_id, month)
    current_prob = info["probability"]
    has_food_path = bool(info.get("incoming_paths"))

    suggestions = []
    seen_plants = set()

    # 1. 直接食べる植物のうち、植えていないものを提案(バイオーム/気温が合うもの)
    for p_id in bird.get("eats_plants", []):
        if p_id not in PLANTS:
            continue
        if p_id in planted_plants:
            continue
        if biome_id not in PLANTS[p_id].get("biome", []):
            continue
        p_fit = temperature_fit(temp, PLANTS[p_id]["temp_fit"])
        if p_fit < 0.05:
            continue
        if p_id not in seen_plants:
            seen_plants.add(p_id)
            suggestions.append({
                "plant_id": p_id,
                "reason": f"{bird['name']}が直接食べる",
                "directness": "direct",
            })

    # 2. 食べる昆虫を成立させるための植物を提案
    for i_id in bird.get("eats_insects", []):
        if i_id not in INSECTS:
            continue
        insect = INSECTS[i_id]
        i_fit = temperature_fit(temp, insect["temp_fit"])
        if i_fit < 0.1:
            continue
        insect_satisfied = any(
            p in planted_plants for p in insect.get("eats_plants", [])
        )
        if insect_satisfied:
            continue
        for p_id in insect.get("eats_plants", []):
            if p_id not in PLANTS:
                continue
            if biome_id not in PLANTS[p_id].get("biome", []):
                continue
            p_fit = temperature_fit(temp, PLANTS[p_id]["temp_fit"])
            if p_fit < 0.05:
                continue
            if p_id not in seen_plants:
                seen_plants.add(p_id)
                suggestions.append({
                    "plant_id": p_id,
                    "reason": f"{insect['name']}を呼ぶため "
                              f"({bird['name']}が{insect['name']}を食べる)",
                    "directness": "indirect",
                })
                break

    return {
        "current_prob": current_prob,
        "has_food_path": has_food_path,
        "suggestions": suggestions,
    }


def simulate_with_added_plant(target_bird_id, planted_plants, candidate_plant,
                              biome_id, month):
    """
    候補植物を仮想的に追加した場合の、対象鳥の確率を計算する。
    現状の確率と並べて表示する用。
    """
    sim_planted = list(planted_plants) + [candidate_plant]
    G_sim, _ = build_network(sim_planted, biome_id, month)
    info = calculate_arrival_probability(target_bird_id, G_sim, biome_id, month)
    return info["probability"]


def build_network(planted_plants: list, biome_id: str, month: int):
    """
    その土地・月における生態系ネットワークを構築。
    ノード種別: 'plant' / 'insect' / 'bird'
    """
    G = nx.DiGraph()
    temp = current_temperature(biome_id, month)

    # --- 植物 (気温不適合なら含めない) ---
    active_plants = set()
    for p_id in planted_plants:
        if p_id not in PLANTS:
            continue
        plant = PLANTS[p_id]
        fit = temperature_fit(temp, plant["temp_fit"])
        if fit < 0.05:
            continue
        G.add_node(p_id, kind="plant", label=plant["name"], fit=fit)
        active_plants.add(p_id)

    # --- 昆虫 (依存する植物が1つでもあれば発生) ---
    active_insects = set()
    for i_id, insect in INSECTS.items():
        i_fit = temperature_fit(temp, insect["temp_fit"])
        if i_fit < 0.1:
            continue
        linked = [p for p in insect["eats_plants"] if p in active_plants]
        if not linked:
            continue
        G.add_node(i_id, kind="insect", label=insect["name"], fit=i_fit)
        for p in linked:
            G.add_edge(p, i_id, weight=i_fit)
        active_insects.add(i_id)

    # --- 鳥 (すべての鳥をノードとして含める) ---
    for b_id, bird in BIRDS.items():
        G.add_node(b_id, kind="bird", label=bird["name"], rarity=bird["rarity"])
        for p in bird["eats_plants"]:
            if p in active_plants:
                G.add_edge(p, b_id, weight=G.nodes[p]["fit"])
        for i in bird["eats_insects"]:
            if i in active_insects:
                G.add_edge(i, b_id, weight=G.nodes[i]["fit"])

    return G, temp


def calculate_arrival_probability(bird_id: str, G: nx.DiGraph, biome_id: str, month: int) -> dict:
    """鳥の出現確率 = 気温適合 × バイオーム × 食物網スコア × レア度係数"""
    bird = BIRDS[bird_id]
    temp = current_temperature(biome_id, month)

    t_fit = temperature_fit(temp, bird["temp_fit"])
    # 適合バイオーム外はかなり厳しく(生態的に来づらい)
    biome_bonus = 1.0 if biome_id in bird["biome_pref"] else 0.15

    # 食物網スコア: その鳥に流入するエッジ重みの合計
    food_score = 0.0
    incoming_paths = []
    if bird_id in G:
        for pred in G.predecessors(bird_id):
            w = G[pred][bird_id]["weight"]
            food_score += w
            incoming_paths.append((G.nodes[pred].get("kind"), pred, w))

    # 飽和関数で 0-1 に正規化(以前より食物網が育たないと確率が低い)
    food_factor = 0.0 if food_score <= 0 else 1.0 - (0.6 ** food_score)

    # レア度係数: 基本はシードのrarity、Sony CSL PageRank補正があれば上書き
    # 0.85 倍することで全体的に確率を下げる(鳥が来すぎ防止)
    rarity_factor = (1.0 - bird["rarity"] * 0.85) * 0.9
    centrality_used = None

    cents = _try_load_centralities()
    if cents and bird.get("scientific"):
        key = bird["scientific"].upper()
        if key in cents:
            pr = cents[key].get("pr_corrected") or cents[key].get("pr")
            if pr and pr > 0:
                log_pr = math.log10(pr)
                # 範囲を狭めて、レアな鳥がより来づらくなるよう調整
                # -8 → 0.05 (超レア) / -4 → 0.7 (普通)
                normalized = max(0.05, min(0.7, (log_pr + 8) / 5))
                rarity_factor = normalized
                centrality_used = pr

    # 全体倍率(0.5)で引き締め: 自然観察的にも、コレクション体験的にも、
    # 滞在2-4種の落ち着いたフィールドを目指す
    prob = t_fit * biome_bonus * food_factor * rarity_factor * 0.5
    prob = min(1.0, max(0.0, prob))

    return {
        "probability": prob,
        "temp_fit": t_fit,
        "biome_bonus": biome_bonus,
        "food_score": food_score,
        "food_factor": food_factor,
        "rarity_factor": rarity_factor,
        "centrality_used": centrality_used,
        "incoming_paths": incoming_paths,
    }


def run_turn(planted_plants, biome_id, month, resident_birds, rng,
             max_residents=4, max_arrivals_per_turn=1):
    """1サイクル進める。
    生態学的・体験的な落ち着きのため、上限を設ける:
      max_residents: 滞在中の最大鳥数(自然観察と画面の静けさ)
      max_arrivals_per_turn: 1サイクルあたり新規到着の最大数(急激な変化を避ける)
    """
    G, temp = build_network(planted_plants, biome_id, month)

    arrivals, departures = [], []
    new_residents = set(resident_birds)

    # まず退去判定(既存の滞在鳥について)
    for b_id in list(new_residents):
        info = calculate_arrival_probability(b_id, G, biome_id, month)
        p = info["probability"]
        # 退去率: p=0→0.3, p=1→0.05
        if rng.random() < (0.3 - 0.25 * p):
            new_residents.remove(b_id)
            departures.append(b_id)

    # 次に到着判定(候補をシャッフルし、上限まで)
    candidates = []
    for b_id in BIRDS:
        if b_id in new_residents:
            continue
        info = calculate_arrival_probability(b_id, G, biome_id, month)
        if info["probability"] > 0:
            candidates.append((b_id, info["probability"]))
    rng.shuffle(candidates)

    for b_id, p in candidates:
        if len(arrivals) >= max_arrivals_per_turn:
            break
        if len(new_residents) >= max_residents:
            break
        if rng.random() < p:
            new_residents.add(b_id)
            arrivals.append(b_id)

    return {
        "graph": G,
        "temperature": temp,
        "residents": new_residents,
        "arrivals": arrivals,
        "departures": departures,
    }


def force_directed_layout(G: nx.DiGraph, width=1200, height=900, iterations=200, seed=42):
    """
    同心円(シェル)レイアウト。ノード重なりを防ぐため、カテゴリ別に同心円上に均等配置。
      - 植物(入力): 一番内側の円
      - 昆虫: 中間の円
      - 鳥(滞在中): 中間よりやや外
      - 未訪問の鳥: 一番外側の円
    各円の内部では、つながりの強いノード同士を近づけるように並べる。
    """
    import math
    if G.number_of_nodes() == 0:
        return {}

    cx, cy = width / 2, height / 2

    # 各ノードをカテゴリに振り分け
    plants = [n for n in G.nodes if G.nodes[n].get("kind") == "plant"]
    insects = [n for n in G.nodes if G.nodes[n].get("kind") == "insect"]
    birds_resident = []  # ここでは判別できないので全鳥を区別せず扱う
    birds_reachable = [n for n in G.nodes
                       if G.nodes[n].get("kind") == "bird" and G.in_degree(n) > 0]
    birds_isolated = [n for n in G.nodes
                      if G.nodes[n].get("kind") == "bird" and G.in_degree(n) == 0]

    # つながりが強い順にソート(中心性の高いものを先頭に)
    plants.sort(key=lambda n: -G.degree(n))
    insects.sort(key=lambda n: -G.degree(n))
    birds_reachable.sort(key=lambda n: -G.degree(n))

    # 各シェルの半径(画面サイズから計算)
    max_radius = min(width, height) * 0.42
    shells = [
        (plants,          max_radius * 0.30, "plants"),     # 内側
        (insects,         max_radius * 0.58, "insects"),    # 中間
        (birds_reachable, max_radius * 0.85, "birds_near"), # 外側に近い
        (birds_isolated,  max_radius * 1.00, "birds_far"),  # 最外周
    ]

    pos = {}
    for nodes, radius, _ in shells:
        if not nodes:
            continue
        n = len(nodes)
        # 開始角度をシェルごとに少しずらして、隣接シェルのノードと重ならないように
        offset = 0 if n % 2 else math.pi / n
        for i, node in enumerate(nodes):
            theta = 2 * math.pi * i / n + offset
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            pos[node] = (x, y)

    return pos
