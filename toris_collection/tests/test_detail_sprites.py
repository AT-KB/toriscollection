"""
test_detail_sprites.py - 図鑑の詳細ドット絵(designbird/<種ID>_detail.png)存在判定のテスト(2026-07-08)

実行: python3 toris_collection/tests/test_detail_sprites.py
依存なし(pytest 不要、stdlib のみ)。detail_sprites.py は Streamlit に依存しない
純粋関数のみを持つモジュール。

確認すること:
  1. 今回配置済みの2種(northern_cardinal / american_goldfinch)は存在判定が True。
  2. まだ詳細画像が無い種(例: blue_jay)は False(=今まで通りの表示に留まる)。
  3. 存在しない種IDでも例外を投げず False を返す。
  4. base_dir を差し替えれば、実ファイルの有無だけで判定される(一時ディレクトリでの検証)。
  5. エイリアス解決を行わない(SPRITE_ALIASES とは無関係)ことを、
     実際にエイリアスを持つ種で確認する。
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import detail_sprites  # noqa: E402
import data  # noqa: E402


def test_existing_detail_images_found():
    assert detail_sprites.has_detail_image("northern_cardinal") is True
    assert detail_sprites.has_detail_image("american_goldfinch") is True


def test_missing_detail_image_returns_false():
    # 詳細画像が無い種は常にFalseになること。個別の種IDをハードコードすると
    # 新しい詳細画像が追加されるたびにテストが壊れるため、実行時点でファイルが
    # 存在しない種をdata.BIRDSから動的に選んで確認する。
    missing = [
        bird_id for bird_id in data.BIRDS.keys()
        if not detail_sprites.detail_image_path(bird_id).is_file()
    ]
    assert missing, "検証対象がありません(全種に詳細画像がある状態は想定外)"
    assert detail_sprites.has_detail_image(missing[0]) is False


def test_unknown_bird_id_no_exception():
    assert detail_sprites.has_detail_image("no_such_bird_species_xyz") is False


def test_uses_base_dir_override_with_tempdir():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        assert detail_sprites.has_detail_image("fake_bird", base_dir=tmp_path) is False
        (tmp_path / "fake_bird_detail.png").write_bytes(b"\x89PNG\r\n")
        assert detail_sprites.has_detail_image("fake_bird", base_dir=tmp_path) is True
        # 通常のスプライト名(サフィックスなし)だけでは詳細画像扱いにならない
        (tmp_path / "other_bird.png").write_bytes(b"\x89PNG\r\n")
        assert detail_sprites.has_detail_image("other_bird", base_dir=tmp_path) is False


def test_no_alias_resolution():
    # SPRITE_ALIASES(designbird/ の簡易スプライト流用)に登録されている種のうち、
    # 実ファイルが無いものは詳細画像判定でも False のままであること
    # (=詳細画像はエイリアスで"借りて"来ない)。
    from data import SPRITE_ALIASES
    aliased_without_detail_file = [
        bird_id for bird_id, sprite_id in SPRITE_ALIASES.items()
        if bird_id != sprite_id
        and not detail_sprites.detail_image_path(bird_id).is_file()
    ]
    for bird_id in aliased_without_detail_file:
        assert detail_sprites.has_detail_image(bird_id) is False


def test_all_bird_ids_resolve_without_error():
    # BIRDSの全種でクラッシュしないことを確認(存在有無を問わず bool を返す)
    for bird_id in data.BIRDS.keys():
        result = detail_sprites.has_detail_image(bird_id)
        assert isinstance(result, bool)


if __name__ == "__main__":
    test_existing_detail_images_found()
    test_missing_detail_image_returns_false()
    test_unknown_bird_id_no_exception()
    test_uses_base_dir_override_with_tempdir()
    test_no_alias_resolution()
    test_all_bird_ids_resolve_without_error()
    print("OK: すべての詳細ドット絵存在判定テストがパスしました。")
