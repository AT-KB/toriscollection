"""移植したロジックが Python 版と**同じ答えを返す**ことを、総当たりで確かめる。

手で書き写したテストは、書き写した人の思い込みも一緒に写る。そこで Python 版に
入力を総当たりで食わせ、その答えを表にして Dart 側に渡す。Dart はそれを再現
できるかだけを見る(差分テスト)。移植のズレ — 特に切り捨て除算・型変換・
境界の不等号 — はここで落ちる。

    py -3 tools/logic_fixtures.py     # toris_core/test/fixtures/logic.json を作る
    dart test                          # Dart 側が再現できるか
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import badges  # noqa: E402
import bird_profile as bp  # noqa: E402
import predators as pred  # noqa: E402
import absence_loop as absence  # noqa: E402
import eco_log  # noqa: E402
import ecology  # noqa: E402
import engine  # noqa: E402
import feeder_chain as fc  # noqa: E402
import garden_items as gi  # noqa: E402
import disturbance as dist  # noqa: E402
import data as seed  # noqa: E402
import flock  # noqa: E402
import i18n  # noqa: E402

# バッジの呼び名・一言は t() を通るため、生成時の表示言語で結果が変わる。
# 移植先(toris_core)は UI を持たない層なので**日本語の原文**を返す設計にした
# (訳を当てるのは表示側の仕事)。比べる相手も原文に揃えるため、ここで ja に固定する。
# これを忘れると、既定の en で作られた表を相手にして「移植がズレている」ように見える。
i18n.set_lang("ja")

OUT = os.path.join(os.path.dirname(__file__), "..", "toris_core", "test",
                   "fixtures", "logic.json")

# 種データの作り方の総当たり。Sheets 由来で型が揃わない現実を写している
# (数が文字列で来る、空文字、None、範囲外、など)。
BIRD_VARIANTS = [
    {},                                  # データ無し
    {"rarity": 0.0}, {"rarity": 0.39}, {"rarity": 0.4}, {"rarity": 0.69},
    {"rarity": 0.7}, {"rarity": 1.0},
    {"rarity": "0.5"}, {"rarity": "abc"}, {"rarity": None}, {"rarity": ""},
    {"flock_max": 1}, {"flock_max": 2}, {"flock_max": 3}, {"flock_max": 9},
    {"flock_max": 0}, {"flock_max": -5},
    {"flock_max": "2"}, {"flock_max": "abc"}, {"flock_max": None},
    {"flock_max": 2.7},
    {"flock_max": 2, "rarity": 0.9},     # flock_max が優先されること
    {"flock_max": "x", "rarity": 0.9},   # 読めない時は rarity に落ちること
]

COUNTS = [0, 1, 2, 3, 4, 5, 6, 8, 9, 30, -1, -100, "3", "abc", None, 2.9, True]

DAYS = [0, 1, 9, 10, 11, 29, 30, 31, 99, 100, 101, 1000, None]


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    flock_cases = []
    for i, bird in enumerate(BIRD_VARIANTS):
        data = {"x": bird}
        cap = flock.flock_cap("x", data)
        # 存在しない ID も見る(データ欠けはふつうに起きる)
        cap_missing = flock.flock_cap("nope", data)
        sizes = []
        for c in COUNTS:
            try:
                s = flock.flock_size("x", c, data)
            except Exception as e:
                s = f"ERROR:{type(e).__name__}"
            sizes.append({"count": c, "size": s})
        flock_cases.append({
            "bird": bird, "cap": cap, "cap_missing": cap_missing, "sizes": sizes,
        })

    badge_cases = []
    for d in DAYS:
        b = badges.badge_for_days(d)
        badge_cases.append({
            "days": d,
            "threshold": b["threshold"] if b else None,
            "icon": b["icon"] if b else None,
            # label は t() を通るので、日本語表示のときの原文と一致する
            "label": b["label"] if b else None,
            "message": badges.badge_message("コマドリ", d),
        })

    # 生態(共起ネットワーク): 実データ37種の**全ペア**で答えを出す。
    # 顔ぶれの選び方の根っこなので、1組でもズレると出てくる鳥が変わる。
    birds = seed.BIRDS
    ids = sorted(birds)
    eco = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            eco.append({
                "a": a, "b": b,
                "co": round(ecology.co_occurrence(a, b, birds), 12),
                "clim": round(ecology.climate_overlap(a, b, birds), 12),
                "diet": round(ecology.diet_jaccard(a, b, birds), 12),
            })
    guilds = {b: ecology.guild(b, birds) for b in ids}

    # 到来の仕組み: 実データで、植えた組み合わせ × 全12ヶ月 × 全37種。
    # 「植える→虫→鳥」はこの商品の背骨なので、ここがズレると別物になる。
    plant_sets = [
        [],
        ["sakura"],
        ["sakura", "kunugi"],
        ["himawari", "susuki", "sakura", "kunugi"],
        ["nonexistent_plant", "sakura"],
    ]
    arrivals = []
    for biome_id in sorted(seed.BIOMES):
        for pset in plant_sets:
            for month in range(1, 13):
                G, temp = engine.build_network(pset, biome_id, month)
                web = {
                    "plants": sorted(n for n, d in G.nodes(data=True)
                                     if d.get("kind") == "plant"),
                    "insects": sorted(n for n, d in G.nodes(data=True)
                                      if d.get("kind") == "insect"),
                }
                probs = {}
                for bid in ids:
                    r = engine.calculate_arrival_probability(bid, G, biome_id, month)
                    probs[bid] = [round(r["probability"], 12),
                                  round(r["food_score"], 12)]
                arrivals.append({
                    "biome": biome_id, "planted": pset, "month": month,
                    "temp": round(temp, 12), **web, "probs": probs,
                })

    # 餌台の連鎖(餌台 → リス → タカ → 警戒鳥の抑制)。
    # 餌台の置き方 × 植えた組み合わせを**総当たり**で。
    # ここは分岐が細かい(かご型だけならリスは届かない/堅果は地面なので届く)ので、
    # 手で書いたテストでは抜ける。
    feeder_sets = [
        [], ["feeder_open"], ["feeder_cage"],
        ["feeder_open", "feeder_cage"], ["nonexistent_feeder"],
        ["feeder_cage", "nonexistent_feeder"],
    ]
    fc_plant_sets = [
        [], ["sunflower"], ["white_oak"], ["sunflower", "white_oak"],
        ["sakura"], ["sakura", "sunflower"],
    ]
    # 警戒心は 0〜1 の外まで見る(データが汚れていても落ちないこと)
    wariness_values = [0.0, 0.25, 0.5, 0.55, 0.7, 1.0, -0.3, 1.4]

    feeder_cases = []
    for feats in feeder_sets:
        for pset in fc_plant_sets:
            r = fc.resolve(feats, pset)
            feeder_cases.append({
                "features": feats, "planted": pset,
                "foods": sorted(fc.available_foods(feats, pset)),
                "animals": r["animals"], "raptors": r["raptors"],
                "mult": {str(w): round(
                    fc.wary_arrival_multiplier(w, r["raptors"]), 12)
                    for w in wariness_values},
            })

    # 図鑑のプロフィール(好きなもの / 好きな場所 / こわいもの)。
    #
    # ⚠️ ここは私が **Dart 側に分類の表を手で書いて間違えた**ところ。
    # 実データが使う crow/falcon/fox/rodent/weasel が表に無く、逆に
    # mammal/corvid/other という存在しない分類を書いていた。表ごと突き合わせる。
    i18n.set_lang("en")   # 表示名は出荷済みの英語
    profile_cases = []
    for bid in ids:
        b = birds[bid]
        prof = bp.build(bid, b, seed.PLANTS, seed.INSECTS, seed.BIOMES)
        profile_cases.append({
            "bird": bid,
            "likes": [[x["kind"], x["id"]] for x in prof["likes"]],
            "home": [x["id"] for x in prof["home"]],
            "categories": prof["fears"]["categories"],
            "genus_level": prof["fears"]["genus_level"],
            "labels": pred.labels(bid),
            "has_data": pred.has_data(bid),
        })
    predator_labels = {k: i18n.t(v) for k, v in pred.CATEGORY_LABELS.items()}
    # 表に無い分類は静かに落ちること(データが汚れても知らない語を出さない)
    _dirty = {"zzz_unknown": {"categories": ["raptor", "zzz_unknown", "owl"],
                              "level": "genus"}}
    _saved_pred = pred.PREDATORS
    try:
        pred.PREDATORS = _dirty
        unknown_case = {"categories": pred.categories("zzz_unknown"),
                        "genus": pred.is_genus_level("zzz_unknown"),
                        "labels": pred.labels("zzz_unknown"),
                        "has_data": pred.has_data("zzz_unknown"),
                        "missing_bird": pred.categories("no_such_bird")}
    finally:
        pred.PREDATORS = _saved_pred
    i18n.set_lang("ja")

    # 「どうすればあの鳥が来るか」— network_stats / simulate / suggest。
    # 確率そのものではないが、確率の読み方を客に見せる部分なので同じ判定を移す。
    helper_cases = []
    for biome_id in sorted(seed.BIOMES):
        for pset in plant_sets:
            for month in (1, 5, 8, 11):
                G, _t = engine.build_network(pset, biome_id, month)
                st = engine.network_stats(G)
                hub = st["hub"]
                # 提案は全37種ぶん(順序も含めて比べる)
                sug = {}
                for bid in ids:
                    r = engine.suggest_for_bird(bid, pset, biome_id, month)
                    sug[bid] = {
                        "prob": round(r["current_prob"], 12),
                        "has_food_path": r["has_food_path"],
                        "items": [[x["plant_id"], x["directness"],
                                   x.get("insect_id")] for x in r["suggestions"]],
                    }
                helper_cases.append({
                    "biome": biome_id, "planted": pset, "month": month,
                    "stats": {"plants": st["n_plants"], "insects": st["n_insects"],
                              "birds_active": st["n_birds_active"],
                              "edges": st["n_edges"],
                              "hub": None if not hub else [hub[0], hub[1], hub[3]]},
                    "suggest": sug,
                })
    # 仮に1つ植えたら確率がどうなるか
    sim_cases = []
    for biome_id in sorted(seed.BIOMES):
        for cand in sorted(seed.PLANTS)[:6]:
            for bid in ids[:8]:
                sim_cases.append({
                    "biome": biome_id, "candidate": cand, "bird": bid,
                    "prob": round(engine.simulate_with_added_plant(
                        bid, ["sakura"], cand, biome_id, 5), 12),
                })

    # 中心性(Sony CSL の補正済み PageRank)によるレア度係数の上書き。
    #
    # ⚠️ 元データ(200-300MB)はリポジトリに無いので、ふだんは発動しない。
    # だが**式は移す**(CEO 2026-08-16「推測ではなく忠実に」)ので、ここで
    # `engine._CENTRALITIES` に値を注入して**実際に発動させ**、答えを取る。
    # そうしないと「発動しない道」しか比べられない。
    PR_VALUES = [
        1e-9,     # log10 = -9 → (−9+8)/5 = −0.2 → 下限 0.05 に張り付く
        1e-8,     # −8 → 0.0   → 0.05
        1e-7,     # −7 → 0.2
        1e-6,     # −6 → 0.4
        1e-5,     # −5 → 0.6
        1e-4,     # −4 → 0.8   → 上限 0.7 に張り付く
        1e-2,     # 上限
        0.0,      # 偽なので使わない → シードの rarity のまま
        -1e-6,    # 正でないので使わない
    ]
    cent_cases = []
    _saved = (engine._CENTRALITIES, engine._CENTRALITY_LOADED)
    try:
        engine._CENTRALITY_LOADED = True
        for pr in PR_VALUES:
            for corrected in (True, False):
                # corrected=True: pr_corrected を入れる / False: pr だけ
                table = {}
                for bid, b in birds.items():
                    sci = (b.get("scientific") or "").upper()
                    if not sci:
                        continue
                    table[sci] = ({"pr_corrected": pr, "pr": 1e-3}
                                  if corrected else {"pr": pr})
                engine._CENTRALITIES = table
                G, _t = engine.build_network(["sakura", "kunugi"], "kyoto", 5)
                probs = {}
                for bid in ids:
                    r = engine.calculate_arrival_probability(bid, G, "kyoto", 5)
                    probs[bid] = [round(r["probability"], 12),
                                  round(r["rarity_factor"], 12),
                                  r["centrality_used"]]
                cent_cases.append({"pr": pr, "corrected": corrected,
                                   "probs": probs})
        # 学名がキャッシュに無い場合(GloBI に居ない種)も見る
        engine._CENTRALITIES = {"NOT_A_REAL_TAXON": {"pr_corrected": 1e-6}}
        G, _t = engine.build_network(["sakura", "kunugi"], "kyoto", 5)
        cent_cases.append({
            "pr": None, "corrected": None,
            "probs": {bid: [
                round(engine.calculate_arrival_probability(
                    bid, G, "kyoto", 5)["probability"], 12),
                round(engine.calculate_arrival_probability(
                    bid, G, "kyoto", 5)["rarity_factor"], 12),
                None] for bid in ids},
        })
    finally:
        engine._CENTRALITIES, engine._CENTRALITY_LOADED = _saved

    # 今日の庭アイテム(garden_items)。到来確率と退去率に効く部分。
    from datetime import datetime, timedelta
    item_cases = []
    for item_id in gi.ITEMS:
        for biome_id in sorted(seed.BIOMES):
            item_cases.append({
                "item": item_id, "biome": biome_id,
                "targets": sorted(gi.target_bird_ids(item_id, biome_id, birds)),
                "available": gi.is_available(item_id, biome_id, birds),
                "effect_kind": gi.ITEMS[item_id]["effect_kind"],
                "value": gi.ITEMS[item_id]["value"],
            })
    # 効いている/切れている の境目。**両端を含む**ことまで見る。
    _placed = datetime(2026, 8, 16, 9, 0, 0)
    _plc = gi.place_item("feeder", now=_placed)
    active_cases = []
    for delta in [-1, 0, 1, 3600, 6 * 3600 - 1, 6 * 3600, 6 * 3600 + 1]:
        at = _placed + timedelta(seconds=delta)
        active_cases.append({
            "offset_sec": delta,
            "active": gi.is_active(_plc, at),
            "hours_left": round(gi.hours_remaining(_plc, at), 9),
        })
    bonus_cases = []
    for item_id in gi.ITEMS:
        plc = gi.place_item(item_id, now=_placed)
        at = _placed + timedelta(hours=1)
        fn = gi.make_arrival_bonus_fn(plc, "charlotte", birds, at)
        bonus_cases.append({
            "item": item_id,
            "arrival": {bid: round(fn(bid), 12) for bid in ids},
            "departure": round(gi.departure_bonus(plc, at), 12),
            "boosted": sorted(b for b in ids
                              if gi.is_item_boosted_arrival(
                                  b, plc, "charlotte", birds, at)),
            # 期限切れなら全部ゼロに戻ること
            "expired_departure": round(
                gi.departure_bonus(plc, _placed + timedelta(hours=7)), 12),
        })
    item_bundle = {"targets": item_cases, "active": active_cases,
                   "bonus": bonus_cases, "duration_hours": gi.DURATION_HOURS}

    # 「なぜ来たか」の記録(eco_log)。重複除去と並びが肝。
    # 同じ鳥の同じ理由は1件だけ、というのが「関係の証拠」の意味を保つ。
    eco_log_cases = []
    _evs = [
        {"bird_id": "a", "reason_text": "X", "arrived_at": "2026-08-01T10:00:00"},
        {"bird_id": "a", "reason_text": "X", "arrived_at": "2026-08-02T10:00:00"},
        {"bird_id": "a", "reason_text": "Y", "arrived_at": "2026-08-03T10:00:00"},
        {"bird_id": "b", "reason_text": "X", "arrived_at": "2026-07-01T10:00:00"},
        {"bird_id": "", "reason_text": "Z", "arrived_at": "2026-08-04T10:00:00"},
        {"bird_id": "c", "reason_text": "", "arrived_at": "2026-08-05T10:00:00"},
        {"bird_id": "d", "reason_text": "W", "arrived_at": None},
    ]
    for n in range(len(_evs) + 1):
        log = eco_log.append_events(None, _evs[:n])
        # 二度同じものを流し込んでも増えないこと(重複除去の要)
        twice = eco_log.append_events(log, _evs[:n])
        eco_log_cases.append({
            "n": n, "log": log, "twice_len": len(twice),
            "for_a": eco_log.entries_for_bird(log, "a"),
            "for_missing": eco_log.entries_for_bird(log, "zzz"),
        })
    founding_cases = []
    _log = eco_log.append_events(None, _evs)
    _ents = eco_log.entries_for_bird(_log, "a")
    for first in ["2026-08-01T00:00:00", None, ""]:
        founding_cases.append({
            "observed_first": first,
            "flags": [eco_log.is_founding_record(e, _ents, first)
                      for e in _ents],
            # 記録が空なら常に False
            "empty": eco_log.is_founding_record(
                {"bird_id": "a", "text": "X"}, [], first),
        })

    # 「なぜ来たか」の一文。**実データで全37種 × 植生 × 月**を総当たり。
    # 一番重みの大きい経路を1つだけ採る、という判断がズレると文が変わる。
    #
    # ⚠️ ここだけ表示言語を en に切り替える。バッジ(上)は日本語の原文を
    # 移植先に持たせる設計だが、「なぜ来たか」は**画面にそのまま出る文**で、
    # アプリは全部英語。移植先も出荷済みの英語をそのまま持つ。
    i18n.set_lang("en")
    reason_cases = []
    for biome_id in sorted(seed.BIOMES):
        for pset in plant_sets:
            for month in (1, 5, 8, 11):
                G, _temp = engine.build_network(pset, biome_id, month)
                for bid in ids:
                    info = engine.calculate_arrival_probability(
                        bid, G, biome_id, month)
                    text, plant, insect = absence.build_reason_text(bid, info)
                    reason_cases.append({
                        "biome": biome_id, "planted": pset, "month": month,
                        "bird": bid, "text": text,
                        "plant": plant, "insect": insect,
                    })

    i18n.set_lang("ja")   # 後続に影響させない

    # 撹乱: 乱数列は Python と Dart で違うので、結果そのものは突き合わせられない。
    # 代わりに**定数と判定の境目**を運ぶ(Dart 側は乱数を差し替えて境目を試す)。
    dist_consts = {
        "base_p": dist.BASE_DISTURBANCE_P,
        "weights": dict(dist.TYPE_WEIGHTS),
        "severity": {k: v["severity"] for k, v in dist.DISTURBANCES.items()},
        "default_sensitivity": dist.DEFAULT_SENSITIVITY,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"flock": flock_cases, "badges": badge_cases,
                   "ecology": eco, "guilds": guilds, "arrivals": arrivals,
                   "feeder_chain": feeder_cases,
                   "centrality": cent_cases, "garden_items": item_bundle,
                   "helpers": helper_cases, "simulate": sim_cases,
                   "profiles": profile_cases,
                   "predator_labels": predator_labels,
                   "predator_unknown": unknown_case,
                   "eco_log": eco_log_cases, "founding": founding_cases,
                   "reasons": reason_cases,
                   "disturbance": dist_consts}, f,
                  ensure_ascii=False, indent=1)
    nf = len(feeder_cases) * len(wariness_values)
    print(f"図鑑プロフィール: {len(profile_cases)} 種 / "
          f"天敵の分類 {len(predator_labels)} 種類")
    print(f"食物網の統計と提案: {len(helper_cases)} 状況 / "
          f"仮植え: {len(sim_cases)} 通り")
    print(f"中心性: {len(cent_cases)} 状況 × {len(ids)}種")
    print(f"庭アイテム: 対象{len(item_cases)} / 期限{len(active_cases)} / "
          f"加点{len(bonus_cases)}")
    print(f"なぜ来たか: {len(reason_cases)} 通り / 記録: {len(eco_log_cases)} 段階")
    print(f"餌台の連鎖: {len(feeder_cases)} 状況 × 警戒心{len(wariness_values)}通り "
          f"= {nf} 通り")
    print(f"生態: {len(eco)} 組(37種の全ペア)")
    print(f"到来: {len(arrivals)} 状況 × {len(ids)}種 = {len(arrivals)*len(ids)} 通り")
    n = sum(len(c["sizes"]) for c in flock_cases)
    print(f"flock: {len(flock_cases)} 種 × {len(COUNTS)} 回 = {n} 通り")
    print(f"badges: {len(badge_cases)} 通り")
    print(f"-> {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
