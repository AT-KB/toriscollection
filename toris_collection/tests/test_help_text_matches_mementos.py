"""
test_help_text_matches_mementos.py - 使い方タブの「落とし物のしくみ」説明が
実装(mementos.py)と整合していることの回帰テスト(2026-07-11)

背景: CEO実機フィードバックで、使い方タブの説明が過去の仕様(5カテゴリ:
羽根・種・小枝・木の実・羽冠)のまま残っていて、実際の実装(twig/feather/plume
の3カテゴリのみ)とズレていることが発覚した。これを直した後、再びズレるのを
防ぐための回帰テスト。

app.py はStreamlitランタイムに依存するトップレベル実行文を含むため直接importせず、
ソースをテキストとして検査する(test_save_code_copy_button.py と同じ流儀)。
"""
import os
import sys

import pytest

TESTS_DIR = os.path.dirname(__file__)
APP_PATH = os.path.join(TESTS_DIR, "..", "app.py")
sys.path.insert(0, os.path.join(TESTS_DIR, ".."))

import mementos as mem  # noqa: E402


def _read_app_source():
    with open(APP_PATH, encoding="utf-8") as f:
        return f.read()


def test_mementos_module_has_exactly_three_categories():
    # 実装側の前提が変わっていないか(このテスト自体の前提確認)
    assert mem.CATEGORIES == ["twig", "feather", "plume"]
    assert set(mem.DROP_PROBABILITIES.keys()) == {"twig", "feather", "plume"}


def test_help_text_mentions_actual_categories_only():
    src = _read_app_source()
    section = src[src.index("落とし物のしくみ"):]
    section = section[:section.index('土地と気温')]
    assert "小枝" in section
    assert "羽根" in section
    assert "羽冠" in section
    # 廃止済みカテゴリ(種・木の実)への言及が残っていないこと
    # (「26種」のような単位としての「種」は許容し、旧カテゴリ名としての
    # 「🌱 種」「木の実」だけを対象にする)
    assert "🌱 種" not in section
    assert "木の実" not in section


def test_help_text_no_stale_seed_or_nut_terms_in_app():
    # app.py 自体には旧カテゴリ(種・木の実)への言及が一切無いこと
    # (mementos.py 側の後方互換コードは対象外)
    src = _read_app_source()
    assert "木の実" not in src
    assert "羽根や種などの宝物" not in src


if __name__ == "__main__":
    test_mementos_module_has_exactly_three_categories()
    test_help_text_mentions_actual_categories_only()
    test_help_text_no_stale_seed_or_nut_terms_in_app()
    print("OK")
