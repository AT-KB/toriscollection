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
import ecology  # noqa: E402
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

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"flock": flock_cases, "badges": badge_cases,
                   "ecology": eco, "guilds": guilds}, f,
                  ensure_ascii=False, indent=1)
    print(f"生態: {len(eco)} 組(37種の全ペア)")
    n = sum(len(c["sizes"]) for c in flock_cases)
    print(f"flock: {len(flock_cases)} 種 × {len(COUNTS)} 回 = {n} 通り")
    print(f"badges: {len(badge_cases)} 通り")
    print(f"-> {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
