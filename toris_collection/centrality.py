"""
Toris Collection - Sony CSL 補正済み中心性データセットローダ

Funabashi et al. (2024) が GloBI に Scale-Free 補正を適用したデータセット。
https://github.com/SonyCSL/MMS-open-datasets/wiki

生データの中心性は「有名な種ほど大きく出る」サンプリングバイアスを持つため、
べき分布フィッティングで補正した値が提供されている。
Toris Collection では、鳥のレア度係数を補正済みPageRankから計算することで、
「データが少ないだけのマイナー種」を不当に不利にしない確率計算ができる。

使い方:
  1. https://d38f5mdcvtp0z3.cloudfront.net/interaction_with_centrality_corrected.tsv.xz
     をダウンロード (約200-300MB 圧縮済み)
  2. このモジュール同階層に配置
  3. load_centralities() を呼ぶ

ライセンス: CC BY 4.0
出典: Funabashi, M. et al. (2024) "Scale-Free Correction of Under-/Over-Reported
      Biases in Global Biotic Interaction Network" IEEE WCCS 2024
"""
from __future__ import annotations
import lzma
import csv
import sys
from pathlib import Path
from typing import Optional


DATASET_FILE = Path(__file__).parent / "interaction_with_centrality_corrected.tsv.xz"
DATASET_URL = (
    "https://d38f5mdcvtp0z3.cloudfront.net/"
    "interaction_with_centrality_corrected.tsv.xz"
)
# 初回スキャン結果のキャッシュ(鳥20種分の中心性だけを小さなJSONに保存)
CACHE_FILE = Path(__file__).parent / ".centrality_cache.json"


def is_available() -> bool:
    """補正済みデータセットがローカルにあるか"""
    return DATASET_FILE.exists()


def _load_from_cache(taxon_filter: Optional[set[str]] = None) -> Optional[dict]:
    """キャッシュJSONから読み込む。無効なら None。"""
    if not CACHE_FILE.exists():
        return None
    try:
        import json
        with CACHE_FILE.open(encoding="utf-8") as f:
            cached = json.load(f)
        # taxon_filter が指定されていて、キャッシュに全件含まれていればOK
        if taxon_filter is not None:
            missing = taxon_filter - set(cached.keys())
            # キャッシュに無い種があっても、それは単にGloBIに無いだけなので許容
            # ただし半分以上欠けているならキャッシュ不正とみなす
            if len(missing) > len(taxon_filter) * 0.5:
                return None
        return cached
    except Exception:
        return None


def _save_to_cache(data: dict) -> None:
    try:
        import json
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"[centrality] キャッシュ保存失敗: {e}")


def load_centralities(taxon_filter: Optional[set[str]] = None,
                      use_cache: bool = True) -> dict[str, dict]:
    """
    Sony CSL データセットをロードし、タクソン名 → 中心性指標 の辞書を返す。
    初回はフルスキャン(数分)、2回目以降はキャッシュから瞬時に読み込む。

    Args:
      taxon_filter: 必要な学名の集合(大文字化して渡すこと)。指定するとメモリ節約。
      use_cache: True なら .centrality_cache.json があればそこから読み込む

    Returns:
      {taxon_name: {"dc": float, "bc": float, "pr": float,
                    "dc_corrected": float, "bc_corrected": float, "pr_corrected": float}}
    """
    # 1) キャッシュから試行
    if use_cache:
        cached = _load_from_cache(taxon_filter)
        if cached is not None:
            print(f"[centrality] キャッシュから読み込み: {len(cached)} taxa")
            return cached

    # 2) フルスキャン
    if not is_available():
        raise FileNotFoundError(
            f"Sony CSL データセットが見つかりません: {DATASET_FILE}\n"
            f"ダウンロード: {DATASET_URL}"
        )

    # GloBIの行は非常に長いためデフォルト制限(131072)を解除
    csv.field_size_limit(sys.maxsize)

    print(f"[centrality] 初回フルスキャン中...(数分かかります)")
    result: dict[str, dict] = {}
    line_count = 0

    with lzma.open(DATASET_FILE, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            line_count += 1
            if line_count % 500000 == 0:
                print(f"  ...{line_count:,} 行処理済み / 発見 {len(result)} taxa")
            # Source と Target の両方を処理
            for side in ("source", "target"):  # 小文字
                name = row.get(f"{side}TaxonName", "")
                if not name or name in ("No name", "Null"):
                    continue
                name_upper = name.upper()
                if taxon_filter is not None and name_upper not in taxon_filter:
                    continue

                if name_upper not in result:
                    result[name_upper] = {}

                # 実際のカラム名: Before/AfterCorrection サフィックス
                for key_col, dict_key in [
                    (f"{side}DegreeCentralityBeforeCorrection", "dc"),
                    (f"{side}BetweennessCentralityBeforeCorrection", "bc"),
                    (f"{side}PageRankBeforeCorrection", "pr"),
                    (f"{side}DegreeCentralityAfterCorrection", "dc_corrected"),
                    (f"{side}BetweennessCentralityAfterCorrection", "bc_corrected"),
                    (f"{side}PageRankAfterCorrection", "pr_corrected"),
                ]:
                    v = row.get(key_col)
                    if v and v not in ("", "Null", "No name"):
                        try:
                            result[name_upper][dict_key] = float(v)
                        except (ValueError, TypeError):
                            pass

    print(f"[centrality] スキャン完了: {line_count:,} 行 / {len(result)} taxa")
    # キャッシュ保存(次回高速化)
    if use_cache:
        _save_to_cache(result)
        print(f"[centrality] キャッシュ保存: {CACHE_FILE}")

    return result


def get_centrality(taxon_name: str, centralities: dict[str, dict],
                   use_corrected: bool = True) -> Optional[float]:
    """
    特定の分類群のPageRank(中心性)を返す。
    use_corrected=True で補正後の値、False で生の値。
    存在しなければ None。
    """
    key = taxon_name.upper()
    if key not in centralities:
        return None
    data = centralities[key]
    if use_corrected:
        return data.get("pr_corrected") or data.get("pr")
    return data.get("pr")


if __name__ == "__main__":
    if not is_available():
        print(f"データセット未配置。以下からダウンロードしてください:")
        print(f"  {DATASET_URL}")
        print(f"配置先: {DATASET_FILE}")
    else:
        print(f"データセット確認OK: {DATASET_FILE}")
        from data import BIRDS
        taxa_of_interest = {
            b["scientific"].upper() for b in BIRDS.values() if b.get("scientific")
        }
        data = load_centralities(taxon_filter=taxa_of_interest)
        print(f"\n=== 結果 ===")
        print(f"取得件数: {len(data)} / 対象 {len(taxa_of_interest)} 種\n")
        for b_id, bird in BIRDS.items():
            sci = bird.get("scientific", "")
            key = sci.upper()
            if key in data:
                d = data[key]
                pr = d.get("pr_corrected") or d.get("pr", 0)
                if pr:
                    print(f"  ✅ {bird['name']:15s} ({sci}) pr_corrected = {pr:.3e}")
                else:
                    print(f"  ⚠ {bird['name']:15s} ({sci}) 中心性値なし")
            else:
                print(f"  ❌ {bird['name']:15s} ({sci}) GloBIに未登録")
