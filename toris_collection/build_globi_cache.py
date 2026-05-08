"""
Toris Collection - GloBI キャッシュビルダー

初回のみ実行して、シードデータに登録された全鳥の相互作用を
GloBI API からダウンロード & ローカルキャッシュに保存する。

使い方:
  python build_globi_cache.py

結果:
  .globi_cache/ 以下に JSON ファイルが生成される
  .globi_summary.json に全鳥の取得結果サマリが保存される

実行時間の目安: 鳥20種 × 0.5秒ウェイト = 約20秒
"""
import json
import time
from pathlib import Path
from data import BIRDS
from globi_client import get_diet, get_diet_japan, CACHE_DIR


def main():
    print(f"GloBI キャッシュビルダー")
    print(f"対象鳥種: {len(BIRDS)} 種")
    print(f"キャッシュ保存先: {CACHE_DIR}")
    print("=" * 60)

    summary = {}
    start = time.time()

    for i, (b_id, bird) in enumerate(BIRDS.items(), 1):
        sci = bird.get("scientific")
        if not sci:
            print(f"[{i}/{len(BIRDS)}] {b_id}: 学名なし、スキップ")
            continue

        print(f"[{i}/{len(BIRDS)}] {bird['name']} ({sci})")

        # 全域(グローバル)と日本周辺の両方を取得
        global_diet = get_diet(sci)
        japan_diet = get_diet_japan(sci)

        summary[b_id] = {
            "name": bird["name"],
            "scientific": sci,
            "global_diet_count": len(global_diet),
            "japan_diet_count": len(japan_diet),
            "global_diet_sample": global_diet[:20],
            "japan_diet_sample": japan_diet[:20],
        }
        print(f"    全域 {len(global_diet)}件 / 日本周辺 {len(japan_diet)}件")

        # レート制限対策
        time.sleep(0.3)

    # サマリを保存
    summary_path = Path(__file__).parent / ".globi_summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start
    print("=" * 60)
    print(f"完了: {elapsed:.1f}秒")
    print(f"サマリ保存: {summary_path}")

    # 統計
    total_global = sum(s["global_diet_count"] for s in summary.values())
    total_japan = sum(s["japan_diet_count"] for s in summary.values())
    missing = [s["name"] for s in summary.values() if s["global_diet_count"] == 0]

    print(f"\n取得できた相互作用: 全域 {total_global} / 日本周辺 {total_japan}")
    if missing:
        print(f"GloBIにデータがない鳥: {', '.join(missing)}")


if __name__ == "__main__":
    main()
