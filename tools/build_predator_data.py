"""GloBI の生データ(_data_predators_globi.json)から、図鑑「こわいもの」用の
配布データ `toris_collection/predator_data.py` を生成する。

なぜ種名でなく「分類カテゴリ」にするか:
  - GloBI の生の相手名は地域がバラバラ(ツバメの天敵にアルプスのイワドリが出る等)で、
    京都/シャーロットの庭の体験としては誠実さを損なう。
  - ロングテールに明らかな誤エッジ(魚・甲虫)が混ざる。
  - カテゴリ(タカのなかま/ヘビ/ネコ…)なら、実エッジを根拠にしたまま
    地域差とノイズに強く、ラベルも日英2つで済む。

実行: py -3 tools/build_predator_data.py
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "..", "toris_collection", "docs", "team",
                   "proposals", "_data_predators_globi.json")
OUT = os.path.join(HERE, "..", "toris_collection", "predator_data.py")

# 分類パスのトークン → カテゴリ。**上から順に**判定し、最初に当たったものを採る
# (Felidae を Carnivora より先に置く、Sciuridae を Rodentia より先に置く等、
#  具体的なものを先に)。ここに無い相手は「分類できない」として捨てる。
CATEGORY_RULES = [
    ("owl",      ("Strigiformes",)),
    ("falcon",   ("Falconidae", "Falconiformes")),
    ("raptor",   ("Accipitridae", "Accipitriformes")),
    ("shrike",   ("Laniidae",)),
    ("crow",     ("Corvidae",)),
    ("snake",    ("Serpentes",)),
    ("cat",      ("Felidae",)),
    ("raccoon",  ("Procyonidae",)),
    ("weasel",   ("Mustelidae",)),
    ("fox",      ("Canidae",)),
    ("squirrel", ("Sciuridae",)),
    ("rodent",   ("Rodentia",)),
]

# 1エッジ = 2レコードで返ってくるため、単発の孤立エッジ(=2)は落とし、
# 複数の独立した記録があるものだけを「こわいもの」として出す。
MIN_RECORDS = 4
# 出す数の上限(図鑑を賑やかにしない=静かなトーン)
MAX_CATEGORIES = 3


def classify(path: str) -> str | None:
    tokens = {x.strip() for x in (path or "").split("|")}
    for key, needles in CATEGORY_RULES:
        if tokens & set(needles):
            return key
    return None


def main():
    with open(RAW, encoding="utf-8") as f:
        raw = json.load(f)

    table = {}
    for bid, rec in sorted(raw.items()):
        cats = Counter()
        for p in rec.get("predators", []):
            key = classify(p.get("path", ""))
            if key:
                cats[key] += p.get("records", 0)
        kept = [(k, n) for k, n in cats.most_common() if n >= MIN_RECORDS]
        kept = kept[:MAX_CATEGORIES]
        if not kept:
            continue
        table[bid] = {
            "level": rec.get("level", "species"),
            "categories": [k for k, _ in kept],
            "records": {k: n for k, n in kept},
        }

    lines = [
        '"""predator_data.py - 図鑑「こわいもの」の実データ(自動生成)。',
        "",
        "GloBI (Global Biotic Interactions) の preyedUponBy 実エッジから生成。",
        "手で編集しない。更新するときは:",
        "    py -3 tools/globi_predator_pull.py      # GloBI から再取得",
        "    py -3 tools/build_predator_data.py      # このファイルを再生成",
        "",
        "level='genus' は、その種自体の記録が GloBI に無く、同属の近縁種の記録から",
        "採ったことを示す(誇張しないため区別して持つ。表示側で断りを添える)。",
        '"""',
        "from __future__ import annotations",
        "",
        "PREDATORS: dict[str, dict] = {",
    ]
    for bid, v in table.items():
        lines.append(f"    {bid!r}: {{")
        lines.append(f"        'level': {v['level']!r},")
        lines.append(f"        'categories': {v['categories']!r},")
        lines.append(f"        'records': {v['records']!r},")
        lines.append("    },")
    lines.append("}")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"saved: {os.path.abspath(OUT)}")
    print(f"天敵カテゴリを持つ鳥: {len(table)} / {len(raw)}")
    total = Counter()
    for v in table.values():
        for k in v["categories"]:
            total[k] += 1
    for k, n in total.most_common():
        print(f"  {k:9s} {n} 種")


if __name__ == "__main__":
    main()
