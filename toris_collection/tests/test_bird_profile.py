"""
test_bird_profile.py - 図鑑プロフィール(好きなもの/好きな場所/こわいもの)の単体テスト

実行: py -3 toris_collection/tests/test_bird_profile.py
依存なし(stdlib のみ)。bird_profile.py / predators.py は Streamlit にも
engine.py にも依存しない純粋関数群。

確認すること:
  1. 好きなもの/好きな場所が、既存フィールド(eats_plants/eats_insects/biome_pref)
     だけから導かれること。図鑑に無い ID は静かに落ちること。
  2. こわいもの = GloBI 実データ由来で、勝手に作られないこと(原則4)。
     カテゴリは既知のキーだけ・最大3件・多い順。
  3. genus フォールバック由来のものが level で区別されていること
     (=「近縁のなかまの記録から」と断れる)。
  4. 天敵ラベルが EN 表示で日本語のまま漏れないこと(2026-08-02 監査の再発防止)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n            # noqa: E402
import bird_profile    # noqa: E402
import predators       # noqa: E402
from predator_data import PREDATORS  # noqa: E402

PLANTS = {
    "sakura": {"name": "サクラ", "english": "Cherry"},
    "kunugi": {"name": "クヌギ", "english": "Sawtooth oak"},
}
INSECTS = {"aomushi": {"name": "アオムシ", "english": "Caterpillar"}}
BIOMES = {
    "kyoto": {"name": "京都の庭", "name_en": "Kyoto garden"},
    "charlotte": {"name": "シャーロットの庭", "name_en": "Charlotte garden"},
}
BIRD = {
    "name": "シジュウカラ", "english": "Japanese Tit",
    "eats_plants": ["sakura", "kunugi", "MISSING"],
    "eats_insects": ["aomushi", "GONE"],
    "biome_pref": ["kyoto", "NOWHERE"],
}


def test_likes_uses_only_existing_species():
    got = bird_profile.likes(BIRD, PLANTS, INSECTS)
    assert [x["id"] for x in got] == ["sakura", "kunugi", "aomushi"]
    assert [x["kind"] for x in got] == ["plant", "plant", "insect"]
    # 図鑑に無い ID(MISSING/GONE)は静かに除外される
    assert all(x["entity"] for x in got)


def test_home_uses_only_existing_biomes():
    got = bird_profile.home(BIRD, BIOMES)
    assert [x["id"] for x in got] == ["kyoto"]


def test_empty_fields_are_empty_not_invented():
    bare = {"eats_plants": [], "eats_insects": [], "biome_pref": []}
    assert bird_profile.likes(bare, PLANTS, INSECTS) == []
    assert bird_profile.home(bare, BIOMES) == []
    # データの無い鳥の「こわいもの」は空。埋め草を作らない(原則4)。
    assert bird_profile.fears("no_such_bird")["categories"] == []


def test_fears_come_from_real_globi_data_only():
    for bird_id, rec in PREDATORS.items():
        cats = predators.categories(bird_id)
        assert cats, f"{bird_id}: 生成データにカテゴリが無い"
        assert len(cats) <= 3, f"{bird_id}: カテゴリが多すぎる(静かなトーンを守る)"
        assert len(set(cats)) == len(cats), f"{bird_id}: カテゴリが重複"
        for c in cats:
            assert c in predators.CATEGORY_LABELS, f"{bird_id}: 未知のカテゴリ {c}"
        # 多い順に並んでいること
        recs = [rec["records"][c] for c in cats]
        assert recs == sorted(recs, reverse=True), f"{bird_id}: 件数の降順でない"
        assert rec["level"] in ("species", "genus")


def test_genus_level_is_flagged_not_hidden():
    genus_birds = [b for b, r in PREDATORS.items() if r["level"] == "genus"]
    # 京都の小鳥は GloBI に種レベルの記録が無く、属フォールバックに頼っている。
    # それを「種の事実」として黙って出さないための旗が立っていること。
    assert genus_birds, "genus フォールバックの鳥が1種も無い(取得方法の退行?)"
    for b in genus_birds:
        assert predators.is_genus_level(b) is True
        assert bird_profile.fears(b)["genus_level"] is True
    for b in (b for b, r in PREDATORS.items() if r["level"] == "species"):
        assert predators.is_genus_level(b) is False


def test_predator_labels_are_translated_in_english():
    try:
        i18n.set_lang("en")
        for key, ja in predators.CATEGORY_LABELS.items():
            en = i18n.t(ja)
            assert en != ja, f"{key}: 英訳が無く日本語のまま漏れる"
            assert en.isascii(), f"{key}: 英訳に非ASCIIが混じっている -> {en}"
        # 実際に使われるラベル群も EN で日本語が出ないこと
        for bird_id in PREDATORS:
            for label in predators.labels(bird_id):
                assert label.isascii(), f"{bird_id}: EN 画面に日本語ラベル {label}"
    finally:
        i18n.set_lang("en")


def test_build_returns_all_three_sections():
    prof = bird_profile.build("shijukara", BIRD, PLANTS, INSECTS, BIOMES)
    assert set(prof) == {"likes", "home", "fears"}
    assert set(prof["fears"]) == {"categories", "genus_level"}


def test_rows_are_localised_and_skip_empty_sections():
    try:
        i18n.set_lang("ja")
        rows = bird_profile.rows("shijukara", BIRD, PLANTS, INSECTS, BIOMES)
        labels = {label for _, label, _ in rows}
        assert labels == {"好きなもの", "好きな場所", "こわいもの"}
        by_label = {label: value for _, label, value in rows}
        assert by_label["好きなもの"] == "サクラ、クヌギ、アオムシ"
        assert by_label["好きな場所"] == "京都の庭"
        # シジュウカラは属フォールバック由来 = 断りが添えられる
        assert "(近縁のなかまの記録から)" in by_label["こわいもの"]

        i18n.set_lang("en")
        rows_en = bird_profile.rows("shijukara", BIRD, PLANTS, INSECTS, BIOMES)
        by_label_en = {label: value for _, label, value in rows_en}
        assert by_label_en["Favourites"] == "Cherry, Sawtooth oak, Caterpillar"
        assert by_label_en["Home"] == "Kyoto garden"
        for label, value in by_label_en.items():
            assert label.isascii() and value.isascii(), \
                f"EN 画面に日本語が漏れている: {label} / {value}"

        # データが1つも無ければ行は0(空の枠を描かないため)
        bare = {"eats_plants": [], "eats_insects": [], "biome_pref": []}
        assert bird_profile.rows("no_such_bird", bare, PLANTS, INSECTS, BIOMES) == []
    finally:
        i18n.set_lang("en")


def test_rows_work_for_every_real_bird_in_both_languages():
    """実データ(species_loader)の全種で落ちず、EN で日本語が漏れないこと。"""
    import species_loader as sl

    try:
        for lang in ("ja", "en"):
            i18n.set_lang(lang)
            for bid, bird in sl.BIRDS.items():
                rows = bird_profile.rows(bid, bird, sl.PLANTS, sl.INSECTS,
                                         sl.BIOMES)
                for emoji, label, value in rows:
                    assert emoji and label and value, f"{bid}: 空の行がある"
                    if lang == "en":
                        assert label.isascii(), f"{bid}: EN にラベル {label}"
                        assert value.isascii(), f"{bid}: EN に値 {value}"
    finally:
        i18n.set_lang("en")


if __name__ == "__main__":
    test_likes_uses_only_existing_species()
    test_home_uses_only_existing_biomes()
    test_empty_fields_are_empty_not_invented()
    test_fears_come_from_real_globi_data_only()
    test_genus_level_is_flagged_not_hidden()
    test_predator_labels_are_translated_in_english()
    test_build_returns_all_three_sections()
    test_rows_are_localised_and_skip_empty_sections()
    test_rows_work_for_every_real_bird_in_both_languages()
    print("OK: すべての図鑑プロフィール(bird_profile.py)テストがパスしました。")
