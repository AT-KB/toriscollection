"""
flock.py - 群れ(同種が複数)のサイズを決める純粋計算

■ 方針(交渉不能・HANDOFF §1-1 の背骨に沿う)
  群れは「ラジオを豊かにする」装置。新種を増やさずに、馴染んだ鳥の声を
  厚くする。よく会った鳥ほど大きな群れで鳴く = 「会いに行く」がそのまま
  声の厚みに accrete する。これは軸(ラジオが豊かになる / また会いに行く)
  に直結する。罰でも損でもなく、ただ豊かさが積み上がる。

■ 生態学的根拠(誠実さ)
  - 群れ形成は種に強く依存する: 小型で普通種(スズメ・メジロ等)は群れ、
    猛禽や縄張り性の強い種は単独でいることが多い。
    ここでは rarity を素朴な代理変数として使う(普通種ほど群れやすい)。
    種ごとに正確に決めたいときは Sheets の flock_max 列で上書きできる。
  - 群れの大きさは生息地の質と馴染みで育つ。本モジュールは観察回数
    (familiarity)で cap まで成長させる。馴染みのない鳥はまず1羽から。

このモジュールは I/O にも UI にも依存しない純粋計算。
"""
from __future__ import annotations

MAX_CAP = 3          # 1種あたりの群れ上限(音が濁らない範囲に抑える)
GROWTH_EVERY = 3     # 観察何回ごとに群れが1羽増えるか


def flock_cap(bird_id: str, birds_data: dict) -> int:
    """その種が作りうる群れの最大サイズ(1..MAX_CAP)。

    data に flock_max があればそれを使う(Sheets 列で種ごとに調整可)。
    無ければ rarity から導く: 普通種=群れやすい / レア種=単独。
    """
    bird = birds_data.get(bird_id, {})
    explicit = bird.get("flock_max")
    if explicit is not None:
        try:
            return max(1, min(MAX_CAP, int(explicit)))
        except (TypeError, ValueError):
            pass
    try:
        r = float(bird.get("rarity", 0.5))
    except (TypeError, ValueError):
        r = 0.5
    if r >= 0.7:
        return 1      # レア = 単独(特別な一声)
    if r >= 0.4:
        return 2
    return 3          # 普通種 = 群れやすい


def flock_size(bird_id: str, count: int, birds_data: dict) -> int:
    """ラジオで今この鳥が何羽で鳴くか(1..cap)。

    cap を超えない範囲で、観察回数(familiarity)に応じて群れが育つ。
    単独種(cap=1)は常に1。よく会った社会性の鳥ほど厚い群れになる。
    """
    cap = flock_cap(bird_id, birds_data)
    if cap <= 1:
        return 1
    try:
        c = int(count)
    except (TypeError, ValueError):
        c = 0
    grown = 1 + max(0, c) // GROWTH_EVERY
    return max(1, min(cap, grown))
