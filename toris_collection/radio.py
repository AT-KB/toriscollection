"""
庭のラジオ - 出会った鳥たちが奏でるアンビエントプレイヤー

■ ラジオの正体(交渉不能・HANDOFF §1-1 の背骨)
  ラジオは「蓄積するコレクション」である。一度会った鳥は observed に
  記録され、その記録は減らない。嵐や伐採で庭の植物が倒れ、その鳥が
  live な庭(residents)から去っても、ラジオでは今までどおり鳴く。
  撹乱が触るのは「庭(=会いに行く手段の層)」だけで、ラジオ(=目的の層)は
  痩せない。だから「ラジオが豊かになる」は単調に成り立つ。
    → render_radio は residents ではなく observed/discovered を読む。
      これがコレクション性の構造的な保証。

  観察した鳥だけが鳴く。会った鳥が増えるほどコーラスが豊かになる。
  さらに、よく会った社会性の鳥は「群れ」で鳴き、声に厚みが増す(flock.py)。
  捕まえる仕組みはない。ただ聴く。

季節:  アプリ内時間で2週ごとに季節が変わる(8週サイクル)。
      渡り鳥はいない季節は一時的にラジオから引っ込む(コレクションからは消えない)。
距離感: 観察回数が多い鳥ほど手前(クリア)に聞こえる。
"""
from __future__ import annotations
import json
import base64
import random
import concurrent.futures
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import ecology
import flock as flk
import audio_engine as ae

try:
    import xc_client
except Exception:
    xc_client = None  # type: ignore

try:
    import freesound_client
except Exception:
    freesound_client = None  # type: ignore

_SPRITE_DIR = Path(__file__).parent / "designbird"
_MAX_RADIO_BIRDS = 6   # ritual より多め(呼応がメインなので多すぎず)
_COMPONENT_HEIGHT = 340

# ── アプリ内季節 ───────────────────────────────────────────────
# 2025-03-01 を春の始まりとして、2週ごとに季節が進む(8週サイクル)。
_APP_EPOCH = date(2025, 3, 1)
_WEEKS_PER_SEASON = 1

_SEASON_META = {
    "spring": {"label": "春", "icon": "🌸", "jp": "春"},
    "summer": {"label": "夏", "icon": "☀️", "jp": "夏"},
    "autumn": {"label": "秋", "icon": "🍂", "jp": "秋"},
    "winter": {"label": "冬", "icon": "❄️", "jp": "冬"},
}
_SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


