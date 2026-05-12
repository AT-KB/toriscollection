"""
xeno-canto に各鳥の音源があるかを一覧化するスクリプト。

使い方:
  py -m streamlit run app.py で実機ローカル起動できる状態で、
  ターミナルで:
    cd toris_collection
    py check_xeno_canto_coverage.py

  実行すると、各鳥の音源カバレッジ(あり/なし、件数)を表示。
"""
from __future__ import annotations
import sys
import json
import time
from pathlib import Path

# プロジェクト直下から実行する前提
sys.path.insert(0, str(Path(__file__).parent))

from data import BIRDS, BIOMES
from xc_client import search_recordings, is_enabled


def main():
    if not is_enabled():
        print("⚠️ xc_api_key.txt が見つかりません。xeno-canto APIキーが必要です。")
        print("   1. https://xeno-canto.org/account/register で登録")
        print("   2. https://xeno-canto.org/account/api-key でキー取得")
        print("   3. xc_api_key.txt にキーだけ1行で保存")
        return

    print(f"# Toris Collection - xeno-canto 音源カバレッジ")
    print(f"## 対象鳥数: {len(BIRDS)}")
    print()

    results = []
    for bird_id, bird in BIRDS.items():
        sci = bird.get("scientific")
        if not sci:
            results.append({
                "id": bird_id, "name": bird["name"],
                "scientific": "", "status": "no_scientific",
                "count": 0,
            })
            continue

        # API 呼び出し(複数の品質フォールバックで確認)
        recordings = search_recordings(sci, quality="A", sound_type="song")
        if not recordings:
            recordings = search_recordings(sci, quality="A", sound_type="call")
        if not recordings:
            recordings = search_recordings(sci, quality="B", sound_type="song")
        if not recordings:
            recordings = search_recordings(sci, quality="B", sound_type="call")

        count = len(recordings)
        status = "ok" if count > 0 else "no_audio"

        # バイオーム情報
        biomes = bird.get("biome_pref", [])
        biome_names = [BIOMES[b]["name"] for b in biomes if b in BIOMES]

        results.append({
            "id": bird_id, "name": bird["name"],
            "scientific": sci, "status": status, "count": count,
            "biomes": ",".join(biome_names),
        })

        # 進捗
        emoji = "✅" if status == "ok" else "❌"
        print(f"  {emoji} {bird['name']:25s} ({sci:35s}) → {count} 件")

        # レート制限対策(キャッシュなしの場合のみ意味あり)
        time.sleep(0.3)

    print()
    print("===== サマリ =====")
    ok = [r for r in results if r["status"] == "ok"]
    no_audio = [r for r in results if r["status"] == "no_audio"]

    print(f"音源あり: {len(ok)} 種")
    print(f"音源なし: {len(no_audio)} 種")
    print()

    if no_audio:
        print("===== 音源なしの鳥(対処要検討) =====")
        for r in no_audio:
            print(f"  - {r['name']} ({r['scientific']}) [{r['biomes']}]")
        print()
        print("対処案:")
        print("  A. このまま残す(図鑑では「録音なし」表示)")
        print("  B. 別の音源がある同地域の近縁種に差し替え")
        print("  C. データを残しつつ、音源だけプレースホルダーを用意")

    # JSON 出力
    out_path = Path(__file__).parent / "xc_coverage_report.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n詳細レポート: {out_path}")


if __name__ == "__main__":
    main()
