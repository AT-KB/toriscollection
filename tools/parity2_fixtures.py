"""まだ Python と突き合わせていなかった移植を、同じ入力で比べる表を作る(2026-11-10)。

`tools/migration_audit.py` が「移した(うち突き合わせ無し 32)」と出していたうち、
**計算をする関数**をここで比べる(画面の部品は実機で確かめる)。

    py -3 tools/parity2_fixtures.py   # toris_core/test/fixtures/parity2.json を作る
    dart test test/parity2_test.dart  # Dart が同じ答えを出せるか

やり方は `logic_fixtures.py` と同じ。Python 版に入力を総当たりで食わせ、
答えを表にして Dart に渡す。手で期待値を書かない。
"""
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "toris_collection"))

import absence_loop  # noqa: E402
import ads  # noqa: E402
import bird_profile  # noqa: E402
import centrality  # noqa: E402
import data  # noqa: E402
import disturbance  # noqa: E402
import ecology  # noqa: E402
import engine  # noqa: E402
import feeder_chain as fc  # noqa: E402
import save_code  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "toris_core", "test",
                   "fixtures", "parity2.json")


def main() -> None:
    out = {}

    # ── engine.temperature_fit ─────────────────────────────────────
    ranges = [list(v["temp_fit"]) for v in data.BIRDS.values() if v.get("temp_fit")]
    ranges += [list(v["temp_fit"]) for v in data.PLANTS.values() if v.get("temp_fit")]
    ranges = [list(r) for r in {tuple(r) for r in ranges}]
    ranges += [[5, 5], [10, 0], [-5, 30]]
    temps = [t / 2 for t in range(-30, 90, 3)]
    out["temperature_fit"] = [
        {"temp": t, "range": r, "want": engine.temperature_fit(t, tuple(r))}
        for r in sorted(ranges) for t in temps
    ]

    # ── engine.current_temperature ─────────────────────────────────
    out["current_temperature"] = [
        {"biome": b, "month": m, "want": engine.current_temperature(b, m)}
        for b in data.BIOMES for m in range(1, 13)
    ]

    # ── ecology.co_occurrence_matrix ───────────────────────────────
    kyoto = [b for b, v in data.BIRDS.items() if "kyoto" in v.get("biome_pref", [])]
    char = [b for b, v in data.BIRDS.items() if "charlotte" in v.get("biome_pref", [])]
    lists = [kyoto[:6], char[:6], kyoto[:3] + char[:3], kyoto, []]
    out["co_occurrence_matrix"] = [
        {"ids": ids, "want": ecology.co_occurrence_matrix(ids, data.BIRDS)}
        for ids in lists
    ]

    # ── feeder_chain.animals_present / raptors_present ─────────────
    feats = [[], ["feeder_open"], ["feeder_cage"], ["feeder_open", "feeder_cage"]]
    plants = [[], list(data.PLANTS)[:4], ["sunflower"], ["oak"], ["sakura", "kaki"]]
    rows = []
    for f in feats:
        for p in plants:
            for baffled in (False, True):
                a = fc.animals_present(f, p, baffled)
                rows.append({"features": f, "plants": p, "baffled": baffled,
                             "animals": a, "raptors": fc.raptors_present(a)})
    out["feeder_chain"] = rows

    # ── bird_profile.likes / home / fears ──────────────────────────
    prof = []
    for bid, b in data.BIRDS.items():
        prof.append({
            "id": bid,
            "likes": [[x["kind"], x["id"]] for x in bird_profile.likes(b, data.PLANTS, data.INSECTS)],
            "home": [x["id"] for x in bird_profile.home(b, data.BIOMES)],
            "fears": bird_profile.fears(bid),
        })
    out["bird_profile"] = prof

    # ── disturbance.plant_sensitivity ──────────────────────────────
    pd = {"a": {"disturbance_sensitivity": 0.2}, "b": {"disturbance_sensitivity": 1.7},
          "c": {"disturbance_sensitivity": -1}, "d": {"disturbance_sensitivity": "0.3"},
          "e": {"disturbance_sensitivity": "x"}, "f": {}}
    out["plant_sensitivity"] = {
        "plants": pd,
        "cases": [{"id": k, "want": disturbance.plant_sensitivity(k, pd)}
                  for k in list(pd) + ["missing"]],
        # 出荷している植物データでの値(今は全部既定値になる)
        "real": {k: disturbance.plant_sensitivity(k, data.PLANTS) for k in data.PLANTS},
    }

    # ── centrality.get_centrality ──────────────────────────────────
    cent = {"PARUS MINOR": {"pr": 1e-5, "pr_corrected": 2e-5},
            "ZOSTEROPS JAPONICUS": {"pr": 3e-6},
            "EMPTY": {}}
    out["centrality"] = {
        "table": cent,
        "cases": [{"name": n, "corrected": c, "want": centrality.get_centrality(n, cent, c)}
                  for n in ["Parus minor", "zosterops japonicus", "Missing", "EMPTY"]
                  for c in (True, False)],
    }

    # ── absence_loop.parse_iso ─────────────────────────────────────
    isos = ["2026-11-10T08:30:00", "2026-11-10T08:30:00.123456", "2026-11-10",
            "", None, "abc", "2026-13-01T00:00:00"]
    out["parse_iso"] = []
    for s in isos:
        d = absence_loop.parse_iso(s)
        out["parse_iso"].append({"in": s, "want": d.isoformat() if d else None})

    # ── ads.has_claimed_today / mark_claimed_today ─────────────────
    today = date(2026, 11, 10)
    st = {}
    ads.mark_claimed_today(st, "k", today)
    out["claimed_today"] = {
        "today": "2026-11-10",
        "marked": st["k"],
        "cases": [{"stored": v, "want": ads.has_claimed_today({"k": v}, "k", today)}
                  for v in ["2026-11-10", "2026-11-09", "", None]],
    }

    # ── save_code.encode_current_state ─────────────────────────────
    state = {"biome": "kyoto", "planted": ["sakura", "kaki"], "feeders": ["feeder_cage"],
             "residents": ["mejiro"], "discovered": ["mejiro", "shijukara"],
             "observed": {"mejiro": {"count": 3}},
             "bird_days": {"mejiro": {"days": 2, "last": "2026-11-09"}}}
    now = datetime(2026, 11, 10, 8, 30, 0)
    out["encode_current_state"] = {
        "state": state, "now": now.isoformat(),
        "code": save_code.encode_current_state(state, now),
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"wrote {OUT}: " + ", ".join(f"{k} {len(v) if isinstance(v, list) else ''}".strip()
                                        for k, v in out.items()))


if __name__ == "__main__":
    main()
