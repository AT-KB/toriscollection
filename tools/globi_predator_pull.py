"""図鑑「こわいもの」の土台となる GloBI 実データ取得(原則4=生態に誠実)。

現行ロスター(species_loader.BIRDS)の全種について GloBI の preyedUponBy を引き、
「その鳥を実際に捕食する生き物」を記録件数つきで集計する。恣意的な天敵は作らない
= 本物の GloBI エッジだけを根拠にする。

猛禽(肉食鳥)拡張とは独立。天敵が図鑑内の鳥でなくても(ヘビ・ネコ・アライグマ等)
実データであれば「こわいもの」として誠実に出せる。

出力: toris_collection/docs/team/proposals/_data_predators_globi.json
実行: py -3 tools/globi_predator_pull.py
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import globi_client as gb          # noqa: E402
import species_loader as sl        # noqa: E402

# GloBI の「食われる側」視点の相互作用。preyedUponBy = 捕食された、が主。
INTERACTIONS = ["preyedUponBy"]

# 1種あたりの取得上限(GloBI の返却上限に合わせる)
LIMIT = 500


def pull(taxon: str, exclude: str = "") -> tuple[Counter, dict]:
    """taxon を起点に「食われた」エッジを引き、相手名の件数と分類パスを返す。"""
    counter: Counter = Counter()
    paths: dict[str, str] = {}
    for itype in INTERACTIONS:
        for row in gb.get_interactions(taxon, itype, limit=LIMIT):
            name = (row.get("target_taxon_name") or "").strip()
            if not name or name == exclude:
                continue
            counter[name] += 1
            # 分類パス(哺乳類/鳥類/爬虫類… の判定に使う)を控えておく
            p = row.get("target_taxon_path")
            if p and name not in paths:
                paths[name] = p
    return counter, paths


def main():
    results = {}
    for bid, b in sorted(sl.BIRDS.items()):
        sci = (b.get("scientific") or "").strip()
        if not sci:
            continue
        counter, paths = pull(sci, exclude=sci)
        level = "species"
        # 種レベルで GloBI にデータが無い鳥(日本の小鳥に多い)は、属レベルで引き直す。
        # 「近縁種の記録」として level=genus で区別し、誇張はしない(原則4)。
        genus = sci.split()[0]
        if not counter and genus and genus != sci:
            counter, paths = pull(genus, exclude=sci)
            if counter:
                level = "genus"
        results[bid] = {
            "bird_id": bid,
            "name": b.get("name"),
            "english": b.get("english"),
            "scientific": sci,
            "biome_pref": b.get("biome_pref") or [],
            "level": level,
            "n_records": sum(counter.values()),
            "predators": [
                {"taxon": n, "records": c, "path": paths.get(n, "")}
                for n, c in counter.most_common()
            ],
        }
        print(f"{bid:26s} {sci:34s} [{level:7s}] predators={len(counter):3d} "
              f"records={sum(counter.values())}")

    out_path = os.path.join(os.path.dirname(__file__), "..",
                            "toris_collection", "docs", "team", "proposals",
                            "_data_predators_globi.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"\nsaved: {os.path.abspath(out_path)}")

    covered = sum(1 for r in results.values() if r["predators"])
    print(f"天敵データのある鳥: {covered} / {len(results)}")


if __name__ == "__main__":
    main()
