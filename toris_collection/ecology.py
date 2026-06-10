"""
ecology.py - 庭の鳥どうしの生態的つながりを計算する

「誰と誰が一緒に鳴くか」を生態で決めるためのモジュール。
鳥が同じ食物源(植物・昆虫)を共有しているほど、同じ場所に共存しやすく、
混群(mixed-species flock)のように一緒に行動しやすい。この共有関係を
  - ラジオUIの「この庭のつながり」表示
  - 呼応(かけあい)の相手選び(生態的に近い鳥ほど応えあう)
の両方に使う。

food web はすでに data.py に符号化されている:
  PLANT --(eats_plants)--> BIRD            (果実・種子・花の蜜を直接食べる)
  PLANT --> INSECT --(eats_insects)--> BIRD (虫を介して間接的につながる)

このモジュールは表示にもロジックにも依存しない純粋な計算だけを持つ。
"""
from __future__ import annotations

from data import PLANTS, INSECTS


def bird_food_sources(bird_id: str, birds_data: dict) -> tuple[set[str], set[str]]:
    """ある鳥が依存する食物源を (植物IDの集合, 昆虫IDの集合) で返す。"""
    bird = birds_data.get(bird_id, {})
    return set(bird.get("eats_plants", [])), set(bird.get("eats_insects", []))


def shared_resources(bird_a: str, bird_b: str, birds_data: dict) -> dict:
    """2羽が共有する食物源を返す。{"plants": [...], "insects": [...]}"""
    pa, ia = bird_food_sources(bird_a, birds_data)
    pb, ib = bird_food_sources(bird_b, birds_data)
    return {"plants": sorted(pa & pb), "insects": sorted(ia & ib)}


def affinity(bird_a: str, bird_b: str, birds_data: dict) -> int:
    """2羽の生態的近さ = 共有する食物源(植物+昆虫)の数。"""
    sr = shared_resources(bird_a, bird_b, birds_data)
    return len(sr["plants"]) + len(sr["insects"])


def affinity_matrix(bird_ids: list[str], birds_data: dict) -> list[list[int]]:
    """生態的近さの対称行列を返す(自己同士=0)。呼応の相手選びに使う。"""
    n = len(bird_ids)
    mat = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a = affinity(bird_ids[i], bird_ids[j], birds_data)
            mat[i][j] = mat[j][i] = a
    return mat


def resource_clusters(
    bird_ids: list[str],
    birds_data: dict,
    plants_data: dict | None = None,
    insects_data: dict | None = None,
    min_birds: int = 2,
) -> list[dict]:
    """
    共有食物源ごとに「それを分け合う鳥たち」をまとめる(UI表示用)。

    Returns: つながりの強い順(関わる鳥が多い順)に並んだ
      [{"kind": "plant"/"insect", "id", "name", "icon", "birds": [bird_id...]}, ...]
    min_birds 羽以上が共有する食物源だけを返す(=庭の中で実際に共起しているつながり)。
    """
    plants_data = plants_data if plants_data is not None else PLANTS
    insects_data = insects_data if insects_data is not None else INSECTS

    clusters: list[dict] = []

    for p_id, plant in plants_data.items():
        eaters = [b for b in bird_ids
                  if p_id in birds_data.get(b, {}).get("eats_plants", [])]
        if len(eaters) >= min_birds:
            clusters.append({
                "kind": "plant", "id": p_id,
                "name": plant.get("name", p_id),
                "icon": plant.get("icon", "🌿"),
                "birds": eaters,
            })

    for i_id, insect in insects_data.items():
        eaters = [b for b in bird_ids
                  if i_id in birds_data.get(b, {}).get("eats_insects", [])]
        if len(eaters) >= min_birds:
            clusters.append({
                "kind": "insect", "id": i_id,
                "name": insect.get("name", i_id),
                "icon": "🐛",
                "birds": eaters,
            })

    clusters.sort(key=lambda c: -len(c["birds"]))
    return clusters
