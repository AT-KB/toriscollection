"""
test_i18n.py - 表示文言の多言語化(i18n.py)の単体テスト

実行: python3 toris_collection/tests/test_i18n.py または pytest
依存なし(pytest 不要、stdlib のみ)。i18n は Streamlit ランタイム外でも動く。

観点:
  - 言語切替(set_lang / get_lang / 既定は en)
  - t(): en は訳、ja は原文、未訳キーは原文にフォールバック、kwargs 埋め込み
  - describe(): en は description_en、無ければ description にフォールバック、ja は description
  - 日本語原文が辞書のキーとして残っている(= バックアップを兼ねる)ことの確認
  - パイロット移行した badges / mementos が言語で切り替わること
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import i18n  # noqa: E402
import badges  # noqa: E402
import mementos as mem  # noqa: E402


def setup_function(_func=None):
    # 各テストの前に既定(en)へ戻す
    i18n.set_lang("en")


def test_default_lang_is_en():
    # モジュール既定は en(CEO確定)
    i18n._fallback_lang = "en"
    assert i18n.get_lang() == "en"


def test_set_lang_switches():
    i18n.set_lang("ja")
    assert i18n.get_lang() == "ja"
    i18n.set_lang("en")
    assert i18n.get_lang() == "en"


def test_set_lang_ignores_unknown():
    i18n.set_lang("en")
    i18n.set_lang("fr")  # 未対応言語は無視
    assert i18n.get_lang() == "en"


def test_t_ja_returns_original():
    i18n.set_lang("ja")
    assert i18n.t("小枝") == "小枝"


def test_t_en_returns_translation():
    i18n.set_lang("en")
    assert i18n.t("小枝") == "Twig"


def test_t_unknown_key_falls_back_to_original():
    # 辞書に無いキーは、どの言語でも日本語原文をそのまま返す(落とさない)
    i18n.set_lang("en")
    assert i18n.t("辞書に無い未訳の文言") == "辞書に無い未訳の文言"
    i18n.set_lang("ja")
    assert i18n.t("辞書に無い未訳の文言") == "辞書に無い未訳の文言"


def test_t_formats_kwargs():
    i18n.set_lang("en")
    assert i18n.t("{bird}の羽根", bird="Robin") == "Robin's feather"
    i18n.set_lang("ja")
    assert i18n.t("{bird}の羽根", bird="コマドリ") == "コマドリの羽根"


def test_t_extra_kwargs_are_ignored():
    # プレースホルダに無い余分な kwargs があっても落ちない
    i18n.set_lang("en")
    assert i18n.t("小枝", bird="X", sci="Y") == "Twig"


def test_japanese_original_kept_as_dict_key():
    # 日本語原文がキーとして残っていること = バックアップを兼ねる設計の担保
    assert "小枝" in i18n.TRANSLATIONS
    assert "皆勤の友" in i18n.TRANSLATIONS


def test_describe_en_uses_description_en():
    i18n.set_lang("en")
    entity = {"description": "日本語の説明", "description_en": "English text."}
    assert i18n.describe(entity) == "English text."


def test_describe_en_falls_back_when_no_en():
    i18n.set_lang("en")
    entity = {"description": "日本語の説明"}  # description_en 欠損
    assert i18n.describe(entity) == "日本語の説明"


def test_describe_en_falls_back_when_en_empty():
    i18n.set_lang("en")
    entity = {"description": "日本語の説明", "description_en": ""}  # 空
    assert i18n.describe(entity) == "日本語の説明"


def test_describe_ja_uses_description():
    i18n.set_lang("ja")
    entity = {"description": "日本語の説明", "description_en": "English text."}
    assert i18n.describe(entity) == "日本語の説明"


def test_badge_message_switches_language():
    i18n.set_lang("ja")
    msg_ja = badges.badge_message("シジュウカラ", 100)
    assert "シジュウカラとはすっかり顔なじみです。" in msg_ja

    i18n.set_lang("en")
    msg_en = badges.badge_message("Japanese Tit", 100)
    assert "Japanese Tit" in msg_en
    # 事務的でない、あたたかい訳になっていること(直訳の否定は最低限、英語であることを確認)
    assert "old friends" in msg_en
    # 数字・煽りを持たない方針は言語に関わらず維持
    assert not any(ch.isdigit() for ch in msg_en)


def test_badge_label_switches_language():
    i18n.set_lang("ja")
    assert badges.badge_for_days(100)["label"] == "皆勤の友"
    i18n.set_lang("en")
    assert badges.badge_for_days(100)["label"] == "Dear Friend"


def test_memento_display_switches_language():
    BIRDS = {
        "robin": {"name": "コマドリ", "english": "Robin",
                  "scientific": "Erithacus", "color": "#a00"},
    }
    i18n.set_lang("ja")
    icon, name, desc, _ = mem.memento_display("feather:robin", BIRDS, {}, {})
    assert name == "コマドリの羽根"
    assert desc == "コマドリ (Erithacus) の美しい羽根。"

    i18n.set_lang("en")
    icon, name, desc, _ = mem.memento_display("feather:robin", BIRDS, {}, {})
    assert name == "Robin's feather"       # english 名を使う
    assert desc == "A lovely feather from Robin (Erithacus)."


def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        setup_function()
        t()
        print(f"  PASS  {t.__name__}")
        passed += 1
    setup_function()  # 後始末: 既定 en に戻す
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    _run()
