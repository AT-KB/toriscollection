"""
garden_items.py - 広告リワード「今日の庭アイテム」(6種)

■ 位置づけ(交渉不能の原則・00_共通サマリ.md、および
  docs/team/proposals/2026-07-08_広告リワードアイテム拡充案.md)
  - 広告視聴で1日1回だけ配置できる、6時間だけ効果を持つ任意のおまけ。
  - 効果は対象の鳥の到来確率を+1〜6ポイント程度後押しする、または退去率を
    下げるという実際の(ただし小さな)ブースト。見なくても鳥の声・ラジオ・図鑑
    そのものや、通常(アイテムなし)の到来確率は変わらない(交渉不能の原則3の核は
    維持)が、「一切変わらない」は言い過ぎのため2026-07-12に文言修正
    (app.py 使い方タブ・フッターと合わせて訂正)。
  - 効果は常に加点方向のみ(到来確率アップ or 退去率ダウン)。ペナルティはない
    (交渉不能の原則2)。
  - `feeder_chain.py`(リス→Hawk連鎖)とは別枠の軽量・独立実装。
    `engine.build_network`(GloBIベースの食物網エッジ)自体は一切変更しない。
  - 対象種の絞り込みは既存の `data.py` フィールド(eats_plants/eats_insects/
    english/wariness/biome_pref)だけを根拠にする。新しい恣意的な指標は作らない。
  - 「なぜ来たか」生態ログ(GloBI由来の理由文)にはこのアイテム効果を混ぜない。
    UI上は別枠のバッジで「今日はこのアイテムを置いています」とだけ示す
    (app.py 側の責務)。

依存は標準ライブラリのみ(datetime)。Streamlit にも依存しないため、
`app.py` から独立してユニットテストできる。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from i18n import t

# 1回の配置が効果を持つ時間
DURATION_HOURS = 6

# 水系専門種の除外(⑥リス返し用)。カワセミは魚類・水生昆虫食で庭の給餌器文脈と
# 無関係なため、wariness閾値だけで機械的に対象化すると不誠実な理由付けになる。
# これは企画部の裁量判断であり、原則4(生態に誠実)を優先した結果(提案書§3)。
WATER_SPECIALIST_EXCLUDE = {"kawasemi"}

# ⑤ニジャーシードフィーダーの対象(ヒワの仲間限定)。
# data.py にはGloBI由来の「属(genus)」情報が無いため、Fringillidae 内でも
# 実際にニジャーシードを好む "goldfinch" 系統(Chloris/Spinus)だけを明示的に
# 対象にする(House Finch = Haemorhous は同じ "finch" でも採餌生態が異なるため
# 対象外、という提案書の裁量判断をそのままコードにも明記する)。
NYJER_TARGET_BIRDS = {"kawarahiwa", "american_goldfinch"}

# 到来確率アップ / 退去率ダウンの2種類だけ(恣意的な新メカニクスを増やさない)
EFFECT_ARRIVAL_BONUS = "arrival_bonus"
EFFECT_DEPARTURE_REDUCTION = "departure_reduction"

ITEMS = {
    "feeder": {
        "emoji": "🌻",
        "name": "バードフィーダー",
        "subtitle": "ヒマワリ・混合シードの開放型給餌器",
        "effect_kind": EFFECT_ARRIVAL_BONUS,
        "value": 0.010,  # +1.0pp
        "hint": "種子を食べる鳥たちに、少しだけ来やすくなってもらう道具です。",
        "culture_note": "いちばん定番の開放型。誰でも来られる分、代わり映えは控えめ。",
    },
    "hummingbird_feeder": {
        "emoji": "🍬",
        "name": "ハチドリ用ネクター給餌器",
        "subtitle": "砂糖水(4:1)のネクター給餌器",
        "effect_kind": EFFECT_ARRIVAL_BONUS,
        "value": 0.060,  # +6.0pp
        "hint": "ルビーノドハチドリだけに強く効く、専門アイテムです。",
        "culture_note": (
            "砂糖水を吸いに来る、アメリカ東部の夏の風物詩。"
            "日本にハチドリはいないので、京都の庭では使えません——"
            "これはバグではなく生態的な事実です。"
        ),
        "single_target": "ruby_throated_hummingbird",
    },
    "suet_feeder": {
        "emoji": "🧈",
        "name": "スエット(脂身)フィーダー",
        "subtitle": "高カロリーの脂身ブロック",
        "effect_kind": EFFECT_ARRIVAL_BONUS,
        "value": 0.025,  # +2.5pp
        "hint": "キツツキの仲間に効く道具です。",
        "culture_note": "高カロリーで、種子より虫を捕る鳥に効く。冬に特に人気。",
    },
    "bird_bath": {
        "emoji": "💧",
        "name": "バードバス",
        "subtitle": "水場",
        "effect_kind": EFFECT_DEPARTURE_REDUCTION,
        "value": 0.05,
        "hint": "すべての鳥が少しだけ長居しやすくなります。",
        "culture_note": "水浴びに来た鳥はしばらく庭に残る。呼ぶというより、長居させる道具。",
    },
    "nyjer_feeder": {
        "emoji": "🌰",
        "name": "ニジャーシードフィーダー",
        "subtitle": "網目の細かいヒワ専用給餌器",
        "effect_kind": EFFECT_ARRIVAL_BONUS,
        "value": 0.050,  # +5.0pp
        "hint": "ヒワの仲間だけに強く効く、専門アイテムです。",
        "culture_note": (
            "網目の細かい専用給餌器。ヒワ以外はほぼ使えない、"
            "\"狙って呼ぶ\"文化の象徴。"
        ),
    },
    "squirrel_baffle": {
        "emoji": "🛡",
        "name": "リス返し(スクワレルバッフル)",
        "subtitle": "餌台への侵入を防ぐバッフル",
        "effect_kind": EFFECT_ARRIVAL_BONUS,
        "value": 0.030,  # +3.0pp
        "hint": "警戒心の強い鳥だけに効く道具です。",
        "culture_note": (
            "リスや大型を締め出す道具。実際、ハチドリ給餌器の砂糖水はリスや"
            "アリに横取りされやすく、バッフルは定番の対策。"
        ),
    },
}

# UI表示順(提案書の番号順)
ITEM_ORDER = [
    "feeder", "hummingbird_feeder", "suet_feeder",
    "bird_bath", "nyjer_feeder", "squirrel_baffle",
]


def target_bird_ids(item_id: str, biome_id: str, birds_data: dict) -> set:
    """このアイテムが今のバイオームで効果を持つ鳥ID集合を返す。

    既存の data.py フィールド(eats_plants/eats_insects/english/wariness/
    biome_pref)だけを根拠にする。新しい恣意的な指標は作らない。
    バードバス(全種共通)は対象を持たない設計のため空集合を返す
    (呼び出し側は effect_kind で分岐すること。 `is_available` はこれを考慮済み)。
    """
    item = ITEMS.get(item_id)
    if not item:
        return set()

    if "single_target" in item:
        bid = item["single_target"]
        bird = birds_data.get(bid)
        if bird and biome_id in (bird.get("biome_pref") or []):
            return {bid}
        return set()

    if item_id == "bird_bath":
        # 全種共通。個別の対象リストは持たない(is_available/is_item_boosted_arrival
        # 側で effect_kind により特別扱いする)。
        return set()

    out = set()
    for bid, b in birds_data.items():
        if biome_id not in (b.get("biome_pref") or []):
            continue
        if item_id == "feeder":
            if b.get("eats_plants"):
                out.add(bid)
        elif item_id == "suet_feeder":
            if "woodpecker" in (b.get("english") or "").lower():
                out.add(bid)
        elif item_id == "nyjer_feeder":
            if bid in NYJER_TARGET_BIRDS:
                out.add(bid)
        elif item_id == "squirrel_baffle":
            wariness = b.get("wariness") or 0
            if wariness >= 0.55 and bid not in WATER_SPECIALIST_EXCLUDE:
                out.add(bid)
    return out


def is_available(item_id: str, biome_id: str, birds_data: dict) -> bool:
    """このバイオームでこのアイテムに意味があるか(選べるか)。

    バードバスは全種共通(=このバイオームに鳥が1種でもいれば意味がある)。
    それ以外は対象種が1種以上いるかどうか。
    """
    item = ITEMS.get(item_id)
    if not item:
        return False
    if item_id == "bird_bath":
        return any(
            biome_id in (b.get("biome_pref") or []) for b in birds_data.values()
        )
    return len(target_bird_ids(item_id, biome_id, birds_data)) > 0


def unavailable_reason(item_id: str, biome_id: str, birds_data: dict) -> str:
    """選べない理由の事実説明文(ペナルティ文言にしない)。"""
    item = ITEMS.get(item_id)
    if not item:
        return ""
    if item_id == "hummingbird_feeder":
        return t(
            "{emoji} {name} — この庭にはハチドリが生息していないため使えません"
            "(シャーロットの庭で使えます)。",
            emoji=item['emoji'], name=t(item['name']),
        )
    return t("{emoji} {name} — 今のこの庭では対象になる鳥がいません。",
             emoji=item['emoji'], name=t(item['name']))


def place_item(item_id: str, now: datetime | None = None) -> dict:
    """アイテムを配置する({item_id, placed_at, expires_at} を返す・純粋関数)。"""
    now = now or datetime.now()
    return {
        "item_id": item_id,
        "placed_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(hours=DURATION_HOURS)).isoformat(timespec="seconds"),
    }


def _parse(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def is_active(placement: dict | None, at_time: datetime | None = None) -> bool:
    """指定時刻において、この配置がまだ効果を持っているか。"""
    if not placement:
        return False
    at_time = at_time or datetime.now()
    placed = _parse(placement.get("placed_at"))
    expires = _parse(placement.get("expires_at"))
    if not placed or not expires:
        return False
    return placed <= at_time <= expires


def hours_remaining(placement: dict | None, at_time: datetime | None = None) -> float:
    """指定時刻から見た残り時間(時間)。効果が無ければ0.0。"""
    if not is_active(placement, at_time):
        return 0.0
    at_time = at_time or datetime.now()
    expires = _parse(placement.get("expires_at"))
    return max(0.0, (expires - at_time).total_seconds() / 3600)


def make_arrival_bonus_fn(placement: dict | None, biome_id: str, birds_data: dict,
                          at_time: datetime | None = None):
    """engine.run_turn に渡す (bird_id) -> pp加算値 の関数を作る。

    アイテム未配置・期限切れ・到来確率アップ系でないアイテムなら、常に0を返す
    関数を返す(=既存の挙動から一切変わらない)。
    """
    if not is_active(placement, at_time):
        return lambda bid: 0.0
    item_id = placement.get("item_id")
    item = ITEMS.get(item_id)
    if not item or item["effect_kind"] != EFFECT_ARRIVAL_BONUS:
        return lambda bid: 0.0
    targets = target_bird_ids(item_id, biome_id, birds_data)
    value = item["value"]
    return lambda bid: value if bid in targets else 0.0


def departure_bonus(placement: dict | None, at_time: datetime | None = None) -> float:
    """engine.run_turn に渡す退去率の減算値。効果が無ければ0.0(既存の挙動のまま)。"""
    if not is_active(placement, at_time):
        return 0.0
    item_id = placement.get("item_id")
    item = ITEMS.get(item_id)
    if not item or item["effect_kind"] != EFFECT_DEPARTURE_REDUCTION:
        return 0.0
    return item["value"]


def is_item_boosted_arrival(bird_id: str, placement: dict | None, biome_id: str,
                            birds_data: dict, at_time: datetime | None = None) -> bool:
    """この鳥が、今アクティブなアイテムの効果対象かどうか。

    「なぜ来たか」の理由文生成のためだけに使う(生態ログの内容そのものを
    書き換えるのではなく、食物網由来の理由が薄い場合の正直な代替文の判定に使う)。
    """
    if not is_active(placement, at_time):
        return False
    item_id = placement.get("item_id")
    item = ITEMS.get(item_id)
    if not item or item["effect_kind"] != EFFECT_ARRIVAL_BONUS:
        return False
    return bird_id in target_bird_ids(item_id, biome_id, birds_data)
