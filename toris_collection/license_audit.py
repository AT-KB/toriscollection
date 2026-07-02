"""
license_audit.py - 使用中の鳴き声録音の CC ライセンスを集計する。

広告つき=商用アプリでは、xeno-canto の CC BY-NC(非商用)録音は使えない。
各種について「商用可(CC0 / CC BY / BY-SA / BY-ND / パブリックドメイン)の
録音が1本でもあるか」を調べ、商用モードで鳴かせられる種を把握する。

I/O は xc_client 経由(APIキーは Streamlit secrets / 環境変数から)。
結果は「商用可の種 / NCしか無い種 / 音源なしの種」に振り分ける。
"""
from __future__ import annotations

import xc_client


def species_license_summary(scientific_name: str) -> dict:
    """1種について song/call × A/B の録音を集め、ライセンス内訳を返す。"""
    seen: dict[str, str] = {}
    for stype in ("song", "call"):
        for q in ("A", "B"):
            for r in xc_client.search_recordings(
                scientific_name, quality=q, sound_type=stype
            ):
                rid = r.get("id")
                if rid and rid not in seen:
                    lic = r.get("lic") or r.get("license") or ""
                    seen[rid] = xc_client.license_class(lic)
    counts = {"commercial": 0, "noncommercial": 0, "unknown": 0}
    for cls in seen.values():
        counts[cls] += 1
    return {
        "total": len(seen),
        "counts": counts,
        # 商用可の録音が1本でもあれば、商用モードでも鳴かせられる
        "commercial_ok": counts["commercial"] > 0,
    }


def audit(birds_data: dict) -> list[dict]:
    """scientific を持つ全種のライセンス監査。1件ずつ dict のリストで返す。"""
    rows = []
    for bid, b in birds_data.items():
        sci = b.get("scientific")
        if not sci:
            continue
        summ = species_license_summary(sci)
        rows.append({
            "id": bid,
            "name": b.get("name", bid),
            "scientific": sci,
            **summ,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    """監査結果を集計。商用モードでの鳴き声カバー率を返す。"""
    total = len(rows)
    commercial = [r for r in rows if r["commercial_ok"]]
    nc_only = [r for r in rows if not r["commercial_ok"] and r["total"] > 0]
    no_audio = [r for r in rows if r["total"] == 0]
    return {
        "total_species": total,
        "commercial_ok": len(commercial),
        "nc_only": len(nc_only),
        "no_audio": len(no_audio),
        "coverage_pct": round(100 * len(commercial) / total, 1) if total else 0.0,
        "nc_only_names": [r["name"] for r in nc_only],
        "no_audio_names": [r["name"] for r in no_audio],
    }
