"""
ecology.py - 鳥どうしの「共起しやすさ」を生態学的に計算する

■ 設計の根拠(科学的背景)
  競争排除則(Gause 1934): ニッチが完全に重なる2種は共存できない。
  → だから「同じ餌を分け合う鳥=仲良し」は誤り。餌が同一なら競争相手。
  共存はニッチ分割(採餌高度・嘴サイズ・時間帯のずらし)によって成立する。

  種共起ネットワーク(co-occurrence network)の実証研究によれば、
  正の共起(=よく一緒に見られる)を駆動するのは
    ① 同じ生息環境を好むこと(environmental filtering)
    ② 同じ採餌ギルドに属すること(ただしニッチは分割している)
  であって、同一資源の奪い合いではない。
  完全に資源が重なるペアはむしろ競争で排除しあう。

■ このモジュールの共起スコア
    co_occurrence(A,B) = 気候ニッチ重なり × ギルド係数 × 競争抑制
  - 気候ニッチ重なり: temp_fit レンジの重なり(環境フィルタリング)
  - ギルド係数: 同ギルドなら高く、異ギルドなら下げる
  - 競争抑制: 餌がほぼ同一(Jaccard>0.7)なら下げる(競争排除)

  「分け合う」ではなく「関係が強い/よく一緒に見られる」を表す観察的な指標。

food web は data.py に符号化されている(PLANTS/INSECTS/BIRDS)。
このモジュールは表示にもUIにも依存しない純粋計算だけを持つ。
"""
from __future__ import annotations

# 採餌ギルド(同じギルド=同じ「採餌のしかた」の仲間。共起の正の駆動要因)
GUILD_LABELS = {
    "insectivore": ("🐛", "虫を追う"),
    "herbivore":   ("🍇", "木の実・花の蜜を好む"),
    "omnivore":    ("🍃", "なんでも食べる"),
    "other":       ("🐦", "その他"),
}


def guild(bird_id: str, birds_data: dict) -> str:
    """鳥の採餌ギルドを diet から導出する。"""
    bird = birds_data.get(bird_id, {})
    has_i = bool(bird.get("eats_insects"))
    has_p = bool(bird.get("eats_plants"))
    if has_i and has_p:
        return "omnivore"
    if has_i:
        return "insectivore"
    if has_p:
        return "herbivore"
    return "other"


def climate_overlap(bird_a: str, bird_b: str, birds_data: dict) -> float:
    """temp_fit レンジの重なり(0..1)。環境フィルタリングの指標。"""
    fa = birds_data.get(bird_a, {}).get("temp_fit")
    fb = birds_data.get(bird_b, {}).get("temp_fit")
    if not fa or not fb:
        return 0.0
    la, ha = fa
    lb, hb = fb
    inter = max(0.0, min(ha, hb) - max(la, lb))
    union = max(ha, hb) - min(la, lb)
    return inter / union if union > 0 else 0.0


def diet_jaccard(bird_a: str, bird_b: str, birds_data: dict) -> float:
    """餌(植物+昆虫)の Jaccard 類似度。1に近いほどニッチが同一=競争。"""
    a = birds_data.get(bird_a, {})
    b = birds_data.get(bird_b, {})
    sa = set(a.get("eats_plants", [])) | set(a.get("eats_insects", []))
    sb = set(b.get("eats_plants", [])) | set(b.get("eats_insects", []))
    if not (sa | sb):
        return 0.0
    return len(sa & sb) / len(sa | sb)


def co_occurrence(bird_a: str, bird_b: str, birds_data: dict) -> float:
    """2羽の「よく一緒に見られる度」(0..1)。

    = 気候ニッチ重なり × ギルド係数 × 競争抑制
    """
    if bird_a == bird_b:
        return 0.0
    clim = climate_overlap(bird_a, bird_b, birds_data)
    g = 1.0 if guild(bird_a, birds_data) == guild(bird_b, birds_data) else 0.45
    j = diet_jaccard(bird_a, bird_b, birds_data)
    # 競争排除: 餌がほぼ同一(J>0.7)なら線形に抑制(J=1 で 0.3 倍)
    comp = 1.0 - 0.7 * max(0.0, j - 0.7) / 0.3
    return clim * g * comp


def co_occurrence_matrix(bird_ids: list[str], birds_data: dict) -> list[list[float]]:
    """共起しやすさの対称行列(自己=0)。呼応の相手選びに使う。"""
    n = len(bird_ids)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = co_occurrence(bird_ids[i], bird_ids[j], birds_data)
            mat[i][j] = mat[j][i] = c
    return mat


def pick_lineup(candidate_ids: list[str], birds_data: dict, k: int, rng,
                base_weight: dict | None = None) -> list[str]:
    """共起ネットワークに沿って「今日の顔ぶれ」を選ぶ。

    純粋ランダムではなく、すでに選ばれた鳥と共起しやすい鳥を引きやすくする。
    こうして「関係の強い鳥たちが揃う」コヒーレントな顔ぶれになる。

    base_weight: 鳥ID→基礎重み(観察回数など。よく会う鳥ほど出やすくする用)。
    """
    cand = list(candidate_ids)
    if len(cand) <= k:
        return cand
    bw = base_weight or {}

    def _weighted_pick(items, weights):
        total = sum(weights)
        if total <= 0:
            return rng.choice(items)
        r = rng.random() * total
        acc = 0.0
        for it, w in zip(items, weights):
            acc += w
            if r <= acc:
                return it
        return items[-1]

    remaining = list(cand)
    # 種(seed)は基礎重みで選ぶ(=今日の庭の「主役」)
    seed = _weighted_pick(remaining, [bw.get(b, 1.0) for b in remaining])
    chosen = [seed]
    remaining.remove(seed)

    while len(chosen) < k and remaining:
        weights = []
        for b in remaining:
            co = max(co_occurrence(b, c, birds_data) for c in chosen)
            # 0.25 の下駄で、関係の薄い鳥もたまには混じる(単調さの回避)
            weights.append(bw.get(b, 1.0) * (0.25 + co))
        pick = _weighted_pick(remaining, weights)
        chosen.append(pick)
        remaining.remove(pick)

    return chosen


def guild_groups(bird_ids: list[str], birds_data: dict) -> list[dict]:
    """顔ぶれをギルドごとにまとめる(表示用)。

    Returns: [{"guild", "icon", "label", "birds": [bird_id...]}, ...]
             2羽以上いるギルドだけ、人数の多い順。
    """
    from collections import defaultdict
    by_guild: dict[str, list[str]] = defaultdict(list)
    for b in bird_ids:
        by_guild[guild(b, birds_data)].append(b)
    groups = []
    for g, members in by_guild.items():
        if len(members) < 2:
            continue
        icon, label = GUILD_LABELS.get(g, GUILD_LABELS["other"])
        groups.append({"guild": g, "icon": icon, "label": label, "birds": members})
    groups.sort(key=lambda x: -len(x["birds"]))
    return groups