def current_app_season() -> str:
    weeks = (date.today() - _APP_EPOCH).days // 7
    return _SEASON_ORDER[(weeks // _WEEKS_PER_SEASON) % 4]


def weeks_until_next_season() -> int:
    weeks = (date.today() - _APP_EPOCH).days // 7
    return _WEEKS_PER_SEASON - (weeks % _WEEKS_PER_SEASON)


# ── 鳥の在籍季節 ───────────────────────────────────────────────
# ここに載っていない鳥は year-round 扱い。
_YEAR_ROUND = set(_SEASON_ORDER)
BIRD_SEASONS: dict[str, set[str]] = {
    # 京都: 夏鳥(春〜夏に来る)
    "kibitaki":                {"spring", "summer"},
    "tsubame":                 {"spring", "summer"},
    # シャーロット: 夏鳥
    "ruby_throated_hummingbird": {"spring", "summer"},
    # シドニーはすべて year-round(固有種で渡りなし)
}


def bird_in_season(bird_id: str, season: str) -> bool:
    return season in BIRD_SEASONS.get(bird_id, _YEAR_ROUND)


# ── 観察回数 → 音響レベル ───────────────────────────────────────
# よく出会った鳥ほど「近く」に聞こえる。
def _obs_to_depth(count: int) -> str:
    if count >= 6:
        return "b1"   # 手前・クリア
    if count >= 3:
        return "b2"   # 中間
    return "b3"       # 遠景


# ── 音声キャッシュ(ritual.py と同じパターン) ───────────────────

@st.cache_data(show_spinner=False)
def _radio_audio_variants(scientific_name: str,
                          max_n: int = 2) -> list[tuple[str, str]]:
    """(base64, 鳴き方) のリスト。

    iframe に全鳥ぶんを base64 で埋め込むため、毎回の再実行で HTML が重くなる。
    1鳥あたりの変奏数と容量を絞り、読み込みを軽くする(さえずり/地鳴きの2本まで)。
    """
    if xc_client is None:
        return []
    paths = xc_client.download_audio_variants(scientific_name, max_n=max_n)
    out: list[tuple[str, str]] = []
    total = 0
    _BUDGET = 750_000   # 1鳥あたり base64 約750KB(≈ MP3 560KB)まで
    for p, sound_type in paths:
        if not (p and p.exists()):
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        if out and total + len(b64) > _BUDGET:
            continue
        out.append((b64, sound_type))
        total += len(b64)
    return out


@st.cache_data(show_spinner=False)
def _radio_ambient_b64() -> str | None:
    if freesound_client is None or not freesound_client.is_enabled():
        return None
    path = freesound_client.get_ambient_path()
    if path and path.exists():
        return base64.b64encode(path.read_bytes()).decode("ascii")
    return None


@st.cache_data(show_spinner=False)
def _radio_sprite_b64(bird_id: str) -> str | None:
    from data import SPRITE_ALIASES
    sprite_id = SPRITE_ALIASES.get(bird_id, bird_id)  # 新種は既存のドット絵を流用
    p = _SPRITE_DIR / f"{sprite_id}.png"
    if p.exists():
        try:
            return base64.b64encode(p.read_bytes()).decode("ascii")
        except Exception:
            return None
    return None


def _fetch_radio_audio(args: tuple) -> tuple:
    bid, bird = args
    sci = bird.get("scientific", "")
    if not sci:
        return bid, None
    return bid, _radio_audio_variants(sci) or None


# ── メインレンダラ ──────────────────────────────────────────────

def render_radio(
    biome_id: str,
    observed: dict,          # {bird_id: {count, first, last}}
    birds_data: dict,
    selected_biome: str | None = None,
    key_prefix: str = "radio",   # 複数箇所に埋め込む場合にキーを変える
) -> None:
    """
    庭のラジオを描画する。

    biome_id:      プレイヤーの現在のバイオーム(デフォルト選択に使う)
    observed:      観察記録 {bird_id: {count, first, last}}
    birds_data:    BIRDS 辞書
    selected_biome: ユーザーが選んだバイオーム(None = biome_id を使う)
    """
    if xc_client is None or not xc_client.is_enabled():
        st.info(
            "xeno-canto APIキーが設定されていません。鳴き声機能を有効にするには、"
            "Streamlit Cloud では secrets に `xc_api_key`、環境変数なら `XC_API_KEY`、"
            "ローカルなら `xc_api_key.txt` のいずれかでキーを設定してください。"
        )
        return

    season = current_app_season()
    season_meta = _SEASON_META[season]
    weeks_left = weeks_until_next_season()

    # ── バイオーム選択 ──────────────────────────────────────────
    biome_labels = {"kyoto": "🏯 京都", "charlotte": "🌳 シャーロット"}
    biome_ids = list(biome_labels.keys())
    current_biome = selected_biome or biome_id
    if current_biome not in biome_ids:
        current_biome = biome_ids[0]
    default_idx = biome_ids.index(current_biome)

    col_biome, col_time = st.columns([2, 1])
    with col_biome:
        chosen = st.radio(
            "庭を選ぶ",
            options=biome_ids,
            format_func=lambda x: biome_labels[x],
            index=default_idx,
            horizontal=True,
            key=f"{key_prefix}_biome_select",
            label_visibility="collapsed",
        )
    with col_time:
        # 既定は「今の時刻」= 端末のローカル時刻に追従(JS の new Date() で判定)。
        # 手動で時間帯を選べば、その時間のさえずり/地鳴きの好みで鳴く。
        time_options = ["🕒 今の時刻", "朝 (4-8時)", "昼 (10-15時)", "夕 (16-19時)", "夜 (20-3時)"]
        time_hours  = [None, 6, 12, 17, 22]
        t_idx = st.selectbox(
            "時間帯",
            options=range(len(time_options)),
            format_func=lambda i: time_options[i],
            index=0,
            key=f"{key_prefix}_time_select",
            label_visibility="collapsed",
        )
    use_real_time = time_hours[t_idx] is None
    sim_hour = 12 if use_real_time else time_hours[t_idx]
    # 季節表示はタブ見出し(app.py)が出すのでここでは出さない
    _ = weeks_left

    # ヒーリングBGMモード: やわらかな持続音(パッド)が主役。鳥は“ときどき1羽”だけ、
    # 静かに鳴く。録音の背景ノイズは、鳥が鳴かない時間を長くとる+強めのゲート/低域
    # 通過でパッドに溶け込ませる(消しきれないノイズを目立たせない設計)。
    bgm_mode = st.toggle(
        "🎧 ヒーリングBGM(鳥はときどき・環境音が主役)",
        value=False,
        key=f"{key_prefix}_bgm_toggle",
        help="作業や就寝のお供に。鳥の声は控えめになり、環境音が中心になります。",
    )

    # ── バイオームの観察済み鳥を絞り込む ──────────────────────
    biome_birds = [
        bid for bid, bird in birds_data.items()
        if chosen in bird.get("biome_pref", [])
    ]
    observed_in_biome = [
        bid for bid in biome_birds
        if bid in observed and observed[bid].get("count", 0) > 0
    ]

    if not observed_in_biome:
        st.info(f"{biome_labels[chosen]}で鳥に出会うと、ここで声が聴けるようになります。")
        return

    # 季節内・外に分ける
    in_season  = [bid for bid in observed_in_biome if bird_in_season(bid, season)]
    out_season = [bid for bid in observed_in_biome if not bird_in_season(bid, season)]

    in_season.sort(key=lambda b: -observed.get(b, {}).get("count", 0))

    if not in_season:
        # 全員季節外: チップで「いつ戻るか」を見せる
        _render_bird_chips(in_season, out_season, observed, birds_data, season)
        st.info(f"今の季節({season_meta['jp']})に鳴ける鳥がいません。他の季節にまた来てください。")
        return

    _ready_key = f"{key_prefix}_ready"
    if _ready_key not in st.session_state:
        st.session_state[_ready_key] = False

    if not st.session_state[_ready_key]:
        # 開始前: 鳥チップ一覧(在籍+季節外)で「誰が鳴けるか」を見せる
        _render_bird_chips(in_season, out_season, observed, birds_data, season)
        total_observed = len(observed_in_biome)
        st.markdown(
            f'<div style="color:#5a7a5a;font-size:0.85em;">'
            f'🗂 コレクション {total_observed} 羽 · 今の季節に {len(in_season)} 羽が鳴ける</div>',
            unsafe_allow_html=True,
        )
        if st.button("🎙 ラジオを始める", key=f"{key_prefix}_start_btn"):
            st.session_state[_ready_key] = True
            st.rerun()
        return

    # 開始後: 在籍チップは iframe 内(♪付き)に出るので、季節外だけ表示
    if out_season:
        _render_bird_chips([], out_season, observed, birds_data, season)

    # ── 今日の顔ぶれを共起ネットワークで選ぶ ────────────────────
    # 観察済み・季節内の鳥から、共起しやすい(関係の強い)鳥が揃うように選ぶ。
    # 純粋ランダムではなく、すでに選ばれた鳥と一緒に見られやすい鳥を引きやすくする。
    playable = [bid for bid in in_season if birds_data[bid].get("scientific")]
    rng = random.Random(f"{chosen}|{season}")
    # 観察回数が多い鳥ほど主役に出やすい(基礎重み)
    base_w = {bid: 1.0 + observed.get(bid, {}).get("count", 1) * 0.5 for bid in playable}
    lineup = ecology.pick_lineup(playable, birds_data, _MAX_RADIO_BIRDS, rng, base_w)
    # 音源取得に失敗する鳥に備えて、関係の薄い予備を少しだけ足す
    backups = [b for b in playable if b not in lineup]
    rng.shuffle(backups)
    candidates = [(bid, birds_data[bid]) for bid in lineup + backups[:3]]

    birds: list[dict] = []
    with st.spinner("声を集めています…"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_fetch_radio_audio, c): c[0] for c in candidates}
            for future in concurrent.futures.as_completed(futures):
                bid, b64s = future.result()
                if b64s and len(birds) < _MAX_RADIO_BIRDS:
                    bird = birds_data[bid]
                    cnt  = observed.get(bid, {}).get("count", 1)
                    birds.append({
                        "id":     bid,
                        "name":   bird.get("name", bid),
                        "color":  bird.get("color", "#888"),
                        "b64s":   b64s,
                        "sprite": _radio_sprite_b64(bid),
                        "depth":  _obs_to_depth(cnt),
                        "count":  cnt,
                        # 群れ: よく会った社会性の鳥ほど複数で鳴き、声が厚くなる
                        "flock":  flk.flock_size(bid, cnt, birds_data),
                        "nv":     len(b64s),
                        "vt":     [t for _, t in b64s],
                    })

    if not birds:
        st.info("音源を取得できませんでした。")
        return

    # 顔ぶれの並び(lineup)順に整える。先頭が今日の「主役」。
    order = {bid: i for i, bid in enumerate(lineup)}
    birds.sort(key=lambda b: order.get(b["id"], 999))
    birds = birds[:_MAX_RADIO_BIRDS]

    # ── 共起ネットワーク ──────────────────────────────────────
    # 鳴く鳥たちが「よく一緒に見られる関係」であることを見せる。
    # 同じ並び順で呼応の重み付け行列(共起度)も作る(JSへ渡す)。
    bird_ids = [b["id"] for b in birds]
    groups = ecology.guild_groups(bird_ids, birds_data)
    co_mat = ecology.co_occurrence_matrix(bird_ids, birds_data)

    # ループの payoff: 会いに行った鳥がラジオに新しく加わったことを祝う
    fresh_ids = st.session_state.get("radio_new_arrivals", set())
    fresh_names = [b["name"] for b in birds if _is_fresh(b["id"], observed, fresh_ids)]
    if fresh_names:
        _render_new_arrivals(fresh_names)

    # なぜこの顔ぶれかを一文で語る(生態の可視化 = 見えない堀を聞こえる物語に)
    story = ecology.lineup_story(bird_ids, birds_data)
    _render_connections(groups, birds_data, story)

    # ── HTML/JS レンダリング ───────────────────────────────────
    _render_radio_iframe(birds, sim_hour, chosen, season, season_meta, co_mat,
                         use_real_time=use_real_time, bgm_mode=bgm_mode)


def _render_bird_chips(
    in_season: list[str], out_season: list[str],
    observed: dict, birds_data: dict, season: str,
) -> None:
    """在籍・離脱の鳥チップを表示する(CSS chips)。"""
    chips_html = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:6px 0;">'
    for bid in in_season:
        bird = birds_data.get(bid, {})
        cnt  = observed.get(bid, {}).get("count", 0)
        bar  = "▮" * min(cnt, 5) + "▯" * max(0, 5 - cnt)
        chips_html += (
            f'<span style="background:#e8f0e0;border:1px solid #b0c890;'
            f'border-radius:16px;padding:3px 10px;font-size:0.82em;color:#3a5a3a;">'
            f'{bird.get("name","?")} <span style="color:#7ab040;font-size:0.75em">{bar}</span></span>'
        )
    for bid in out_season:
        bird   = birds_data.get(bid, {})
        s_list = BIRD_SEASONS.get(bid, _YEAR_ROUND)
        next_s = next((s for s in _SEASON_ORDER if s in s_list), "春")
        next_label = _SEASON_META.get(next_s, {}).get("jp", "春")
        chips_html += (
            f'<span style="background:#f0f0ec;border:1px solid #ccc;'
            f'border-radius:16px;padding:3px 10px;font-size:0.82em;color:#aaa;">'
            f'{bird.get("name","?")} <span style="font-size:0.75em">{next_label}に来る</span></span>'
        )
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)


