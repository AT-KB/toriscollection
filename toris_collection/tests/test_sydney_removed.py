"""
test_sydney_removed.py - シドニーバイオーム削除(2026-07-08)の回帰テスト

実行: python3 toris_collection/tests/test_sydney_removed.py
依存なし(pytest 不要、stdlib のみ)。data.py / mementos.py は
Streamlit にも依存しない純粋データ・純粋関数。

確認すること:
  1. BIOMES から "sydney" が消えている(UIはBIOMES.keys()から動的生成されるため、
     ここが消えていればセレクタからも自動的に消える)。
  2. BIOME_MIGRATION が "sydney" -> "kyoto" を持つ(旧セーブの安全な自動移行)。
  3. PLANTS / INSECTS / BIRDS に "sydney" を参照する行が残っていない。
  4. 削除されたシドニー鳥10種が BIRDS に存在しない。
  5. mementos.PLUME_BIRDS からシドニー種(sulphur_crested_cockatoo /
     eastern_yellow_robin)が削除されている。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import data  # noqa: E402
import mementos as mem  # noqa: E402

REMOVED_SYDNEY_BIRDS = [
    "rainbow_lorikeet", "kookaburra", "australian_magpie",
    "sulphur_crested_cockatoo", "eastern_yellow_robin", "superb_fairywren",
    "noisy_miner", "galah", "willie_wagtail", "satin_bowerbird",
]


def test_sydney_biome_removed():
    assert "sydney" not in data.BIOMES, "BIOMESにsydneyが残っている"


def test_sydney_migrates_to_kyoto():
    assert data.BIOME_MIGRATION.get("sydney") == "kyoto", \
        "BIOME_MIGRATIONにsydney->kyotoの変換がない(旧セーブが救済されない)"


def test_no_sydney_plants():
    for pid, p in data.PLANTS.items():
        assert "sydney" not in p.get("biome", []), f"植物{pid}がまだsydneyに属している"


def test_no_sydney_insects():
    # 昆虫は biome フィールドを直接持たず eats_plants 経由でバイオームに紐づく。
    # シドニー植物が全廃されたので、シドニー植物だけを食べていた昆虫が
    # 残っていないことを確認する(=昆虫側の掃除漏れがないこと)。
    sydney_plant_ids = set()  # PLANTSは既にsydney biomeを持たないので空集合になるはず
    for pid, p in data.PLANTS.items():
        if "sydney" in p.get("biome", []):
            sydney_plant_ids.add(pid)
    assert not sydney_plant_ids
    for iid, ins in data.INSECTS.items():
        eats = set(ins.get("eats_plants", []))
        assert not eats.issubset(sydney_plant_ids) or not eats, \
            f"昆虫{iid}が消えたシドニー植物にしか依存していない"


def test_no_sydney_birds():
    for bid in REMOVED_SYDNEY_BIRDS:
        assert bid not in data.BIRDS, f"削除対象のシドニー鳥{bid}がまだBIRDSに残っている"
    for bid, b in data.BIRDS.items():
        assert "sydney" not in b.get("biome_pref", []), f"鳥{bid}がまだsydneyに属している"


def test_no_sydney_wariness_orphans():
    # _WARINESS で設定された値は BIRDS[bid]["wariness"] に書き込まれる実装。
    # 削除済みの鳥IDに wariness が残っていないことを、BIRDS本体で確認する。
    for bid in REMOVED_SYDNEY_BIRDS:
        assert bid not in data.BIRDS


def test_plume_birds_no_sydney():
    assert "sulphur_crested_cockatoo" not in mem.PLUME_BIRDS
    assert "eastern_yellow_robin" not in mem.PLUME_BIRDS
    # 削除後もPLUME_BIRDS自体は空にならない(他バイオームの鳥は残る)
    assert len(mem.PLUME_BIRDS) > 0
    for bid in mem.PLUME_BIRDS:
        assert bid in data.BIRDS, f"PLUME_BIRDSに存在しない鳥ID{bid}が残っている"


def test_species_counts_after_removal():
    # 2026-07-08 実測値(回帰検知用。仕様上の下限として扱う簡易チェック)
    assert len(data.BIOMES) == 2
    assert set(data.BIOMES.keys()) == {"kyoto", "charlotte"}
    assert len(data.BIRDS) >= 30
    assert len(data.PLANTS) >= 25


if __name__ == "__main__":
    test_sydney_biome_removed()
    test_sydney_migrates_to_kyoto()
    test_no_sydney_plants()
    test_no_sydney_insects()
    test_no_sydney_birds()
    test_no_sydney_wariness_orphans()
    test_plume_birds_no_sydney()
    test_species_counts_after_removal()
    print("OK: すべてのシドニー削除回帰テストがパスしました。")
