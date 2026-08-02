"""肉食鳥(猛禽)拡張の企画提案の"生態に誠実"な土台を作るためのGloBI実データ取得。

species_expand.py が挙げた猛禽3種について GloBI の preysOn / eats を引き、
現行の鳥ロスター(species_loader.BIRDS)のうち「実際に襲われる種」を突き合わせる。
恣意的な"なぜ来たか"は作らない=本物の GloBI エッジだけを根拠にする(原則4)。

出力: toris_collection/docs/team/proposals/_data_raptor_globi.json(生データ+突合結果)
実行: py -3 tools/globi_raptor_pull.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import globi_client as gb          # noqa: E402
import species_loader as sl        # noqa: E402

RAPTORS = [
    ("Accipiter cooperii", "クーパーハイタカ / Cooper's Hawk", "charlotte"),
    ("Buteo jamaicensis", "アカオノスリ / Red-tailed Hawk", "charlotte"),
    ("Accipiter gularis", "ツミ / Japanese Sparrowhawk", "kyoto"),
]


def roster_birds(biome):
    """(bird_id, en, sci) のリスト。指定バイオームに来る鳥。"""
    out = []
    for bid, b in sl.BIRDS.items():
        if biome in (b.get("biome_pref") or []):
            sci = b.get("scientific") or ""
            if sci:
                out.append((bid, b.get("english") or b.get("name"), sci))
    return out


def matches(prey_name, sci):
    """GloBI の相手名 prey_name が、ロスター種 sci(=Genus species)に該当するか。
    属レベル/亜種レベルの表記ゆれを吸収する。"""
    p = prey_name.strip()
    genus = sci.split()[0]
    return (
        p == genus or
        p.startswith(sci) or          # 亜種(sci + subsp)
        sci.startswith(p) or          # 相手が "Genus species" まで
        p.startswith(genus + " ")     # 同属の別種は「同属だが別種」候補
    )


def main():
    results = []
    for sci, label, biome in RAPTORS:
        preys = sorted({r.get("target_taxon_name") for r in
                        gb.get_interactions(sci, "preysOn", limit=200)
                        if r.get("target_taxon_name")})
        eats = sorted({r.get("target_taxon_name") for r in
                       gb.get_interactions(sci, "eats", limit=200)
                       if r.get("target_taxon_name")})
        all_targets = sorted(set(preys) | set(eats))
        roster = roster_birds(biome)
        hits = []  # (bird_id, en, sci, matched_globi_name, exact_or_genus)
        for bid, en, bsci in roster:
            for tgt in all_targets:
                if matches(tgt, bsci):
                    exact = tgt.startswith(bsci) or bsci.startswith(tgt)
                    hits.append({
                        "bird_id": bid, "en": en, "sci": bsci,
                        "globi_match": tgt,
                        "level": "species" if exact else "genus",
                    })
                    break
        results.append({
            "raptor_sci": sci, "raptor_label": label, "biome": biome,
            "n_preysOn": len(preys), "n_eats": len(eats),
            "roster_prey_hits": hits,
            "sample_preysOn": preys[:25],
        })
    out_path = os.path.join(os.path.dirname(__file__), "..",
                            "toris_collection", "docs", "team", "proposals",
                            "_data_raptor_globi.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    # コンソール要約(ascii安全)
    for r in results:
        print(f"\n### {r['raptor_label']} [{r['biome']}]  preysOn={r['n_preysOn']} eats={r['n_eats']}")
        if r["roster_prey_hits"]:
            for h in r["roster_prey_hits"]:
                print(f"   HIT {h['en']:24s} ({h['sci']})  <- GloBI:{h['globi_match']} [{h['level']}]")
        else:
            print("   (現行ロスターに一致する獲物なし)")
    print(f"\nsaved: {os.path.abspath(out_path)}")


if __name__ == "__main__":
    main()