# ── 「新しく加わった」判定(会う→聴くループの payoff) ──────────────
_FRESH_DAYS = 2  # 何日以内に会った鳥を「新顔」として祝うか


def _is_fresh(bid: str, observed: dict, fresh_ids: set) -> bool:
    """この鳥が最近ラジオに加わったか。

    判定はふたつの信号の OR:
      ① fresh_ids: 今このセッションで初めて会った鳥(即時)
      ② observed[bid]["first"] が直近 _FRESH_DAYS 日以内(永続・セッションをまたぐ)
    """
    if bid in fresh_ids:
        return True
    first = (observed.get(bid) or {}).get("first") or ""
    if not first:
        return False
    try:
        d = datetime.fromisoformat(str(first)).date()
    except (ValueError, TypeError):
        return False
    return 0 <= (date.today() - d).days <= _FRESH_DAYS


def _render_new_arrivals(names: list[str]) -> None:
    """会いに行った鳥がラジオに加わったことを祝うバナー(ループの payoff)。"""
    label = "・".join(names)
    st.markdown(
        f'<div style="background:#fbf6e8;border-left:3px solid #c8a830;'
        f'border-radius:8px;padding:8px 12px;margin:8px 0;">'
        f'<div style="font-size:0.84em;color:#a07f20;">'
        f'🌟 <b>{label}</b> が新しく加わりました'
        f'<span style="color:#c0a850;font-weight:400;">'
        f' — 会いに行った鳥が、ラジオの顔ぶれに増えています。</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_connections(groups: list[dict], birds_data: dict, story: str = "") -> None:
    """今日の顔ぶれの「関係」を採餌ギルドごとに見せ、なぜ一緒かを一文で語る。

    共起の科学的な駆動要因は「同じ環境を好み、採餌のしかたが近いこと」。
    なので食物の奪い合い(競争)ではなく、同じ採餌ギルドの仲間としてまとめる。
    story は今日の顔ぶれ固有の説明(ecology.lineup_story)。
    """
    if not groups and not story:
        return
    rows = ""
    for g in groups[:3]:
        names = "・".join(birds_data.get(b, {}).get("name", b) for b in g["birds"])
        rows += (
            f'<div style="display:flex;align-items:baseline;gap:8px;'
            f'margin:3px 0;font-size:0.84em;color:#3a5a3a;">'
            f'<span style="font-size:1.05em;">{g["icon"]}</span>'
            f'<span style="color:#6a8a5a;min-width:8em;">{g["label"]}</span>'
            f'<span style="font-weight:500;">{names}</span>'
            f'</div>'
        )
    caption = story or "同じ環境を好み、採餌のしかたが近い鳥ほど一緒に現れます"
    st.markdown(
        f'<div style="background:#f3f7ed;border-left:3px solid #b0c890;'
        f'border-radius:8px;padding:8px 12px;margin:8px 0;">'
        f'<div style="font-size:0.78em;color:#7a9a6a;margin-bottom:4px;">'
        f'🔗 今日の顔ぶれ &nbsp;<span style="color:#a8b89a;font-weight:400;">'
        f'— {caption}</span></div>'
        f'{rows}</div>',
        unsafe_allow_html=True,
    )


def _render_radio_iframe(
    birds: list[dict], sim_hour: int,
    biome_id: str, season: str, season_meta: dict,
    affinity: list[list[int]] | None = None,
    use_real_time: bool = True,
    bgm_mode: bool = False,
) -> None:
    """Web Audio ベースのラジオ iframe を描画する。"""

    n = len(birds)
    total_indiv = sum(b.get("flock", 1) for b in birds)  # 群れ込みの総個体数
    count_label = f"{total_indiv}羽 ({n}種)" if total_indiv > n else f"{n}羽"
    birds_meta = [
        {"id": b["id"], "name": b["name"], "nv": b["nv"],
         "vt": b["vt"], "depth": b["depth"], "flock": b.get("flock", 1)}
        for b in birds
    ]
    birds_json = json.dumps(birds_meta, ensure_ascii=False)
    if affinity is None:
        affinity = [[0] * n for _ in range(n)]
    affinity_json = json.dumps(affinity)
    use_real_time_js = "true" if use_real_time else "false"
    bgm_js = "true" if bgm_mode else "false"

    # 音声タグ
    audio_tags = "".join(
        f'<audio id="ra_{i}_{v}" preload="auto" loop style="display:none">'
        f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        for i, b in enumerate(birds)
        for v, (b64, _) in enumerate(b["b64s"])
    )

    # 環境音タグ
    amb_b64 = _radio_ambient_b64()
    ambient_tag = ""
    has_ambient = "false"
    if amb_b64:
        ambient_tag = (
            '<audio id="ra_ambient" preload="auto" loop style="display:none">'
            f'<source src="data:audio/mp3;base64,{amb_b64}" type="audio/mp3"></audio>'
        )
        has_ambient = "true"

    # スプライト表示 (チップ形式でラジオUI内にも表示)
    sprite_divs = "".join(
        f'<div class="ra_bird_chip" id="ra_chip_{i}" '
        f'style="display:inline-flex;align-items:center;gap:4px;'
        f'background:#f0f4e8;border:1px solid #c0d0a0;border-radius:20px;'
        f'padding:3px 10px 3px 5px;font-size:0.8em;color:#3a5a3a;'
        f'opacity:0.5;transition:opacity 0.8s;">'
        + (
            f'<img src="data:image/png;base64,{b["sprite"]}" '
            f'width="24" height="24" style="image-rendering:pixelated;" />'
            if b["sprite"] else
            f'<span style="width:20px;height:20px;border-radius:50%;'
            f'background:{b["color"]};display:inline-block;"></span>'
        )
        + f'<span>{b["name"]}</span>'
        + (
            f'<span style="color:#6a8a5a;font-size:0.82em;">×{b["flock"]}</span>'
            if b.get("flock", 1) > 1 else ""
        )
        + f'<span class="ra_note_{i}" style="display:inline-block;width:1em;'
        f'text-align:center;font-size:0.9em;color:#7ab040;visibility:hidden;">♪</span>'
        f'</div>'
        for i, b in enumerate(birds)
    )

    html = f"""
    {ambient_tag}
    {audio_tags}
    <style>
      body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
      #ra_wrap {{ background:linear-gradient(180deg,#f7faf2,#eef4e6);
                  padding:14px 18px; border-radius:12px;
                  border-left:4px solid #7ba87b; }}
      #ra_btn {{ background:#cfd9b8;color:#3a5a3a;border:none;
                 padding:10px 22px;border-radius:8px;cursor:pointer;
                 font-size:1em;font-weight:600; }}
      #ra_chips {{ display:flex;flex-wrap:wrap;gap:6px;margin-top:10px; }}
      .ra_active {{ opacity:1 !important; background:#e0f0d0 !important;
                   border-color:#8ab860 !important; }}
    </style>

    <div id="ra_wrap">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
        <button id="ra_btn">🎙 ラジオを始める</button>
        <div style="color:#5a7a5a;font-size:0.9em;font-weight:500;">
          {season_meta["icon"]} {season_meta["jp"]}の庭のラジオ &nbsp;·&nbsp;
          <span style="font-weight:400;">{count_label}</span>
        </div>
      </div>
      <div id="ra_chips">{sprite_divs}</div>
    </div>

    <script>
    (function() {{
        const BIRDS = {birds_json};
        const AFFINITY = {affinity_json};
        const HAS_AMBIENT = {has_ambient};
        const SIM_HOUR = {sim_hour};
        const USE_REAL_TIME = {use_real_time_js};
        const BGM = {bgm_js};   // ヒーリングBGMモード
        const n = BIRDS.length;
        const btn = document.getElementById('ra_btn');

        // ── ラジオ固有の音作り(ritual.py の共有定数は変えずに上書き) ──
        // 通常: 鳥ごとに“鳴く⇄休む”で、ソロ・重なり・無音がばらばらに生まれる。
        // BGM: 環境音(パッド)が主役。鳥は“ときどき1羽”だけ短く鳴き、大半は無音。
        //      → 消しきれない録音ノイズが鳴る時間そのものを減らし、パッドに溶かす。
        const RA_GATE_THRESH = BGM ? 0.030 : 0.024;  // BGMはゲートを厳しめに(無音の雑音を切る)
        const RA_GATE_FLOOR  = BGM ? 0.02  : 0.05;   // 休符中はより深く絞る
        const RA_AGC_MAX     = BGM ? 2.2   : 3.0;    // BGMは上げすぎない(ノイズ増幅を抑制)
        const RA_SING_MIN_S    = BGM ? 1.8 : 2.5;    // BGMは1フレーズを短め
        const RA_SING_MAX_S    = BGM ? 3.5 : 5.5;
        const RA_TARGET_ACTIVE = BGM ? 0.4 : 1.2;    // BGMは同時発声~0.4(大半は無音、たまに1羽)
        const RA_REST_MIN_S    = BGM ? 5.0 : 2.5;    // BGMは休符を長く
        const RA_REST_MAX_S    = BGM ? 26.0 : 20.0;

        // 音響パラメータ。奥行き感(残響/明るさ)は残しつつ、音量差は圧縮して
        // どの鳥も聞こえるようにする(=一部の鳥だけ小さい問題への対策)。
        const D = {{
            b3: {{ gain: 0.85, freq: 4600, wet: 0.20 }},
            b2: {{ gain: 1.00, freq: 8000, wet: 0.09 }},
            b1: {{ gain: 1.12, freq: 12000, wet: 0.01 }},
        }};

        let ctx = null, master = null, reverb = null;
        let running = false, rafId = null;
        const nodes = [];

        // AGC の状態(鳥ごとのピーク追従)
        const peakRMS   = [];

        // 鳥ごとの発声サイクル長(秒)
        function singDuration() {{
            return RA_SING_MIN_S + Math.random() * (RA_SING_MAX_S - RA_SING_MIN_S);
        }}
        function restDuration() {{
            // 同時発声を RA_TARGET_ACTIVE 前後に保つよう、鳥数で休符を伸縮。
            const avgSing = (RA_SING_MIN_S + RA_SING_MAX_S) / 2;
            let r = avgSing * (n / RA_TARGET_ACTIVE - 1);
            r = Math.max(RA_REST_MIN_S, Math.min(RA_REST_MAX_S, r));
            return r * (0.7 + Math.random() * 0.6);   // ±30% のゆらぎ(バラバラに)
        }}
        {ae.AUDIO_CONSTANTS_JS}
        {ae.MAKE_PANNER_JS}
        function setPan(nd, left) {{
            const x = (left - 50) / 50 * 4;
            const t = ctx.currentTime;
            if (nd.pan.hrtf) {{
                const z = DEPTH_Z[nd.depth] ?? -5;
                try {{
                    nd.pan.node.positionX.setTargetAtTime(x, t, 0.25);
                    nd.pan.node.positionZ.setTargetAtTime(z, t, 0.25);
                }} catch(e) {{ try {{ nd.pan.node.setPosition(x, 0, z); }} catch(e2){{}} }}
            }} else {{
                nd.pan.node.pan.setTargetAtTime(Math.max(-0.85, Math.min(0.85, x/4*0.8)), t, 0.25);
            }}
        }}

        function preferredType() {{
            // 「今の時刻」選択時は端末のローカル時刻に追従。手動選択時は SIM_HOUR。
            const h = USE_REAL_TIME ? new Date().getHours() : SIM_HOUR;
            if (h >= 4 && h < 10)  return 'song';
            if (h >= 16 || h < 4)  return 'call';
            return null;
        }}
        {ae.PICK_VARIANT_JS}

        {ae.MAKE_REVERB_IR_JS}
        {ae.MAKE_NOISE_BUFFER_JS}

        function buildAmbient() {{
            const ambEl = document.getElementById('ra_ambient');
            if (HAS_AMBIENT && ambEl) {{
                const src = ctx.createMediaElementSource(ambEl);
                const lp  = ctx.createBiquadFilter(); lp.type='lowpass'; lp.frequency.value=6000;
                const ag  = ctx.createGain(); ag.gain.value=0;
                src.connect(lp); lp.connect(ag); ag.connect(master);
                ambEl.play().catch(()=>{{}});
                ag.gain.setTargetAtTime(0.28, ctx.currentTime, 3.5);
                return ag;
            }}
            // ── キー無しのときの“ヒーリング”環境音 ──
            // ザーザーした雑音は使わず、やわらかな持続音(パッド)を主役に。
            // 完全五度と八度を重ねた濁らない和音を、音ごとに違う速さでそっと揺らす。
            const t = ctx.currentTime;
            const padBus = ctx.createGain(); padBus.gain.value = 0;
            const padLP  = ctx.createBiquadFilter();
            padLP.type='lowpass'; padLP.frequency.value=1200;
            padBus.connect(padLP); padLP.connect(master); padLP.connect(reverb);
            const notes = [130.81, 196.00, 261.63, 392.00];  // C3 G3 C4 G4
            notes.forEach(function(f, idx) {{
                // わずかにデチューンした2本で温かみ(コーラス効果)
                [-1, 1].forEach(function(sgn, k) {{
                    const o = ctx.createOscillator();
                    o.type = 'sine'; o.frequency.value = f; o.detune.value = sgn * 3.5;
                    const g = ctx.createGain(); g.gain.value = 0.22;  // 揺れの中心
                    o.connect(g); g.connect(padBus);
                    // ゆっくりした音量のうねり(息づかい)。音ごとに速さを変える。
                    const swl  = ctx.createOscillator();
                    swl.frequency.value = 0.03 + idx * 0.016 + k * 0.004;
                    const swlG = ctx.createGain(); swlG.gain.value = 0.18;
                    swl.connect(swlG); swlG.connect(g.gain);
                    o.start(); swl.start();
                }});
            }});
            padBus.gain.setTargetAtTime(BGM ? 0.11 : 0.06, t, 5.0);  // BGMはパッドを主役に
            // ごく弱い低い風(ザーザー感が出ない範囲で“自然”をひとさじ)
            const wind = ctx.createBufferSource(); wind.buffer = makeNoiseBuffer(true); wind.loop=true;
            const wlp  = ctx.createBiquadFilter(); wlp.type='lowpass'; wlp.frequency.value=280;
            const wg   = ctx.createGain(); wg.gain.value=0;
            wind.connect(wlp); wlp.connect(wg); wg.connect(master);
            wind.start();
            wg.gain.setTargetAtTime(0.03, t, 3.0);
            return padBus;
        }}

        function buildNode(i) {{
            const depth = BIRDS[i].depth || 'b3';
            const nv    = BIRDS[i].nv   || 1;
            const els   = [];
            // ハイパスを上げて低域の暗騒音(風・交通・空調のゴロゴロ)を強めに切る
            const hp = ctx.createBiquadFilter(); hp.type='highpass'; hp.frequency.value=820;
            for (let v = 0; v < nv; v++) {{
                const el = document.getElementById('ra_' + i + '_' + v);
                if (el) {{ els.push(el); ctx.createMediaElementSource(el).connect(hp); }}
            }}
            // 鳥のさえずり帯域(〜3.5kHz)を持ち上げて声の存在感を上げる
            const presence = ctx.createBiquadFilter();
            presence.type='peaking'; presence.frequency.value=3500;
            presence.Q.value=0.9; presence.gain.value=5.0;
            const filter  = ctx.createBiquadFilter(); filter.type='lowpass';
            const gate    = ctx.createGain(); gate.gain.value=1;
            const agcGain = ctx.createGain(); agcGain.gain.value=1;
            const gain    = ctx.createGain();
            const chGain  = ctx.createGain(); chGain.gain.value=1;
            const pan     = makePanner();
            const wet     = ctx.createGain();
            const ana     = ctx.createAnalyser(); ana.fftSize=512;

            hp.connect(presence); presence.connect(filter);
            filter.connect(ana); filter.connect(gate);
            gate.connect(agcGain); agcGain.connect(gain);
            gain.connect(chGain);
            chGain.connect(pan.node); pan.node.connect(master);
            chGain.connect(wet); wet.connect(reverb);

            // BGMでは鳥をやや控えめ・高域を抑えめにして、パッドとノイズの角を丸める
            gain.gain.value        = D[depth].gain * (BGM ? 0.75 : 1.0);
            filter.frequency.value = BGM ? Math.min(D[depth].freq, 5200) : D[depth].freq;
            wet.gain.value         = D[depth].wet;

            // 初期水平位置: 均等間隔
            const left = 20 + (i / Math.max(n-1, 1)) * 60;
            setPan({{ pan, depth }}, left);

            // ── 群れ: 同種が複数いる鳥は“ゴースト声”を足して厚くする ──────
            // 音源は1つ(chGain)を分岐。各個体をわずかに遅延・定位ずらしで重ね、
            // 同じ声が少しずつ間をずらして鳴く=群れの質感を音源を増やさず作る。
            // chGain から分岐するので呼応(call-and-response)で群れごと前後する。
            const flockN = BIRDS[i].flock || 1;
            for (let f = 1; f < flockN; f++) {{
                const dl = ctx.createDelay(1.0);
                dl.delayTime.value = 0.09 + Math.random() * 0.33;   // 群れのずれ
                const fg = ctx.createGain();
                fg.gain.value = 0.55 - f * 0.10;                    // 後ろの個体ほど小さく
                const fp = makePanner();
                chGain.connect(dl); dl.connect(fg);
                fg.connect(fp.node); fp.node.connect(master);
                const fw = ctx.createGain(); fw.gain.value = D[depth].wet * 1.3;
                fg.connect(fw); fw.connect(reverb);
                const goff = (f % 2 ? 1 : -1) * (10 + f * 7);       // 左右に広げる
                setPan({{ pan: fp, depth }}, left + goff);
            }}

            const cur = els.length > 1 ? pickVariant(i, -1) : 0;
            chGain.gain.value = 0;   // 開始時は無音。スケジューラが鳴き始めを決める。
            return {{ els, cur, filter, gain, agcGain, chGain, wet, gate, ana,
                      pan, depth, phase: 'rest', until: 0,
                      buf: new Float32Array(ana.fftSize) }};
        }}

        function updateChip(i, active) {{
            const chip = document.getElementById('ra_chip_' + i);
            const note = chip ? chip.querySelector('.ra_note_' + i) : null;
            if (chip) chip.classList.toggle('ra_active', active);
            // ♪ は常に固定幅の枠を確保し、表示/非表示だけ切り替える(チップ位置のブレ防止)
            if (note) note.style.visibility = active ? 'visible' : 'hidden';
        }}

        function gateTick() {{
            if (!running || !ctx) return;
            const t = ctx.currentTime;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                nd.ana.getFloatTimeDomainData(nd.buf);
                let sum = 0;
                for (let k = 0; k < nd.buf.length; k++) sum += nd.buf[k]*nd.buf[k];
                const rms = Math.sqrt(sum / nd.buf.length);

                // ① ノイズゲート(休符中の雑音をより強く絞る)
                nd.gate.gain.setTargetAtTime(rms < RA_GATE_THRESH ? RA_GATE_FLOOR : 1.0, t, 0.06);

                // ② AGC(静かな録音を上げすぎない=雑音の増幅を抑える)
                if (rms > RA_GATE_THRESH) peakRMS[i] = peakRMS[i]*0.92 + rms*0.08;
                else                      peakRMS[i] *= 0.9998;
                const agcT = Math.min(Math.max(AGC_TARGET / Math.max(peakRMS[i], 0.003),
                                               AGC_MIN), RA_AGC_MAX);
                nd.agcGain.gain.setTargetAtTime(agcT, t, 3.0);

                // ③ 鳥ごとに独立した“鳴く⇄休む”サイクル。
                // 同時発声の目安が ~1.2 なので、ソロ(=この鳥はこう鳴くんだ)も
                // 重なりも無音も、規則に縛られずばらばらに生まれる。
                if (t >= nd.until) {{
                    if (nd.phase === 'sing') {{
                        nd.phase = 'rest';
                        nd.chGain.gain.setTargetAtTime(0.0, t, 0.7);   // しずかに引く
                        nd.until = t + restDuration();
                    }} else {{
                        nd.phase = 'sing';
                        nd.chGain.gain.setTargetAtTime(1.0, t, 0.45);  // 鳴き始め
                        nd.until = t + singDuration();
                    }}
                }}

                // UI: 鳴いている鳥のチップは、その鳥の発声フレーズの間ずっと点灯。
                // (録音内の細かな無音で点滅させない=どの鳥が鳴いているか分かる)
                updateChip(i, nd.phase === 'sing');
            }}
            rafId = requestAnimationFrame(gateTick);
        }}

        function start() {{
            ctx    = new (window.AudioContext || window.webkitAudioContext)();
            // サンドボックス iframe やモバイルでは AudioContext が suspended で
            // 始まり、currentTime が進まない=スケジューラが動かず無音になる。
            // クリック(ユーザー操作)内で必ず resume しておく。
            try {{ ctx.resume(); }} catch(e) {{}}
            master = ctx.createDynamicsCompressor();
            master.threshold.value=-10; master.knee.value=10;
            master.ratio.value=4; master.attack.value=0.003; master.release.value=0.25;
            master.connect(ctx.destination);
            reverb = ctx.createConvolver(); reverb.buffer = makeReverbIR();
            const rvRet = ctx.createGain(); rvRet.gain.value=0.9;
            reverb.connect(rvRet); rvRet.connect(master);
            buildAmbient();

            for (let i = 0; i < n; i++) {{
                peakRMS.push(0.01);
                const nd = buildNode(i);
                nodes.push(nd);
                // 1羽目はすぐ鳴き始め(開始直後に必ず声が出る)、残りは少しずつずらす。
                nd.phase = 'rest';
                nd.until = ctx.currentTime + (i === 0 ? 0 : 0.4 + Math.random() * 4.5);
            }}

            nodes.forEach(nd => {{
                const el = nd.els[nd.cur];
                if (el) el.play().catch(()=>{{}});
            }});
            running = true;
            btn.textContent = '■ 止める';
            btn.style.background = '#b8c8a0';
            rafId = requestAnimationFrame(gateTick);
        }}

        function stop() {{
            if (rafId) {{ cancelAnimationFrame(rafId); rafId = null; }}
            nodes.forEach(nd => nd.els.forEach(el => {{ try {{ el.pause(); }} catch(e){{}} }}));
            if (ctx) ctx.suspend();
            running = false;
            btn.textContent = '🎙 ラジオを始める';
            btn.style.background = '#cfd9b8';
            for (let i = 0; i < n; i++) updateChip(i, false);
        }}

        btn.addEventListener('click', () => {{
            if (running) stop();
            else if (ctx) {{ ctx.resume(); nodes.forEach(nd => {{ const el = nd.els[nd.cur]; if (el) el.play().catch(()=>{{}}); }}); running=true; btn.textContent='■ 止める'; btn.style.background='#b8c8a0'; rafId=requestAnimationFrame(gateTick); }}
            else start();
        }});
    }})();
    </script>
    """

    components.html(html, height=_COMPONENT_HEIGHT)
