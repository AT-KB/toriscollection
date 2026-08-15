"""種データを JSON に書き出して Flutter 版に渡す。

移行の方針: **判断のロジックは Dart に写すが、データは写さない**。
`data.py` のシードをそのまま JSON にして持っていく。ここを手で書き直すと、
写し間違いが静かに紛れ込む(37種 × 12項目)。

出力: `toris_app/assets/data/birds.json`

    py -3 tools/export_data.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import data  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..",
                   "toris_app", "assets", "data", "birds.json")

# Flutter 版で使う項目だけ。表示は英語のみなので、日本語の名前と説明は運ばない
# (製品版は 2026-08-09 に日本語表示を落としている)。
FIELDS = ("scientific", "english", "description_en", "color",
          "eats_plants", "eats_insects", "temp_fit", "biome_pref",
          "rarity", "wariness")


def main() -> None:
    birds = data.BIRDS
    items = birds.items() if isinstance(birds, dict) else \
        ((b["id"], b) for b in birds)

    out = {}
    for bid, b in items:
        out[bid] = {k: b[k] for k in FIELDS if k in b}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)

    missing = {k for b in out.values() for k in FIELDS} - set(FIELDS)
    n_diet = sum(1 for b in out.values() if b.get("eats_insects") or b.get("eats_plants"))
    print(f"{len(out)}種 -> {os.path.abspath(OUT)}")
    print(f"  食べ物のデータがある種: {n_diet}")
    print(f"  温度域(temp_fit)がある種: {sum(1 for b in out.values() if b.get('temp_fit'))}")
    if missing:
        print("  !! 未知のキー:", missing)


if __name__ == "__main__":
    main()
