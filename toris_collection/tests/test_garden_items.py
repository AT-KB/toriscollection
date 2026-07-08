"""
test_garden_items.py - 広告リワード「今日の庭アイテム」(garden_items.py)の単体テスト

実行: python3 toris_collection/tests/test_garden_items.py
依存なし(pytest 不要、stdlib のみ)。garden_items.py は
Streamlit にも engine.py/networkx にも依存しない純粋関数群。

確認すること:
  1. 各アイテムの対象種の絞り込みが、既存の data.py フィールド
     (eats_plants/eats_insects/english/wariness/biome_pref)だけから
     正しく導かれること(ハチドリ限定・京都グレーアウト等)。
  2. 配置(place_item)・有効期限判定(is_active/hours_remaining)が
     6時間ちょうどで正しく切れること。
  3. アイテム未配置時、run_turn に渡すボーナス関数/値が「常に0」になること
     (=既存の挙動から一切変わらないことの保証)。
  4. is_item_boosted_arrival が生態ログを汚さない設計(honest reason)の
     判定ロジックとして正しく機能すること。
  5. ads.py の「1日1回」日付ゲートのpure関数。
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import data  # noqa: E402
import garden_items as gi  # noqa: E402
import ads  # noqa: E402

BIRDS = data.BIRDS


# ── 対象種の絞り込み ──────────────────────────────────────────

def test_hummingbird_feeder_is_charlotte_only():
    charlotte_targets = gi.target_bird_ids("hummingbird_feeder", "charlotte", BIRDS)
    kyoto_targets = gi.target_bird_ids("hummingbird_feeder", "kyoto", BIRDS)
    assert charlotte_targets == {"ruby_throated_hummingbird"}
    assert kyoto_targets == set()
    assert gi.is_available("hummingbird_feeder", "charlotte", BIRDS) is True
    assert gi.is_available("hummingbird_feeder", "kyoto", BIRDS) is False


def test_suet_feeder_targets_woodpeckers_only():
    kyoto_targets = gi.target_bird_ids("suet_feeder", "kyoto", BIRDS)
    charlotte_targets = gi.target_bird_ids("suet_feeder", "charlotte", BIRDS)
    assert kyoto_targets == {"kogera"}
    assert charlotte_targets == {
        "pileated_woodpecker", "downy_woodpecker", "red_bellied_woodpecker",
    }
    # 非キツツキは対象外
    assert "shijukara" not in kyoto_targets
    assert "northern_cardinal" not in charlotte_targets


def test_nyjer_feeder_targets_true_goldfinches_only():
    kyoto_targets = gi.target_bird_ids("nyjer_feeder", "kyoto", BIRDS)
    charlotte_targets = gi.target_bird_ids("nyjer_feeder", "charlotte", BIRDS)
    assert kyoto_targets == {"kawarahiwa"}
    assert charlotte_targets == {"american_goldfinch"}
    # House Finch は"Finch"でも対象外(提案書の裁量判断どおり)
    assert "house_finch" not in charlotte_targets


def test_squirrel_baffle_targets_wary_birds_excluding_water_specialists():
    kyoto_targets = gi.target_bird_ids("squirrel_baffle", "kyoto", BIRDS)
    charlotte_targets = gi.target_bird_ids("squirrel_baffle", "charlotte", BIRDS)
    # カワセミ(水系専門種)はwariness0.7で閾値を超えるが明示的に除外される
    assert "kawasemi" not in kyoto_targets
    for bid in kyoto_targets | charlotte_targets:
        assert (BIRDS[bid].get("wariness") or 0) >= 0.55
    # 代表種が含まれていること
    assert "uguisu" in kyoto_targets
    assert "pileated_woodpecker" in charlotte_targets


def test_feeder_is_broad_seed_eaters():
    kyoto_targets = gi.target_bird_ids("feeder", "kyoto", BIRDS)
    # 種子を食べる代表種は含まれる
    assert "shijukara" in kyoto_targets
    assert "suzume" in kyoto_targets
    # 完全な虫食い(eats_plants空)は対象外
    assert "uguisu" not in kyoto_targets
    assert "kawasemi" not in kyoto_targets


def test_bird_bath_has_no_species_target_but_is_available():
    # バードバスは「全種共通」なので個別対象リストは持たない(空集合)。
    assert gi.target_bird_ids("bird_bath", "kyoto", BIRDS) == set()
    assert gi.is_available("bird_bath", "kyoto", BIRDS) is True
    assert gi.is_available("bird_bath", "charlotte", BIRDS) is True


def test_unavailable_reason_is_factual_not_punitive():
    reason = gi.unavailable_reason("hummingbird_feeder", "kyoto", BIRDS)
    assert "ハチドリ" in reason
    assert "シャーロット" in reason


# ── 配置・有効期限 ──────────────────────────────────────────

def test_place_item_active_within_6_hours_and_expires_after():
    now = datetime(2026, 7, 8, 10, 0, 0)
    placement = gi.place_item("feeder", now=now)
    assert placement["item_id"] == "feeder"

    assert gi.is_active(placement, at_time=now) is True
    assert gi.is_active(placement, at_time=now + timedelta(hours=5, minutes=59)) is True
    assert gi.is_active(placement, at_time=now + timedelta(hours=6)) is True
    assert gi.is_active(placement, at_time=now + timedelta(hours=6, minutes=1)) is False
    assert gi.is_active(placement, at_time=now - timedelta(minutes=1)) is False


def test_hours_remaining_decreases_to_zero():
    now = datetime(2026, 7, 8, 10, 0, 0)
    placement = gi.place_item("bird_bath", now=now)
    assert abs(gi.hours_remaining(placement, at_time=now) - 6.0) < 0.01
    assert abs(gi.hours_remaining(placement, at_time=now + timedelta(hours=3)) - 3.0) < 0.01
    assert gi.hours_remaining(placement, at_time=now + timedelta(hours=7)) == 0.0
    assert gi.hours_remaining(None) == 0.0


# ── run_turn 向けフック(未配置時は常にゼロ=既存挙動を破壊しない) ──

def test_no_placement_means_zero_bonus_everywhere():
    fn = gi.make_arrival_bonus_fn(None, "kyoto", BIRDS)
    assert fn("shijukara") == 0.0
    assert fn("uguisu") == 0.0
    assert gi.departure_bonus(None) == 0.0
    assert gi.is_item_boosted_arrival("shijukara", None, "kyoto", BIRDS) is False


def test_expired_placement_means_zero_bonus():
    now = datetime(2026, 7, 8, 10, 0, 0)
    placement = gi.place_item("feeder", now=now)
    later = now + timedelta(hours=7)
    fn = gi.make_arrival_bonus_fn(placement, "kyoto", BIRDS, at_time=later)
    assert fn("shijukara") == 0.0
    assert gi.departure_bonus(placement, at_time=later) == 0.0


def test_active_arrival_bonus_applies_only_to_targets():
    now = datetime(2026, 7, 8, 10, 0, 0)
    placement = gi.place_item("hummingbird_feeder", now=now)
    fn = gi.make_arrival_bonus_fn(placement, "charlotte", BIRDS, at_time=now)
    assert fn("ruby_throated_hummingbird") == gi.ITEMS["hummingbird_feeder"]["value"]
    assert fn("northern_cardinal") == 0.0
    # 京都では対象0羽なので誰にもボーナスがつかない
    fn_kyoto = gi.make_arrival_bonus_fn(placement, "kyoto", BIRDS, at_time=now)
    assert fn_kyoto("shijukara") == 0.0


def test_active_departure_bonus_only_for_bird_bath():
    now = datetime(2026, 7, 8, 10, 0, 0)
    bath = gi.place_item("bird_bath", now=now)
    feeder = gi.place_item("feeder", now=now)
    assert gi.departure_bonus(bath, at_time=now) == gi.ITEMS["bird_bath"]["value"]
    assert gi.departure_bonus(feeder, at_time=now) == 0.0
    # バードバスは arrival_bonus には寄与しない
    fn = gi.make_arrival_bonus_fn(bath, "kyoto", BIRDS, at_time=now)
    assert fn("shijukara") == 0.0


def test_is_item_boosted_arrival_only_for_active_targets():
    now = datetime(2026, 7, 8, 10, 0, 0)
    placement = gi.place_item("suet_feeder", now=now)
    assert gi.is_item_boosted_arrival("kogera", placement, "kyoto", BIRDS, at_time=now) is True
    assert gi.is_item_boosted_arrival("shijukara", placement, "kyoto", BIRDS, at_time=now) is False
    later = now + timedelta(hours=7)
    assert gi.is_item_boosted_arrival("kogera", placement, "kyoto", BIRDS, at_time=later) is False


# ── ads.py: 1日1回の日付ゲート(pure関数) ──────────────────────

def test_daily_gate_claim_and_check():
    session = {}
    today = datetime(2026, 7, 8).date()
    assert ads.has_claimed_today(session, "twig_reward_claimed_date", today) is False
    ads.mark_claimed_today(session, "twig_reward_claimed_date", today)
    assert ads.has_claimed_today(session, "twig_reward_claimed_date", today) is True

    tomorrow = today + timedelta(days=1)
    assert ads.has_claimed_today(session, "twig_reward_claimed_date", tomorrow) is False


if __name__ == "__main__":
    test_hummingbird_feeder_is_charlotte_only()
    test_suet_feeder_targets_woodpeckers_only()
    test_nyjer_feeder_targets_true_goldfinches_only()
    test_squirrel_baffle_targets_wary_birds_excluding_water_specialists()
    test_feeder_is_broad_seed_eaters()
    test_bird_bath_has_no_species_target_but_is_available()
    test_unavailable_reason_is_factual_not_punitive()
    test_place_item_active_within_6_hours_and_expires_after()
    test_hours_remaining_decreases_to_zero()
    test_no_placement_means_zero_bonus_everywhere()
    test_expired_placement_means_zero_bonus()
    test_active_arrival_bonus_applies_only_to_targets()
    test_active_departure_bonus_only_for_bird_bath()
    test_is_item_boosted_arrival_only_for_active_targets()
    test_daily_gate_claim_and_check()
    print("OK: すべての庭アイテム(garden_items.py)テストがパスしました。")
