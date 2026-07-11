"""Toris Collection - Streamlit アプリ"""
import streamlit as st
import streamlit.components.v1 as components
import random
import math
import json
from datetime import datetime, timedelta
from species_loader import BIOMES, BIOME_MIGRATION, PLANTS, INSECTS, BIRDS, SEASON_TEMP_OFFSET
from engine import (
    build_network, calculate_arrival_probability, run_turn,
    current_temperature, force_directed_layout,
    suggest_for_bird, network_stats,
)
import absence_loop
import mementos as mem
from pathlib import Path
import base64
import xc_client  # Python 3.14 並行インポートバグ対策: ritual.py より先にロード
from ritual import render_ritual  # 儀式UI(距離メカニクス)
import observation_log  # 儀式での近距離観察記録の保存
import community  # 集合アトラス(みんなの庭) = 現在MVPでは非表示(community.py 自体は残置)
from radio import render_radio, current_app_season, weeks_until_next_season, _SEASON_META
import daily  # 今日の庭(Wordle 型・1日1回・全員共通の入口)
import save_code  # ローカル保存 MVP: セーブコードの往復(サーバーに送らない)
import eco_log  # 生態ログ(「なぜ来たか」の蓄積・重複除去)
import badges  # 会った日数の節目バッジ(静かな演出)
import secrets as _secrets_mod  # ローカル識別子の生成用(st.secrets とは無関係)
import ads  # 広告UIの土台(プレースホルダー。実SDK未接続)
import garden_items  # 広告リワード「今日の庭アイテム」(6種・6時間限定)
import tutorial  # 新規スタート向けチュートリアル(案内文言・ステップ進行の純粋ロジック)


# ============================================================
# Sprite 管理(ドット絵対応)
# sprites/birds/{bird_id}.png を読み込み、なければ None を返す。
# 図鑑・フィールド・落とし物の各所でドット絵があれば使用、なければEmojiにフォールバック。
# ============================================================
SPRITES_DIR = Path(__file__).parent / "designbird"


@st.cache_data(show_spinner=False, max_entries=100)
def _get_bird_sprite_data_url(bird_id: str) -> str | None:
    """鳥のドット絵スプライトを data: URL として返す。
    sprites/birds/{bird_id}.png がなければ None を返す。

    Returns:
        str: "data:image/png;base64,..." 形式の URL
        None: スプライトファイルが存在しない場合
    """
    from data import SPRITE_ALIASES
    sprite_id = SPRITE_ALIASES.get(bird_id, bird_id)  # 新種は既存のドット絵を流用
    path = SPRITES_DIR / f"{sprite_id}.png"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


def render_bird_sprite_html(bird_id: str, size_px: int = 64,
                            fallback_emoji: str = "🐦") -> str:
    """鳥のスプライトを HTML img タグまたは Emoji として返す。
    ドット絵があれば pixelated レンダリングで表示、なければ Emoji にフォールバック。
    """
    sprite_url = _get_bird_sprite_data_url(bird_id)
    if sprite_url:
        return (
            f'<img src="{sprite_url}" width="{size_px}" height="{size_px}" '
            f'style="image-rendering:pixelated; image-rendering:crisp-edges; '
            f'vertical-align:middle;" alt="{bird_id}" />'
        )
    return (
        f'<span style="font-size:{int(size_px * 0.8)}px; line-height:1; '
        f'vertical-align:middle;">{fallback_emoji}</span>'
    )


# ============================================================
# 詳細ドット絵(高解像度、種ごとに個別制作)
# designbird/{bird_id}_detail.png があれば図鑑の詳細表示でのみ大きく使う。
# ファイルが無い種は今まで通り(render_bird_sprite_html の簡易スプライトのみ)。
# SPRITE_ALIASES は使わない(詳細画像は流用せず、制作済みの種だけに厳密に紐づける)。
# 存在判定・パス解決は detail_sprites.py(Streamlit非依存の純粋関数、テスト対象)に委譲。
# ============================================================
import detail_sprites


@st.cache_data(show_spinner=False, max_entries=100)
def _get_bird_detail_image_data_url(bird_id: str) -> str | None:
    """種の詳細ドット絵(高解像度)を data: URL として返す。
    designbird/{bird_id}_detail.png が無ければ None(呼び出し側は何もしない=
    既存の簡易スプライト表示のみのまま)。
    """
    if not detail_sprites.has_detail_image(bird_id):
        return None
    path = detail_sprites.detail_image_path(bird_id)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


def render_bird_detail_image_html(bird_id: str, max_width_px: int = 320) -> str | None:
    """詳細ドット絵があれば図鑑の詳細表示に大きく載せる img タグを返す。
    無ければ None を返す(呼び出し側は何も描画しない)。
    """
    detail_url = _get_bird_detail_image_data_url(bird_id)
    if not detail_url:
        return None
    return (
        f'<div style="text-align:center; margin-bottom:10px;">'
        f'<img src="{detail_url}" '
        f'style="width:100%; max-width:{max_width_px}px; height:auto; '
        f'image-rendering:pixelated; image-rendering:crisp-edges; '
        f'border-radius:12px;" alt="{bird_id}" />'
        f'</div>'
    )


def _migrate_biome(biome_id):
    """既存テスターのスプレッドシートに残っている旧バイオームIDを新IDに変換"""
    if biome_id in BIOMES:
        return biome_id
    return BIOME_MIGRATION.get(biome_id, "kyoto")


@st.cache_data(show_spinner=False, max_entries=200)
def _cached_arrival_probability(bird_id, planted_tuple, biome_id, month):
    """シミュレーターでの確率計算をキャッシュ。
    planted_tuple は順序非依存のキー(ソート済tuple)。
    """
    from engine import calculate_arrival_probability as _calc
    G, _ = build_network(list(planted_tuple), biome_id, month)
    info = _calc(bird_id, G, biome_id, month)
    # session_state を抱える NetworkX 等は返さず、必要な数値のみ返す
    return {
        "probability": info["probability"],
        "temp_fit": info["temp_fit"],
        "biome_bonus": info["biome_bonus"],
        "food_score": info["food_score"],
        "rarity_factor": info["rarity_factor"],
        "incoming_paths": info.get("incoming_paths", []),
    }


@st.cache_data(show_spinner=False, max_entries=20, ttl=3600)
def _cached_network_layout(planted_tuple, biome_id, month, residents_tuple):
    """ネットワーク図の構築とレイアウト計算をまとめてキャッシュ。
    軽量版: 食物経路がない孤立した鳥は除外する(ノード数を10〜20程度に抑える)。
    return: dict (nodes, edges, pos, hub) JSONシリアライズ可能な形
    """
    from engine import network_stats
    G_full, temp = build_network(list(planted_tuple), biome_id, month)

    # サブグラフ: 植物・昆虫は全部残し、鳥は「食物経路がある」または「滞在中」のみ残す
    nodes_to_keep = set()
    for n, data in G_full.nodes(data=True):
        kind = data.get("kind")
        if kind in ("plant", "insect"):
            nodes_to_keep.add(n)
        elif kind == "bird":
            # 食物経路がある(in_degree > 0)、または現在滞在中の鳥のみ残す
            if G_full.in_degree(n) > 0 or n in residents_tuple:
                nodes_to_keep.add(n)
    G = G_full.subgraph(nodes_to_keep).copy()

    # サブグラフでレイアウト計算(ノード数が大幅に減るため高速)
    pos = force_directed_layout(G, width=1200, height=900)
    stats = network_stats(G)

    # NetworkX グラフをシリアライズ可能な dict に変換
    nodes = []
    for n, data in G.nodes(data=True):
        nodes.append({
            "id": n,
            "kind": data.get("kind"),
            "label": data.get("label"),
            "color": data.get("color"),
            "in_degree": G.in_degree(n),
            "out_degree": G.out_degree(n),
            "is_resident": n in residents_tuple,
        })
    edges = []
    for u, v, data in G.edges(data=True):
        edges.append({
            "src": u, "tgt": v,
            "weight": data.get("weight", 0.5),
        })
    return {
        "nodes": nodes,
        "edges": edges,
        "pos": {k: list(v) for k, v in pos.items()},
        "stats": stats,
        "temp": temp,
    }


# Google Sheets バックエンド
try:
    import sheets_client as sc
    SHEETS_AVAILABLE = True
except Exception as _e:
    SHEETS_AVAILABLE = False
    _sheets_error = str(_e)

# xeno-canto は遅延インポート(オフライン時もアプリは起動する)
try:
    from xc_client import download_audio, get_citation
    XC_AVAILABLE = True
except Exception:
    XC_AVAILABLE = False


# 音源バイトをセッション越しメモリキャッシュ
# Streamlit Cloud のプロセス再起動でも、最初のテスターが取得すれば
# それ以降の全リクエストが共有する
@st.cache_data(show_spinner=False, max_entries=50, ttl=3600)
def _cached_audio_bytes(scientific_name: str):
    """鳥の鳴き声を bytes で返す。一度ダウンロードしたらメモリキャッシュ。
    Returns: (bytes, citation_dict) または (None, None)
    """
    if not XC_AVAILABLE:
        return None, None
    try:
        path = download_audio(scientific_name)
        if not (path and path.exists()):
            return None, None
        with open(path, "rb") as f:
            data = f.read()
        cit = get_citation(scientific_name)
        return data, cit
    except Exception:
        return None, None


def render_bird_audio(b_id: str, bird: dict, key_prefix: str = ""):
    """
    鳥の鳴き声を再生するUIコンポーネント。
    初回クリックでダウンロード、2回目以降はキャッシュから即再生。
    エラー時は静かにフォールバック(アプリを落とさない)。

    同じ鳥が複数のタブ・箇所(庭タブの在留リスト/図鑑/今日の庭カード等)で
    同時にこのコンポーネントを描くと、ボタンの `key` が衝突して
    StreamlitDuplicateElementKey で落ちる。呼び出し箇所ごとに一意な
    `key_prefix` を渡して回避する(既定は空文字=従来どおり、図鑑タブ用)。
    ロード済みキャッシュ(`audio_loaded_{b_id}`)はどの呼び出し元からでも
    共有してよい(一度取得済みなら別の場所でも即再生でよいため、あえて
    prefix を付けない)。
    """
    if not XC_AVAILABLE:
        st.caption(f"🔊 {bird['name']}の鳴き声 (xeno-canto未読込)")
        return

    sci = bird.get("scientific")
    if not sci:
        return

    key = f"audio_loaded_{b_id}"
    # 自動ロードはしない。ボタンでユーザーがトリガする形
    cols = st.columns([1, 3])
    with cols[0]:
        if st.button("🔊 聴く", key=f"play_{key_prefix}{b_id}"):
            st.session_state[key] = True

    if st.session_state.get(key):
        with st.spinner(f"{bird['name']}の鳴き声を取得中..."):
            audio_bytes, cit = _cached_audio_bytes(sci)

        if audio_bytes:
            try:
                st.audio(audio_bytes, format="audio/mp3", loop=True)
            except Exception as e:
                st.caption(f"再生エラー: {e}")
        elif xc_client.COMMERCIAL_ONLY and xc_client.is_nc_only(sci):
            st.caption(
                "🔒 この鳥の声はNC(非商用)音源のため、録音準備中です。"
                "図鑑や庭での観察は、これまでどおり楽しめます。"
            )
        else:
            st.caption("録音が見つかりませんでした(xeno-cantoに登録なしまたは接続失敗)")


def render_field_view(planted_ids, resident_ids, month, temperature):
    """
    フィールドの様子を SVG で描画。
    地面に植えた植物のアイコンを並べ、鳥たちは植物の上空にランダム配置。
    空の色は「月」と「現在の時刻(端末ローカル)」の組み合わせで変化する。
    """
    import random as _r

    if not planted_ids and not resident_ids:
        st.info("植物を植えて時間を進めると、ここに鳥たちが現れます。")
        return

    # === 時間帯の判定(端末のローカル時刻に基づく) ===
    now_hour = datetime.now().hour
    if 5 <= now_hour < 7:
        period = "dawn"     # 朝焼け
    elif 7 <= now_hour < 17:
        period = "day"      # 昼
    elif 17 <= now_hour < 19:
        period = "dusk"     # 夕焼け
    else:
        period = "night"    # 夜

    # === 月による色補正(季節感)+ 時間帯による主軸 ===
    if period == "dawn":
        sky_top, sky_bot = "#ffb088", "#ffe5cc"
    elif period == "dusk":
        sky_top, sky_bot = "#ff8a70", "#ffd29a"
    elif period == "night":
        sky_top, sky_bot = "#1a2848", "#3a4870"
    else:
        # 昼: 月による色合いの違いを残す
        if month in (3, 4, 5):
            sky_top, sky_bot = "#bce0ff", "#fff5e6"
        elif month in (6, 7, 8):
            sky_top, sky_bot = "#9bd0ff", "#ffefcc"
        elif month in (9, 10, 11):
            sky_top, sky_bot = "#d4a96a", "#f8e6c8"
        else:
            sky_top, sky_bot = "#a8c0d8", "#e0e8ee"

    W, H = 900, 320
    GROUND_Y = 240

    svg = [
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%; height:auto; border-radius:10px;">',
        # 空のグラデーション
        '<defs><linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">',
        f'<stop offset="0%" stop-color="{sky_top}"/>',
        f'<stop offset="100%" stop-color="{sky_bot}"/>',
        '</linearGradient></defs>',
        f'<rect x="0" y="0" width="{W}" height="{GROUND_Y}" fill="url(#sky)"/>',
        # 地面(夜は暗め)
        f'<rect x="0" y="{GROUND_Y}" width="{W}" height="{H - GROUND_Y}" '
        f'fill="{"#3a4d2a" if period == "night" else "#7ba053"}"/>',
        f'<rect x="0" y="{GROUND_Y}" width="{W}" height="6" '
        f'fill="{"#2a3a1a" if period == "night" else "#5a8035"}"/>',
    ]

    # === 太陽・月・星の描画 ===
    if period == "night":
        # 月
        svg.append(f'<circle cx="{W - 80}" cy="60" r="26" fill="#f8f0d4" opacity="0.92"/>')
        svg.append(f'<circle cx="{W - 70}" cy="56" r="22" fill="{sky_top}" opacity="1"/>')
        # 星をランダムに配置
        star_rng = _r.Random(month)
        for _ in range(15):
            sx = star_rng.randint(20, W - 20)
            sy = star_rng.randint(10, GROUND_Y - 80)
            svg.append(
                f'<circle cx="{sx}" cy="{sy}" r="1.2" fill="#fff5d8" opacity="0.85"/>'
            )
    elif period == "dawn":
        # 朝の太陽(地平線寄り、オレンジ)
        svg.append(f'<circle cx="{W - 100}" cy="160" r="32" fill="#ffb060" opacity="0.95"/>')
        svg.append(f'<circle cx="{W - 100}" cy="160" r="44" fill="#ffd49a" opacity="0.4"/>')
    elif period == "dusk":
        # 夕日(地平線寄り、赤)
        svg.append(f'<circle cx="{W - 100}" cy="170" r="34" fill="#ff7a50" opacity="0.95"/>')
        svg.append(f'<circle cx="{W - 100}" cy="170" r="48" fill="#ffa878" opacity="0.4"/>')
    elif month in (12, 1, 2):
        svg.append(f'<circle cx="{W - 80}" cy="60" r="22" fill="#f5f0d8" opacity="0.85"/>')
    else:
        svg.append(f'<circle cx="{W - 80}" cy="60" r="26" fill="#fff2a8" opacity="0.9"/>')

    # 植物の配置(均等間隔で地面に並べる)
    plants_to_draw = [p for p in planted_ids if p in PLANTS]
    plant_positions = {}  # 各植物の中央x座標を記録
    if plants_to_draw:
        n = len(plants_to_draw)
        spacing = (W - 100) / max(n, 1)
        for i, pid in enumerate(plants_to_draw):
            cx = 60 + spacing * (i + 0.5)
            plant_positions[pid] = cx
            icon = PLANTS[pid].get("icon", "🌱")
            name = PLANTS[pid]["name"]
            # 植物アイコン(絵文字)を大きく描く
            svg.append(
                f'<text x="{cx:.0f}" y="{GROUND_Y - 8}" text-anchor="middle" '
                f'font-size="56" dominant-baseline="alphabetic">{icon}</text>'
            )
            # 名前ラベル(地面下)
            plant_label_color = "#e0d8c0" if period == "night" else "#3a3a3a"
            svg.append(
                f'<text x="{cx:.0f}" y="{GROUND_Y + 22}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="11" fill="{plant_label_color}" '
                f'font-weight="600">{name}</text>'
            )

    # 鳥の配置: 各鳥を「最も食物関係が強い植物」に止まらせる
    rng = _r.Random(sum(hash(b) for b in resident_ids) + month)  # 安定的にランダム
    placed = []  # 既に配置した鳥の(cx, cy)
    for b_id in resident_ids:
        if b_id not in BIRDS:
            continue
        bird = BIRDS[b_id]
        # 関連植物を探す(eats_plants でリンクするもの、かつ植えてある)
        linked_plants = [p for p in bird["eats_plants"]
                         if p in plant_positions]
        if linked_plants:
            target = rng.choice(linked_plants)
            base_x = plant_positions[target]
        elif plant_positions:
            # リンクなし: 任意の植物の上
            base_x = list(plant_positions.values())[
                rng.randint(0, len(plant_positions) - 1)
            ]
        else:
            base_x = rng.uniform(80, W - 80)

        # 植物の上空にランダム配置(±60px、高さ80-180)
        bx = base_x + rng.uniform(-50, 50)
        by = rng.uniform(80, GROUND_Y - 80)
        # 重なり回避(簡易): 既存の鳥と近すぎたらずらす
        for px, py in placed:
            if abs(bx - px) < 50 and abs(by - py) < 30:
                bx += 60
                by -= 25
        placed.append((bx, by))

        color = bird.get("color", "#6a8ac8")
        # スプライト(ドット絵)があれば優先表示、なければ既存の楕円描画
        sprite_url = _get_bird_sprite_data_url(b_id)
        svg.append(f'<g>')
        if sprite_url:
            # ドット絵を 48x48 で表示(中央を bx, by に)
            svg.append(
                f'<image href="{sprite_url}" '
                f'x="{bx - 24:.0f}" y="{by - 24:.0f}" '
                f'width="48" height="48" '
                f'style="image-rendering:pixelated;"/>'
            )
        else:
            # 鳥の絵: 楕円(体)と小さい円(頭)、ライン(くちばし)
            # 体
            svg.append(
                f'<ellipse cx="{bx:.0f}" cy="{by:.0f}" rx="14" ry="10" '
                f'fill="{color}" stroke="#fff" stroke-width="2"/>'
            )
            # 頭
            svg.append(
                f'<circle cx="{bx + 11:.0f}" cy="{by - 6:.0f}" r="7" '
                f'fill="{color}" stroke="#fff" stroke-width="1.5"/>'
            )
            # くちばし
            svg.append(
                f'<polygon points="{bx + 17:.0f},{by - 6:.0f} '
                f'{bx + 23:.0f},{by - 5:.0f} {bx + 17:.0f},{by - 4:.0f}" '
                f'fill="#e8a040"/>'
            )
            # 目
            svg.append(
                f'<circle cx="{bx + 13:.0f}" cy="{by - 7:.0f}" r="1.5" fill="#222"/>'
            )
        # 名前ラベル
        svg.append(
            f'<text x="{bx:.0f}" y="{by + 24:.0f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="10" font-weight="600" '
            f'fill="#222" style="paint-order:stroke; stroke:#fff; stroke-width:3;">'
            f'{bird["name"]}</text>'
        )
        svg.append('</g>')

    # 月・気温の小さなインジケーター(右上)
    label_color = "#f0e8d0" if period == "night" else "#3a3a3a"
    period_label = {"dawn": "朝", "day": "", "dusk": "夕", "night": "夜"}[period]
    period_text = f" · {period_label}" if period_label else ""
    svg.append(
        f'<text x="20" y="28" font-family="sans-serif" font-size="13" '
        f'fill="{label_color}" font-weight="600">'
        f'{month}月 {temperature:.1f}℃{period_text}</text>'
    )

    svg.append("</svg>")
    st.markdown("".join(svg), unsafe_allow_html=True)


st.set_page_config(page_title="#Toris Collection#", page_icon="🐦", layout="wide")

st.markdown("""
<style>
    .bird-card {
        background: #f7f9f5; border-left: 4px solid #7ba87b;
        padding: 10px 14px; margin: 6px 0; border-radius: 4px;
    }
    .bird-card-new { border-left-color: #e8a33d; background: #fdf8ee; }
    .plant-chip {
        display: inline-block; background: #e8efd8; color: #3a5a3a;
        padding: 3px 10px; margin: 3px; border-radius: 12px; font-size: 0.85em;
    }
    .stat-box {
        background: #f0f4ea; padding: 8px 12px; border-radius: 6px; margin: 4px 0;
    }
    h1 { color: #3a5a3a; }
    h2 { color: #4a6a4a; margin-top: 1.5em; }
</style>
""", unsafe_allow_html=True)


# 自動保存(ローカル保存MVP・案A上乗せ)で使う localStorage のキー名。
# 書き込み(_inject_local_save_write)・読み込みチェック(_inject_local_restore_check)・
# 壊れたデータの掃除(render_login_screen)の3箇所で共通に使う。
_LOCAL_SAVE_STORAGE_KEY = "toris_save_code"


def _log_local_restore_debug(msg: str):
    """2026-07-11追記(CEO実機報告調査用): Python側で分かったこと(クエリ受信・
    復元成否)を、ブラウザの console.log に "[TorisSave]" タグで出す。

    Android実機(Capacitor版)で自動継続がうまく動いていないという報告の原因を
    `adb logcat | Select-String "TorisSave"` で追えるようにするための、
    JS側ログ(_inject_local_save_write・_inject_local_restore_check)と対になる
    Python側からの片方向ログ。失敗しても本編の動作には一切影響させない
    (components.html自体が失敗しても何もしないだけ)。
    """
    try:
        components.html(
            f"""
            <script>
            try {{ console.log('[TorisSave]', {json.dumps(msg)}); }} catch (e) {{}}
            </script>
            """,
            height=0,
        )
    except Exception:
        pass


def _inject_pwa_head():
    """将来のTWA(Bubblewrap)化に備え、web app manifest をブラウザに知らせる
    (PWA/TWAの下準備)。

    Streamlit は <head> への直接注入手段を持たないため、components.html() が作る
    同一オリジンのiframe(allow-same-origin付き)経由で window.parent.document を
    操作する。失敗しても本編の動作(ラジオ・儀式・図鑑)には一切影響しない
    (try/exceptで握りつぶし、何もしないだけ)。
    manifest.json の実体は static/manifest.json
    (`.streamlit/config.toml` の enableStaticServing=true で配信、実ブラウザで
    Playwright により配信・注入を確認済み)。

    サービスワーカー(static/sw.js)は用意してあるが、あえて登録していない:
    Streamlit の静的ファイル配信 (AppStaticFileHandler) は `.js` 拡張子を
    許可リスト外として扱い、常に `Content-Type: text/plain` +
    `X-Content-Type-Options: nosniff` を返す仕様になっている
    (streamlit/web/server/app_static_file_handler.py の
    SAFE_APP_STATIC_FILE_EXTENSIONS 参照)。ブラウザは nosniff 指定時に
    text/plain のスクリプトを ServiceWorker として登録できないため、
    `navigator.serviceWorker.register()` は必ず失敗する
    (実機Playwrightで "unsupported MIME type" エラーを確認済み)。
    これは Streamlit 側の仕様上の制約であり、こちらのコードでは回避できない。
    詳細は docs/team/proposals/2026-07-05_PWA化調査.md を参照。
    """
    components.html(
        """
        <script>
        (function () {
          try {
            var doc = window.parent.document;
            if (!doc.querySelector('link[rel="manifest"]')) {
              var link = doc.createElement('link');
              link.rel = 'manifest';
              link.href = '/app/static/manifest.json';
              doc.head.appendChild(link);
            }
            if (!doc.querySelector('meta[name="theme-color"]')) {
              var meta = doc.createElement('meta');
              meta.name = 'theme-color';
              meta.content = '#7ba87b';
              doc.head.appendChild(meta);
            }
          } catch (e) {
            // Streamlit内部構造の変化等で失敗しても本編には影響させない
          }
        })();
        </script>
        """,
        height=0,
    )


_inject_pwa_head()


def _inject_native_share_button():
    """Android版(Capacitorラップ)でのみ現れる、共有用の小さな浮きボタンを注入する。

    Google Playの「Minimum Functionality」ポリシー(単なるWebサイト表示だけの
    ラッパーは審査で弾かれうる)への対応として、Web版にはないネイティブ機能を
    1つ追加する(`docs/team/proposals/2026-07-07_Phase1実行計画.md`後継の
    Capacitor方式検討を踏まえた実装)。

    `window.Capacitor.isNativePlatform()` で「Capacitorでラップされたネイティブ
    アプリ内かどうか」を判定し、真の場合のみボタンを表示する。通常のブラウザ
    (Streamlit Cloud上のWeb版)では `window.Capacitor` 自体が存在しないため、
    このボタンは一切表示されず、既存のWeb体験には影響しない
    (`_inject_pwa_head()` と同じ try/except で握りつぶすパターンに倣う)。

    Capacitorの `server.url` でリモートURLを直接ロードする方式でも、
    Capacitor Android の `WebViewLocalServer`(`handleProxyRequest`)が
    トップレベルのHTMLレスポンスにブリッジJSを注入する実装になっているため
    (`node_modules/@capacitor/android` の `Bridge.java`/`WebViewLocalServer.java`
    で確認済み)、`window.Capacitor` はネイティブアプリ内では自動的に利用可能になる。
    実際に共有シートを呼び出すには `@capacitor/share` プラグインが
    `android_app/`(Capacitorプロジェクト、npm install・cap sync 済み)側に
    導入されている必要がある。
    """
    components.html(
        """
        <script>
        (function () {
          try {
            var doc = window.parent.document;
            var win = window.parent;
            if (!win.Capacitor || !win.Capacitor.isNativePlatform || !win.Capacitor.isNativePlatform()) {
              return; // Web版(通常ブラウザ)では何もしない
            }
            if (doc.getElementById('toris-native-share-btn')) {
              return; // 二重注入防止
            }
            var btn = doc.createElement('button');
            btn.id = 'toris-native-share-btn';
            btn.textContent = '🐦 共有する';
            btn.style.cssText = [
              'position:fixed', 'right:14px', 'bottom:14px', 'z-index:9999',
              'background:#7ba87b', 'color:#fff', 'border:none',
              'border-radius:20px', 'padding:10px 16px', 'font-size:14px',
              'box-shadow:0 2px 8px rgba(0,0,0,0.2)', 'cursor:pointer'
            ].join(';');
            btn.addEventListener('click', function () {
              try {
                if (win.Capacitor.Plugins && win.Capacitor.Plugins.Share) {
                  win.Capacitor.Plugins.Share.share({
                    title: 'Toris Collection',
                    text: '手のひらの庭に鳥がやってくる、癒しアプリ「Toris Collection」',
                    url: 'https://toris-collection.onrender.com/',
                    dialogTitle: '共有する'
                  });
                }
              } catch (e) {
                // 共有に失敗しても本編の動作には影響させない
              }
            });
            doc.body.appendChild(btn);
          } catch (e) {
            // Capacitor非搭載環境・DOM構造の変化等で失敗しても本編には影響させない
          }
        })();
        </script>
        """,
        height=0,
    )


_inject_native_share_button()


def _inject_native_save_code_share_button(save_code_str: str):
    """Android版(Capacitorラップ)でのみ現れる、セーブコード共有ボタンを注入する。

    2026-07-09 追記(P1修正): CEO実機報告「セーブコードを書き出すのがよく
    わからん、押しても何も起こらない」への対応。`st.download_button` は
    ブラウザの `<a download>` + blob URL でファイルダウンロードを行う仕組みだが、
    CapacitorのネイティブWebView内ではこの種のダウンロードが正常に動作しない
    ことがある(WebViewの既知の制約)。Web版(通常ブラウザ)では
    `st.download_button` がそのまま動くため変更しない。

    アプリ版では代わりに、既に導入済みの `@capacitor/share` プラグイン
    (`_inject_native_share_button` と同じ判定パターン)でセーブコードの
    文字列をネイティブの共有シートに渡す。メモアプリ・メッセージ・
    クリップボードコピー等、OSの共有機能経由で確実に保存・送信できる。
    サイドバーの `st.code`(選択してコピー)も既存のフォールバックとして
    引き続き併存させる(Web版・アプリ版どちらでも確実に動く)。
    """
    payload = json.dumps(save_code_str)
    components.html(
        """
        <script>
        (function () {
          try {
            var doc = window.parent.document;
            var win = window.parent;
            if (!win.Capacitor || !win.Capacitor.isNativePlatform || !win.Capacitor.isNativePlatform()) {
              return; // Web版(通常ブラウザ)では st.download_button がそのまま動く
            }
            var SAVE_CODE = """ + payload + """;
            var existing = doc.getElementById('toris-save-share-btn');
            if (existing) {
              existing.dataset.saveCode = SAVE_CODE;
              return; // 二重注入防止(最新のセーブコードだけ更新)
            }
            var btn = doc.createElement('button');
            btn.id = 'toris-save-share-btn';
            btn.textContent = '💾 セーブコードを共有';
            btn.dataset.saveCode = SAVE_CODE;
            btn.style.cssText = [
              'position:fixed', 'right:14px', 'bottom:64px', 'z-index:9999',
              'background:#a8845a', 'color:#fff', 'border:none',
              'border-radius:20px', 'padding:10px 16px', 'font-size:14px',
              'box-shadow:0 2px 8px rgba(0,0,0,0.2)', 'cursor:pointer'
            ].join(';');
            btn.addEventListener('click', function () {
              try {
                if (win.Capacitor.Plugins && win.Capacitor.Plugins.Share) {
                  win.Capacitor.Plugins.Share.share({
                    title: 'Toris Collection セーブコード',
                    text: btn.dataset.saveCode,
                    dialogTitle: 'セーブコードを共有・保存'
                  });
                }
              } catch (e) {
                // 共有に失敗しても本編の動作には影響させない
              }
            });
            doc.body.appendChild(btn);
          } catch (e) {
            // Capacitor非搭載環境・DOM構造の変化等で失敗しても本編には影響させない
          }
        })();
        </script>
        """,
        height=0,
    )


def _render_save_code_copy_button(save_code_str: str):
    """セーブコードを「ボタン1つでクリップボードにコピー」できるようにする。

    2026-07-10追記(CEO依頼): 「バックアップが面倒」への対応。従来は
    `st.code()` の選択→コピーのみで、特にアプリ版(Capacitor WebView)では
    手順が分かりにくかった。ここでは components.html() のiframe内に、
    見た目にも分かりやすい単独のコピーボタンを描画する。

    コピー手段は3段のフォールバック(上から順に試す):
      1. Capacitorネイティブの `@capacitor/clipboard` プラグイン
         (アプリ版・最も確実。Web版では window.parent.Capacitor が無いのでスキップ)
      2. 標準Web API `navigator.clipboard.writeText()`
         (Web版・モダンWebViewで動作。Streamlit の components.html iframe には
         `allow="clipboard-write"` が付与されているため、iframe内からの
         呼び出しでも権限エラーにならない)
      3. 旧来の `document.execCommand('copy')`(1・2が使えない環境向けの最終手段)

    どの経路でも、成功/失敗を画面上のテキストで即座にフィードバックする
    (「押しても何も起こらない」ように見えないようにするため)。
    """
    payload = json.dumps(save_code_str)
    components.html(
        """
        <div id="toris-copy-wrap" style="font-family:inherit;">
          <button id="toris-copy-btn" style="
            width:100%; box-sizing:border-box; padding:12px 16px;
            background:#4a7c59; color:#fff; border:none; border-radius:10px;
            font-size:15px; font-weight:600; cursor:pointer;
          ">📋 セーブコードをコピー(ワンタップ)</button>
          <div id="toris-copy-feedback" style="
            margin-top:6px; font-size:13px; min-height:18px; text-align:center;
          "></div>
        </div>
        <script>
        (function () {
          var SAVE_CODE = """ + payload + """;
          var btn = document.getElementById('toris-copy-btn');
          var feedback = document.getElementById('toris-copy-feedback');

          function showFeedback(msg, ok) {
            feedback.textContent = msg;
            feedback.style.color = ok ? '#2e7d32' : '#b3261e';
          }

          async function copyViaCapacitor(text) {
            var parentWin = window.parent;
            if (parentWin && parentWin.Capacitor &&
                parentWin.Capacitor.isNativePlatform &&
                parentWin.Capacitor.isNativePlatform() &&
                parentWin.Capacitor.Plugins &&
                parentWin.Capacitor.Plugins.Clipboard) {
              await parentWin.Capacitor.Plugins.Clipboard.write({ string: text });
              return true;
            }
            return false;
          }

          async function copyViaWebApi(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              await navigator.clipboard.writeText(text);
              return true;
            }
            return false;
          }

          function copyViaExecCommand(text) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            var ok = false;
            try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
            document.body.removeChild(ta);
            return ok;
          }

          btn.addEventListener('click', async function () {
            var text = SAVE_CODE;
            var done = false;
            try { done = await copyViaCapacitor(text); } catch (e) { done = false; }
            if (!done) {
              try { done = await copyViaWebApi(text); } catch (e) { done = false; }
            }
            if (!done) {
              try { done = copyViaExecCommand(text); } catch (e) { done = false; }
            }
            if (done) {
              showFeedback('✅ セーブしました(コピー済み。貼り付けて保管してください)', true);
            } else {
              showFeedback('コピーできませんでした。下の「うまくいかない場合はこちら」を開いてお試しください', false);
            }
          });
        })();
        </script>
        """,
        height=90,
    )


def _inject_local_save_write():
    """現在の進行データを、ブラウザの localStorage に自動保存する(自動再開MVP)。

    案A(ブラウザストレージ、`docs/team/proposals/2026-07-04_ローカル保存MVP技術検討.md`)を
    案B(セーブコード方式・既存実装)へ"上乗せ"する形の実装。保存内容は
    `save_code.encode_current_state()` が作る、手動書き出し(サイドバー)と
    完全に同一フォーマットのセーブコード文字列そのものであり、復元時は
    既存の `_start_local_session(restore=...)` をそのまま再利用する
    (新しい復元ロジックは作らない)。

    `_inject_pwa_head()` と同じ一方向 JS 注入パターン(components.html、
    双方向のカスタムコンポーネントではない)。この関数は毎回の script rerun
    ごとに呼ばれ、そのつど最新の状態で localStorage を上書きする
    (「植える・時間経過・観察などの操作のたび」を、個別のフックを増やさず
    シンプルに満たす)。

    current_tester_id が未設定(まだセッションが始まっていない=ログイン画面)
    のときは何もしない。エンコードに失敗しても例外は投げず、本編の動作には
    一切影響させない(壊さない方針)。
    """
    if not st.session_state.get("current_tester_id"):
        return
    try:
        code = save_code.encode_current_state(st.session_state)
    except Exception:
        return
    code_json = json.dumps(code)  # JS文字列リテラルとして安全にエスケープする
    key_json = json.dumps(_LOCAL_SAVE_STORAGE_KEY)
    # 2026-07-11追記(CEO実機報告調査): Android実機(Capacitor版)で自動継続が
    # 効いていないように見える不具合の原因特定用デバッグログ。タグ "[TorisSave]" で
    # 統一し、`adb logcat | Select-String "TorisSave"` で書き込み成否・コード長を
    # 追えるようにする(既存の ads.py の "[TorisAd]" ログと同じ狙い・同じパターン)。
    # ログ自体は console.log の成否に関わらず try/except で握りつぶすので、
    # 本編の自動保存動作(壊さない方針)には一切影響しない。
    components.html(
        f"""
        <script>
        (function () {{
          var TAG = '[TorisSave]';
          function log(msg) {{ try {{ console.log(TAG, msg); }} catch (e) {{}} }}
          try {{
            window.top.localStorage.setItem({key_json}, {code_json});
            log('write ok, len=' + {code_json}.length);
          }} catch (e) {{
            // localStorage無効・シークレットモード等で失敗しても本編には影響させない
            log('write failed: ' + e);
          }}
        }})();
        </script>
        """,
        height=0,
    )


# ============= State =============
def _init_default_state():
    """真っさらな初期状態を session_state にセットする(Sheets には一切触れない)。
    「新規スタート」と、セーブコード復元の下準備の両方から呼ぶ。"""
    st.session_state.biome = "kyoto"
    st.session_state.month = datetime.now().month
    st.session_state.planted = []
    st.session_state.planted_at_map = {}
    st.session_state.residents = set()
    st.session_state.discovered = set()
    st.session_state.observed = {}
    st.session_state.bird_days = {}
    st.session_state.eco_log = []
    st.session_state.mementos = []
    st.session_state.mementos_set = set()
    st.session_state.bird_notes = {}
    st.session_state.bird_visited_biomes = {}
    st.session_state.log = []
    st.session_state.rng = random.Random()
    st.session_state.absence_events = []
    st.session_state.disturbance_events = []
    st.session_state.last_arrivals_info = {}
    st.session_state.recent_new_mementos = []
    # 広告リワード「今日の庭アイテム」(garden_items.py)。未配置ならNone。
    st.session_state.garden_item_placement = None
    st.session_state.garden_item_claimed_date = ""
    # 新規スタート用チュートリアル(スキップ可・強制ブロックなし)。
    # _start_local_session がこの直後に restore の有無で上書きする。
    st.session_state.tutorial_done = False
    st.session_state.tutorial_step = 0


def _start_local_session(restore=None):
    """新規スタート、またはセーブコードからの復元でセッションを開始する。

    ローカル保存 MVP: この関数は Google Sheets に一切依存しない。
    `current_tester_id` はサーバーに送らないローカル限定のランダム識別子で、
    既存の `sc.*` 呼び出し(ベストエフォートの副次書き込み)との互換のためだけに残す。
    """
    _init_default_state()
    st.session_state.current_tester_id = "local_" + _secrets_mod.token_hex(6)

    saved_at = None
    if restore:
        restore = dict(restore)
        saved_at = restore.pop("saved_at", None)
        for key, value in restore.items():
            st.session_state[key] = value

        # 旧バイオームIDの互換変換(既存の load_state_from_sheets と同じ安全弁)
        st.session_state.biome = _migrate_biome(st.session_state.get("biome", "kyoto"))

        # 現在のバイオームで無効な植物・図鑑にない鳥IDは静かに除外
        st.session_state.planted = [
            p for p in st.session_state.get("planted", [])
            if p in PLANTS and st.session_state.biome in PLANTS[p].get("biome", [])
        ]
        _max_plants = BIOMES.get(st.session_state.biome, {}).get("max_plants", 8)
        if len(st.session_state.planted) > _max_plants:
            st.session_state.planted = st.session_state.planted[:_max_plants]
        st.session_state.planted_at_map = {
            p: ts for p, ts in st.session_state.get("planted_at_map", {}).items()
            if p in st.session_state.planted
        }
        st.session_state.residents = {
            b for b in st.session_state.get("residents", set()) if b in BIRDS
        }
        st.session_state.discovered = {
            b for b in st.session_state.get("discovered", set()) if b in BIRDS
        }
        # 生態ログ(蓄積記録)も図鑑にない鳥IDが混ざっていれば静かに除外
        st.session_state.eco_log = [
            e for e in st.session_state.get("eco_log", []) or []
            if isinstance(e, dict) and e.get("bird_id") in BIRDS
        ]
        if not isinstance(st.session_state.get("mementos_set"), set):
            st.session_state.mementos_set = {
                m.get("memento_id") for m in st.session_state.get("mementos", [])
                if isinstance(m, dict) and m.get("memento_id")
            }

        # 派生値の再計算(セーブに含めていない、訪問記録から作る値)
        visited_by_bird = {}
        for m_rec in st.session_state.get("mementos", []):
            if not isinstance(m_rec, dict):
                continue
            bid = m_rec.get("via_bird_id", "")
            b_biome = m_rec.get("biome", "")
            if bid and b_biome:
                visited_by_bird.setdefault(bid, set()).add(b_biome)
        for bid in st.session_state.get("residents", set()):
            visited_by_bird.setdefault(bid, set()).add(st.session_state.biome)
        st.session_state.bird_visited_biomes = visited_by_bird

        st.session_state.month = datetime.now().month

        # セーブコードからの復元 = 既に一度プレイしたことがある人なので、
        # チュートリアル(新規スタート向けの案内)は表示しない。
        st.session_state.tutorial_done = True

    st.session_state.initialized = True

    # セーブコードに保存時刻があれば、離れていた時間ぶん生態系を進化させる。
    # これまで「ログイン時に Sheets の last_access_at と比較」していた不在中ループ
    # (受動的にコアループの心臓部)を、セーブコード復元でも同じ形で再現する。
    if saved_at:
        last_at = absence_loop.parse_iso(saved_at)
        if last_at:
            _evolve_since_last_visit(
                st.session_state.current_tester_id, last_at, datetime.now()
            )


def _inject_local_restore_check():
    """ログイン画面(まだセッションが始まっていない状態)で、ブラウザの
    localStorage に前回の自動保存(`_inject_local_save_write()`)があるかを確認し、
    あれば `?local_restore=<コード>` を付けてトップウィンドウごとリロードする。

    `ritual.py`(`?ritual_obs=...`)・`ads.py`(`?ad_result=...`)と同じ、
    JS→Python の片道経路(top window クエリパラメータ)パターンをそのまま踏襲する。
    localStorage が空、または読み取りに失敗した場合は何もしない
    (=通常の「新規スタート/セーブコードで再開」の選択画面がそのまま表示される)。

    無限リダイレクトループ対策: この関数はコードが実際に localStorage に
    存在するときにしか location を書き換えない(状態駆動・カウンタに依存しない)。
    復元が失敗した場合の後始末(localStorage の掃除・この関数自体の呼び出し停止)は
    呼び出し側の `render_login_screen()` が `_local_restore_failed` フラグで行う
    (`_handle_local_restore_query()` 参照)。

    実装上の注意(実機Playwrightで判明した制約): `components.html()` が作る
    iframe は `sandbox` 属性に `allow-top-navigation`/
    `allow-top-navigation-by-user-activation` を含まないため、iframe内の
    スクリプトから直接 `window.top.location.href = ...` を書き換えるトップ
    ウィンドウ遷移はブラウザに拒否される(コンソールに
    "Unsafe attempt to initiate navigation ... sandboxed" エラーが出る)。
    `ritual.py`/`ads.py` の同パターンがこれまで動いていたのは、常にボタン
    クリック(ユーザー操作)というユーザーアクティベーションの文脈内で
    遷移を発火していたため(`allow-top-navigation-by-user-activation` 相当が
    暗黙に満たされていた)。本関数はページロード直後に自動発火する必要があり
    ユーザー操作を伴わないため、`_inject_pwa_head()` と同じ「iframe内から
    `window.parent.document` に `<script>` 要素を生成して差し込む」手法を使い、
    実際の localStorage 読み取り・location 書き換えはトップウィンドウ自身の
    (サンドボックスされていない)実行コンテキストで行わせる。
    """
    # 実際にトップウィンドウで実行させたい中身(素のJS)。まず素朴な文字列として組み立て、
    # json.dumps() でJS文字列リテラルとして安全にエスケープしてから
    # <script>要素のtextContentへ渡す(手動でのJS文字列連結・二重エスケープを避ける)。
    # 2026-07-11追記(CEO実機報告調査): 上の _inject_local_save_write と同じ狙いの
    # "[TorisSave]" デバッグログ。トップウィンドウの実行コンテキストで動くコードなので、
    # 「保存はできているのに復元チェック側で見つからない」のか「復元チェック自体が
    # 走っていない」のかを実機ログで切り分けられるようにする。
    inner_script = (
        "(function () {\n"
        "  var TAG = '[TorisSave]';\n"
        "  function log(msg) { try { console.log(TAG, msg); } catch (e) {} }\n"
        "  try {\n"
        f"    var code = window.localStorage.getItem({json.dumps(_LOCAL_SAVE_STORAGE_KEY)});\n"
        "    if (!code) { log('restore-check: no code found'); return; }\n"
        "    log('restore-check: found code, len=' + code.length + ' -> redirecting');\n"
        "    var url = new URL(window.location.href);\n"
        "    url.searchParams.set('local_restore', code);\n"
        "    window.location.href = url.toString();\n"
        "  } catch (e) { log('restore-check failed: ' + e); }\n"
        "})();"
    )
    inner_script_json = json.dumps(inner_script)
    components.html(
        f"""
        <script>
        (function () {{
          var TAG = '[TorisSave]';
          function log(msg) {{ try {{ console.log(TAG, msg); }} catch (e) {{}} }}
          try {{
            var doc = window.parent.document;
            if (doc.getElementById('toris-local-restore-check')) return;  // 二重注入防止
            var script = doc.createElement('script');
            script.id = 'toris-local-restore-check';
            script.textContent = {inner_script_json};
            doc.head.appendChild(script);
            log('restore-check script injected into top document');
          }} catch (e) {{
            // Streamlit内部構造の変化・localStorage無効等で失敗しても
            // 通常の選択画面にフォールバックする
            log('failed to inject restore-check script: ' + e);
          }}
        }})();
        </script>
        """,
        height=0,
    )


def _handle_local_restore_query():
    """`_inject_local_restore_check()` が付けてきた `?local_restore=<コード>` を
    受け取り、既存の「セーブコードで再開」ロジック(`_start_local_session`)を
    そのまま呼び出して復元する。JS→Python の片道経路の受け口
    (`_handle_ritual_observation()` と同じ形)。

    `init_state()` の一番最初(ログイン画面を出すかどうかの判定より前)で呼ぶことで、
    復元に成功した回はログイン画面を一切経由せずアプリ本編に入れるようにする。

    復元に失敗しても例外は投げない(壊さない方針)。失敗時は
    `st.session_state["_local_restore_failed"] = True` を立てるだけで、実際の
    ブラウザ側クリーンアップ(localStorage の削除)は `render_login_screen()` に委譲する
    (ここでは Python 側の状態を汚さないことだけに専念する)。

    既にセッションが始まっている(current_tester_id 設定済み)場合は、
    クエリパラメータだけ消して何もしない(二重復元・意図しない上書きを防ぐ)。
    """
    raw = st.query_params.get("local_restore")
    if not raw:
        return
    # 2026-07-11追記(CEO実機報告調査): ここまで来た(=Python側が
    # ?local_restore= クエリを受け取れた)ことを "[TorisSave]" ログに残す。
    # JS側(_inject_local_restore_check)のログと合わせて見ることで、
    # 「JSはリダイレクトしたのにPython側に届いていない」パターンを切り分けられる。
    _log_local_restore_debug(f"python received local_restore query, len={len(raw)}")
    if st.session_state.get("current_tester_id") is not None:
        st.query_params.clear()
        return
    restored = None
    try:
        restored = save_code.decode_save(raw)
    except Exception:
        restored = None
    if restored is None:
        st.session_state["_local_restore_failed"] = True
        _log_local_restore_debug("decode failed (corrupted or unsupported format)")
    else:
        try:
            _start_local_session(restore=restored)
            _log_local_restore_debug("restore succeeded, session started")
        except Exception as e:
            st.session_state["_local_restore_failed"] = True
            _log_local_restore_debug(f"_start_local_session raised: {e}")
    # パラメータを消す(リロードで再処理しないように)。これ自体が再実行を誘発する。
    st.query_params.clear()


def render_login_screen():
    """アプリの入口画面。ログイン・認証の概念はない
    (current_tester_id が未設定の時に表示する、開始方法の選択画面)。

    「新規スタート」か「セーブコードを読み込んで再開」のどちらかを選ぶだけで、
    名前の登録や選択は一切不要(ローカル保存 MVP)。

    自動再開(ローカル保存MVP・案A上乗せ): 同じ端末・同じブラウザなら、通常は
    この画面を表示する前に `_handle_local_restore_query()`(`init_state()` の
    冒頭で呼ばれる)が localStorage の内容から自動的に復元を済ませてしまうため、
    ここが実際に表示されるのは (1) 初回アクセスで localStorage が空、
    (2) 自動復元が壊れたデータで失敗した、(3) ユーザーが意図的に
    「セッションをリセット」した、のいずれかの場合になる。
    """
    _restore_failed = st.session_state.pop("_local_restore_failed", False)

    st.markdown("# 🐦 Toris Collection")
    st.markdown(
        "<p style='color:#5a7a5a;'>土地を選び、植物を植え、時間が経つのを待つ。"
        "やってきた鳥たちの声に耳を澄まそう。</p>",
        unsafe_allow_html=True
    )
    st.info(
        "🔒 進行データ(図鑑・会った日数・落とし物など)は、この端末のこのブラウザにのみ"
        "保存されます。次にこの端末・このブラウザで開いたときは自動的に続きから"
        "始まります。ブラウザのデータを消す・別の端末や別のブラウザで開くと"
        "引き継がれません。ときどき「セーブコードを書き出す」(サイドバーの中)で"
        "バックアップしておくと安心です。",
        icon="💾",
    )

    if _restore_failed:
        # 壊れたセーブデータを検出: ブラウザ側を1回だけ掃除し、この回は
        # 自動復元チェックJSを再注入しない(無限リダイレクトループ防止)。
        # 掃除後は localStorage が空になるため、次回以降のチェックは
        # 何もしない(=通常の選択画面のまま)状態に自然に収束する。
        key_json = json.dumps(_LOCAL_SAVE_STORAGE_KEY)
        components.html(
            f"""
            <script>
            (function () {{
              var TAG = '[TorisSave]';
              function log(msg) {{ try {{ console.log(TAG, msg); }} catch (e) {{}} }}
              try {{
                window.top.localStorage.removeItem({key_json});
                log('cleaned up corrupted local save data');
              }} catch (e) {{
                log('cleanup failed: ' + e);
              }}
            }})();
            </script>
            """,
            height=0,
        )
        st.warning(
            "この端末に保存されていた進行データを自動で読み込めませんでした"
            "(壊れているか、対応していない形式のようです)。"
            "セーブコードをお持ちの場合は、下から読み込んで再開してください。",
            icon="⚠️",
        )
    else:
        _inject_local_restore_check()

    start_mode = st.radio(
        "はじめかた",
        options=["new", "restore"],
        format_func=lambda c: {
            "new": "🌱 新規スタート",
            "restore": "📥 セーブコードを読み込んで再開",
        }[c],
        label_visibility="collapsed",
        key="_start_mode_choice",
    )

    if start_mode == "new":
        if st.button("▶ はじめる", type="primary", use_container_width=True):
            _start_local_session()
            st.rerun()
    else:
        pasted_code = st.text_area(
            "セーブコードを貼り付け",
            key="_restore_code_text",
            height=120,
            placeholder="書き出しておいたセーブコードをここに貼り付けてください",
        )
        uploaded_file = st.file_uploader(
            "またはセーブファイルを選ぶ",
            type=["txt"],
            key="_restore_code_file",
        )
        code_to_use = pasted_code.strip() if pasted_code else ""
        if not code_to_use and uploaded_file is not None:
            try:
                code_to_use = uploaded_file.getvalue().decode("utf-8").strip()
            except Exception:
                code_to_use = ""

        if st.button("📥 読み込んで再開", type="primary", use_container_width=True):
            if not code_to_use:
                st.warning("セーブコードを貼り付けるか、ファイルを選んでください。")
            else:
                restored = save_code.decode_save(code_to_use)
                if restored is None:
                    st.error(
                        "セーブコードを読み込めませんでした。"
                        "コードが壊れているか、対応していない形式です。"
                    )
                else:
                    _start_local_session(restore=restored)
                    st.rerun()

    st.stop()


def load_state_from_sheets(tester_id):
    """[現在未使用・legacy] 選択されたテスターの状態を Sheets から読み込み、
    最終アクセス時刻からの経過時間に応じて生態系を時間進化させて
    session_state にセットする"""
    fs = None
    try:
        fs = sc.load_field_state(tester_id)
    except Exception:
        pass

    # 永続化される基礎情報
    raw_biome = (fs.get("biome") if fs else None) or "kyoto"
    st.session_state.biome = _migrate_biome(raw_biome)

    # マイグレーションが起きていれば即座にSheetsに書き戻す(以後の混乱を防ぐ)
    if fs and raw_biome != st.session_state.biome:
        try:
            sc.save_field_state(
                tester_id, st.session_state.biome,
                BIOMES[st.session_state.biome]["temp_mean"],
                f"month_{datetime.now().month}",
                [],  # 滞在鳥もリセット(旧バイオームの鳥は新バイオームでは不適合)
            )
        except Exception:
            pass

    try:
        all_planted_with_time = sc.load_active_plantings_with_time(tester_id)
        # 現在のバイオームで植えられない植物は除外(マイグレーション時の安全弁)
        valid_planted = [
            (pid, ts) for pid, ts in all_planted_with_time
            if pid in PLANTS and st.session_state.biome in PLANTS[pid].get("biome", [])
        ]
        # 同じ植物が複数行あっても1種として数える(収容力は「種数」なので重複排除)。
        # 重複は過去の自動補充や二重登録の名残。植え順を保ったまま最初の1件だけ残す。
        seen_pids = set()
        planted_unique = []
        planted_at_map = {}
        for pid, ts in valid_planted:
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            planted_unique.append(pid)
            if ts:
                planted_at_map[pid] = ts
        st.session_state.planted = planted_unique
        st.session_state.planted_at_map = planted_at_map
        # 収容力(種数)を超える分は切り詰める。過去の自動補充などで上限を超えて
        # 残ったデータ(例: 京都で 5/4)を恒久的に解消する。古い順に上限まで残す。
        _max_plants = BIOMES.get(st.session_state.biome, {}).get("max_plants", 8)
        if len(st.session_state.planted) > _max_plants:
            st.session_state.planted = st.session_state.planted[:_max_plants]
            st.session_state.planted_at_map = {
                p: ts for p, ts in planted_at_map.items()
                if p in st.session_state.planted
            }
        # 不整合(無効な植物・重複・容量超過)があれば Sheets 側もクリーンアップ
        if len(st.session_state.planted) < len(all_planted_with_time):
            try:
                sc.remove_all_plantings(tester_id)
                for pid in st.session_state.planted:
                    sc.add_planting(tester_id, pid)
                # 再読み込みで時刻を更新
                refreshed = sc.load_active_plantings_with_time(tester_id)
                st.session_state.planted_at_map = {
                    pid: ts for pid, ts in refreshed
                }
            except Exception:
                pass
    except Exception:
        st.session_state.planted = []
        st.session_state.planted_at_map = {}

    try:
        st.session_state.discovered = sc.load_collection_set(tester_id)
    except Exception:
        st.session_state.discovered = set()

    # 近距離観察記録(儀式で近くまで来た鳥)。{bird_id: {count, first, last}}
    try:
        st.session_state.observed = observation_log.load_observation_counts(tester_id)
    except Exception:
        st.session_state.observed = {}

    # 会った日数(鳥ごと・1日1カウント)。訪問ログから暦日を畳んで集計。
    # 「よく会う友だち」が増える受動的な習慣カウント(競争でなく愛着)。
    try:
        st.session_state.bird_days = sc.load_bird_days(tester_id)
    except Exception:
        st.session_state.bird_days = {}

    # 月は現実時間に同期する(ターン進行を廃止したため)
    now = datetime.now()
    st.session_state.month = now.month

    # 滞在中の鳥は前回保存された状態を復元(永続的な意味を持つ)
    saved_residents = set(fs.get("current_birds_list", [])) if fs else set()
    # 図鑑データやBIRDSキー変更などへの安全弁: 知られていない鳥IDは捨てる
    st.session_state.residents = {b for b in saved_residents if b in BIRDS}

    # 揮発する状態
    st.session_state.log = []
    st.session_state.rng = random.Random()
    st.session_state.absence_events = []
    st.session_state.last_arrivals_info = {}
    st.session_state.initialized = True

    # 落とし物コレクション(set of memento_id)
    try:
        st.session_state.mementos = sc.load_mementos(tester_id)
        st.session_state.mementos_set = {m["memento_id"] for m in st.session_state.mementos}
    except Exception:
        st.session_state.mementos = []
        st.session_state.mementos_set = set()

    # 鳥への個人メモ(発見地・自由メモ)
    try:
        st.session_state.bird_notes = sc.load_bird_notes(tester_id)
    except Exception:
        st.session_state.bird_notes = {}

    # 訪問記録(bird_visits)から、各鳥がどの土地で観測されたかを集計
    # mementos のレコードに biome 列があるのでそれを使う(最も簡単で十分)
    visited_by_bird = {}
    for m_rec in st.session_state.get("mementos", []):
        bid = m_rec.get("via_bird_id", "")
        biome = m_rec.get("biome", "")
        if bid and biome:
            visited_by_bird.setdefault(bid, set()).add(biome)
    # 現在のバイオームで滞在中の鳥も加える(現在進行形の記録)
    for bid in st.session_state.get("residents", set()):
        visited_by_bird.setdefault(bid, set()).add(st.session_state.biome)
    st.session_state.bird_visited_biomes = visited_by_bird

    # ===== 不在中ループ(状態進化) =====
    if fs:
        last_at = absence_loop.parse_iso(fs.get("last_access_at"))
        if last_at:
            _evolve_since_last_visit(tester_id, last_at, now)


def _evolve_since_last_visit(tester_id, last_at, now):
    """最後に離れてからの経過時間ぶん、生態系を時間進化させ session_state
    (residents/absence_events/mementos 等)に反映する共通ロジック。

    Sheets ログイン(`load_state_from_sheets`)・セーブコード復元
    (`_start_local_session`)の両方から呼ばれる。Sheets への書き戻しは
    ベストエフォート(失敗しても続行、`_sheets_safe`・try/except で保護)。
    """
    _mature_for_evo = list(st.session_state.get("planted", []))
    if not _mature_for_evo:
        return
    try:
        evo = absence_loop.evolve_state(
            _mature_for_evo,
            st.session_state.biome,
            st.session_state.month,
            last_at,
            now,
            st.session_state.residents,
            st.session_state.rng,
            item_placement=st.session_state.get("garden_item_placement"),
        )
    except Exception:
        evo = {"residents": st.session_state.residents,
               "events": [], "departures": [], "n_ticks": 0}

    # 進化した結果を session_state と Sheets に反映
    st.session_state.residents = evo["residents"]
    st.session_state.absence_events = evo["events"]
    # 直近イベントを「なぜ来たか」表示用にも展開(NEWバッジに使う)
    st.session_state.last_arrivals_info = {
        ev["bird_id"]: ev["reason_text"] for ev in evo["events"]
    }
    # 生態ログ(図鑑に蓄積表示する「なぜ来たか」の記録。重複除去・消さない)
    _accumulate_eco_log(evo["events"])

    # 不在中の撹乱・遷移を反映(植生の移ろい)
    _apply_disturbances(tester_id, evo)

    # 各イベントを記録(Sheets への書き戻しはベストエフォート)
    new_mementos = []
    _welcome_arrivals = []   # 「おかえり」ポップアップ用
    for ev in evo["events"]:
        try:
            _is_first = ev["bird_id"] not in st.session_state.discovered
            _sheets_safe(
                sc.add_visit, tester_id, ev["bird_id"], "absence",
                reason_text=ev["reason_text"],
                related_plant_id=ev["related_plant_id"],
                related_insect_id=ev["related_insect_id"],
                arrived_at=ev["arrived_at"],
            )
            _sheets_safe(sc.upsert_collection, tester_id, ev["bird_id"])
            st.session_state.discovered.add(ev["bird_id"])
            # 復帰フック: 留守中に初めて来た鳥は「ラジオに加わった新顔」。
            # ラジオが既に読む radio_new_arrivals に積み、🌟バナーを点ける
            # (会う→ラジオが豊かになる のループを、不在経由でも閉じる)。
            if _is_first:
                st.session_state.setdefault(
                    "radio_new_arrivals", set()).add(ev["bird_id"])
            if not any(a["id"] == ev["bird_id"] for a in _welcome_arrivals):
                _welcome_arrivals.append({
                    "id": ev["bird_id"],
                    "name": BIRDS.get(ev["bird_id"], {}).get(
                        "name", ev["bird_id"]),
                    "first": _is_first,
                })

            # 落とし物の記録
            mid = ev.get("memento_id")
            if mid:
                kind = mem.memento_category(mid)
                target = mem.memento_target(mid) if ":" in mid else mid
                _sheets_safe(
                    sc.add_memento, tester_id, mid, kind, target,
                    st.session_state.biome, ev["bird_id"],
                )
                if mid not in st.session_state.mementos_set:
                    st.session_state.mementos_set.add(mid)
                    new_mementos.append({
                        "memento_id": mid, "kind": kind,
                        "target_id": target,
                        "biome": st.session_state.biome,
                        "found_at": ev["arrived_at"].isoformat(timespec="seconds")
                                    if hasattr(ev["arrived_at"], "isoformat")
                                    else str(ev["arrived_at"]),
                        "via_bird_id": ev["bird_id"],
                    })
        except Exception:
            pass

    # 取得済みリストにマージ
    if new_mementos:
        st.session_state.mementos = (
            st.session_state.get("mementos", []) + new_mementos
        )
    # 直近イベントの新規落とし物のサマリ(ホーム画面表示用)
    st.session_state.recent_new_mementos = new_mementos

    # 「おかえり」ポップアップ: 留守中に何かあった時だけ用意する(毎回は出さない)
    _hours_away = (now - last_at).total_seconds() / 3600
    _departures = []
    for _bid in evo.get("departures", []):
        _nm = BIRDS.get(_bid, {}).get("name", _bid)
        if _nm not in _departures:
            _departures.append(_nm)
    if _welcome_arrivals or _departures or new_mementos:
        st.session_state.welcome_popup = {
            "hours_away": _hours_away,
            "arrivals": _welcome_arrivals,
            "departures": _departures,
            "n_mementos": len(new_mementos),
        }

    # 進化が起きていれば field_state を現在時刻で更新(ベストエフォート)
    if evo["n_ticks"] > 0:
        _sheets_safe(
            sc.save_field_state, tester_id, st.session_state.biome,
            current_temperature(st.session_state.biome, st.session_state.month),
            f"month_{st.session_state.month}",
            list(st.session_state.residents),
        )


def init_state():
    # 自動再開(ローカル保存MVP・案A上乗せ): ログイン画面を出すかどうかを
    # 判定する前に、まず「?local_restore=...」が来ていないか確認する。
    # 復元に成功していればここで current_tester_id が設定され、
    # 下の分岐でログイン画面を経由せずアプリ本編にそのまま入る。
    _handle_local_restore_query()
    if st.session_state.get("current_tester_id") is None:
        render_login_screen()
        return  # render_login_screen が st.stop() を呼ぶので到達しない
    if "initialized" not in st.session_state:
        # 通常は render_login_screen 内の _start_local_session() で初期化済みのはず。
        # 念のためのフォールバック(何らかの理由で initialized が立っていない場合)。
        _start_local_session()


def _sheets_safe(fn, *args, **kwargs):
    """書き戻しの共通ラッパ。失敗してもアプリは止めず、警告だけ出す"""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        st.warning(f"Sheets同期に失敗(処理は続行されます): {e}", icon="⚠️")


def _accumulate_eco_log(events):
    """不在中ループの到来イベントを、生態ログ(図鑑蓄積表示)に追記する。

    `eco_log.append_events` は重複除去のみ行う純粋関数(新しい"なぜ来たか"の
    恣意ロジックは追加しない)。撹乱で植物が失われてもここでは何も削除しない
    (HANDOFF §1-1-a「ラジオ=蓄積するコレクション、記録は減らない」と同じ思想)。
    """
    if not events:
        return
    st.session_state.eco_log = eco_log.append_events(
        st.session_state.get("eco_log", []), events
    )


def _mark_met_today(bird_id):
    """その鳥に「今日会った」ことを会った日数に反映する(1日1カウント)。

    永続の実体は bird_visits(訪問ログ)なので、ここでは session を即時に更新して
    その日の到来をすぐ図鑑へ映すだけ。次回ログイン時に訪問ログから再集計される。
    """
    today = datetime.now().date().isoformat()
    bd = st.session_state.setdefault("bird_days", {})
    rec = bd.setdefault(bird_id, {"days": 0, "last": ""})
    if rec.get("last") != today:
        rec["days"] = rec.get("days", 0) + 1
        rec["last"] = today


def _grant_memento_now(tester_id, memento_id, bird_id):
    """不在ループの外から、単発で落とし物を1つ即時付与する共通ヘルパー。

    既存の不在中ループの roll_drop 抽選(mementos.py)とは別枠の確定付与であり、
    確率抽選には一切触れない。Sheetsへの書き戻しはベストエフォート
    (_sheets_safe、失敗してもアプリは止めない)。
    2026-07-09時点: 広告リワード「案A(小枝確定付与)」の削除により現在は
    呼び出し元が無いが、将来の確定付与系の演出のために汎用ヘルパーとして残す。
    """
    kind = mem.memento_category(memento_id)
    target = mem.memento_target(memento_id) if ":" in memento_id else memento_id
    _sheets_safe(
        sc.add_memento, tester_id, memento_id, kind, target,
        st.session_state.biome, bird_id,
    )
    is_new = memento_id not in st.session_state.mementos_set
    if is_new:
        st.session_state.mementos_set.add(memento_id)
    record = {
        "memento_id": memento_id, "kind": kind, "target_id": target,
        "biome": st.session_state.biome,
        "found_at": datetime.now().isoformat(timespec="seconds"),
        "via_bird_id": bird_id,
    }
    st.session_state.mementos = st.session_state.get("mementos", []) + [record]
    if is_new:
        st.session_state.recent_new_mementos = (
            st.session_state.get("recent_new_mementos", []) + [record]
        )
    return record


def _apply_disturbances(tid, evo):
    """不在中の撹乱・遷移を session と plantings シートへ反映し、表示用に保存する。

    撹乱は植生(plantings)を移ろわせるだけ。生息地の質は別の値として持たず、
    植生から創発させる(木が倒れれば食物網が縮み、確率・種数が下がる
    = 種数–面積関係を engine.py の既存ロジックが自然に表現する)。
    """
    disturbances = evo.get("disturbances") or []
    st.session_state.disturbance_events = disturbances
    if not disturbances:
        return
    # 植生の永続化: 倒れた木を removed に(自動での植え直しはしない=純減)
    for d in disturbances:
        for pid in d.get("removed", []):
            _sheets_safe(sc.remove_planting, tid, pid)
    # session の植生を最終状態に揃える(撹乱の結果)
    if "planted_final" in evo:
        st.session_state.planted = list(evo["planted_final"])


init_state()


def _handle_ritual_observation():
    """儀式UIが top window のクエリパラメータ ?ritual_obs=id1,id2 を付けて
    リロードしてきたら、近距離観察を Sheets に保存してパラメータを消す。

    JS(iframe)→ top.location のクエリ → ここ、という JS→Python の片道経路。
    保存後はパラメータを消し(=再実行)、リロード時の二重保存を防ぐ。
    """
    raw = st.query_params.get("ritual_obs")
    if not raw:
        return
    tester_id = st.session_state.get("current_tester_id")
    biome_id = st.session_state.get("biome", "")
    bird_ids = [b for b in raw.split(",") if b and b in BIRDS]
    saved = []
    if tester_id:
        for bid in bird_ids:
            # 近距離観察の Sheets 保存はベストエフォート(失敗しても体験(session_state
            # 反映)は止めない)。saved には Sheets の成否に関わらず必ず積む。
            _sheets_safe(observation_log.record_observation, tester_id, bid, biome_id)
            saved.append(bid)
    if saved:
        # セッション状態にも即時反映(リロード待ちなしで図鑑へ反映)
        _observed = st.session_state.setdefault("observed", {})
        _discovered = st.session_state.setdefault("discovered", set())
        _flash = []
        for bid in saved:
            # 「初めて」= 図鑑への新規登録(discovered)かどうかで判定する
            # (_evolve_since_last_visit と同じ判定軸に揃える。以前は
            # observedのcountで判定していたため、絶対数観察は初めてでも
            # discovered済み=図鑑には既に載っている鳥にまで「はじめての観察!」
            # と出てしまう不一致があった)。
            _is_first = bid not in _discovered
            rec = _observed.setdefault(bid, {"count": 0, "first": "", "last": ""})
            rec["count"] += 1
            _discovered.add(bid)  # 近くで観察できた鳥は当然「来た鳥」でもある
            _mark_met_today(bid)  # 会った日数(1日1カウント)に反映
            if _is_first:
                # 会う→聴くループ: 初めて会った鳥をラジオで「新しく加わった」と祝う信号
                st.session_state.setdefault("radio_new_arrivals", set()).add(bid)
            _flash.append({
                "id": bid,
                "name": BIRDS[bid].get("name", bid),
                "first": _is_first,
            })
        st.session_state["ritual_flash"] = _flash
    # パラメータを消す(リロードで再保存しないように)。これ自体が再実行を誘発する。
    st.query_params.clear()


_handle_ritual_observation()


def _handle_ad_reward_result():
    """リワード広告JS(ads.py の components.html)が top window のクエリパラメータ
    ?ad_result=success|fail|unavailable&ad_nonce=... を付けてリロードしてきたら、
    保留中のリクエスト(ads_pending_garden_item)と nonce を
    照合し、一致かつ success のときだけ実際に報酬を確定する。

    _handle_ritual_observation() と同じ「JS→top.location のクエリ→ここ」という
    片道経路(ads.py 冒頭のdocstring参照)。ADMOB_ENABLED=False(既定)の間は
    session_state に pending が積まれることが無いため、この関数は事実上 no-op
    のまま(壊さない)。
    """
    result = st.query_params.get("ad_result")
    if not result:
        return
    nonce = st.query_params.get("ad_nonce")
    flash = None

    item_pending = st.session_state.get("ads_pending_garden_item")
    if item_pending and nonce and item_pending.get("nonce") == nonce:
        st.session_state.pop("ads_pending_garden_item", None)
        if result == "success":
            item_id = item_pending.get("item_id")
            if item_id in garden_items.ITEMS:
                st.session_state.garden_item_placement = garden_items.place_item(item_id)
                ads.mark_claimed_today(st.session_state, "garden_item_claimed_date")
                flash = ("item_success", garden_items.ITEMS[item_id].get("name", item_id))
        elif result == "unavailable":
            flash = ("ad_unavailable", None)
        else:
            flash = ("ad_fail", None)

    if flash:
        st.session_state["ad_reward_flash"] = flash
    # パラメータを消す(リロードで再処理しないように)。これ自体が再実行を誘発する。
    st.query_params.clear()


_handle_ad_reward_result()


def _inject_ad_result_check():
    """広告視聴結果(ads.py の `_ADMOB_REWARD_JS_TEMPLATE` が書き込む
    `window.top.localStorage["toris_ad_pending_result"]`)を検出し、
    見つかったら `?ad_result=...&ad_nonce=...` を付けてトップウィンドウを
    リロードする(`_handle_ad_reward_result()` が処理する既存の片道経路に合流)。

    2026-07-10追記(P1修正・CEO承認): 広告SDKの `Dismissed` 等のコールバックの
    「その場」でトップウィンドウへ直接ナビゲーションを試みていた旧実装は、
    実機PlaywrightでCDPのページライフサイクル(`Page.setWebLifecycleState`
    の frozen→active、ネイティブ広告Activity表示中に実際に起きる
    WebViewのバックグラウンド化を再現)により、視聴完了直後のタイミングでは
    ナビゲーションが成功したり失敗したりする不安定な挙動になることを確認した
    (`ads.py` モジュールdocstring「2026-07-10 追記(P1修正)」参照)。

    この関数はそれとは完全に独立して、アプリの**毎回のrerun**で描画され
    (=ADMOB_ENABLED=Trueの間、常にページ上に存在する)、1秒おきに
    localStorageをポーリングする。広告視聴の完了イベント(バックグラウンド
    復帰直後の不安定なタイミング)と、実際にナビゲーションを試みるタイミング
    (このポーリングの独立したタイミング、何度でもリトライ可能)を分離する
    ことで、バックグラウンド化をまたいでも報酬が確実に反映されるようにする。

    二重処理防止: 見つけたら**読み取った瞬間に localStorage から削除**してから
    ナビゲーションする(Python側の `_handle_ad_reward_result()` も
    nonce照合後に対象のpendingを pop するため、二重に安全)。
    ADMOB_ENABLED=False(既定)のときは何もしない(壊さない)。
    """
    if not ads.ADMOB_ENABLED:
        return
    components.html(
        """
        <script>
        (function () {
          var KEY = 'toris_ad_pending_result';
          function tryDeliver() {
            try {
              var top = window.top;
              var raw = top.localStorage.getItem(KEY);
              if (!raw) return;
              // 読み取った時点で削除(以後のポーリングでの二重処理を防ぐ)
              top.localStorage.removeItem(KEY);
              var data = JSON.parse(raw);
              var url = new URL(top.location.href);
              url.searchParams.set('ad_result', data.status || 'fail');
              url.searchParams.set('ad_nonce', data.nonce || '');
              if (data.reason) { url.searchParams.set('ad_reason', data.reason); }
              // components.html() の iframe は sandbox に allow-top-navigation 系
              // フラグを含まないため、ここから直接 top.location.href を書き換える
              // 遷移はブラウザに拒否される(SecurityError)。_inject_local_restore_check()
              // と同じ回避策: top.document に <script> 要素を生成して差し込み、
              // サンドボックスされていないトップウィンドウ自身の実行コンテキストで
              // location 書き換えを行わせる。
              var doc = top.document;
              var script = doc.createElement('script');
              script.textContent = 'window.location.href = ' + JSON.stringify(url.toString()) + ';';
              doc.head.appendChild(script);
            } catch (e) {
              // localStorage無効・想定外のJSON等で失敗しても、通常のUIに
              // フォールバックする(次のポーリングでまた試すだけ)。
            }
          }
          // 既に書き込まれている場合に備え即座に1回確認しつつ、以後は
          // 広告視聴中(バックグラウンド化からの復帰)を待って定期的に再確認する。
          tryDeliver();
          var intervalId = setInterval(tryDeliver, 1000);
          window.addEventListener('beforeunload', function () {
            clearInterval(intervalId);
          });
        })();
        </script>
        """,
        height=0,
    )


_inject_ad_result_check()

# 自動保存(ローカル保存MVP・案A上乗せ): セッションが始まっていれば
# (=current_tester_id 設定済み。ログイン画面表示中は何もしない)、
# 今回のrerunで確定した最新の状態をブラウザの localStorage に書き込む。
# 「植える・時間経過・観察などの操作のたび」を、個別のフックを増やさず
# 満たすため、毎回のscript rerunの終盤でまとめて1回だけ呼ぶ。
_inject_local_save_write()


# ============= Header =============
st.markdown("# 🐦 #Toris Collection#")
st.markdown(
    "<p style='color:#5a7a5a; font-size:1.05em;'>"
    "土地を選び、植物を植え、時間が経つのを待つ。やってきた鳥たちの声に耳を澄まそう。</p>",
    unsafe_allow_html=True
)


# ============= チュートリアル(新規スタート専用・スキップ可)=============
# 交渉不能の原則(受動的・罰しない)を守るため、ポップアップでブロックせず、
# ページ最上部に「案内」として静かに置くだけ。いつでも「スキップ」で消せて、
# 一度スキップ/完了すると tutorial_done が立ち、二度と出さない(このブラウザ
# セッションの間。セーブコードには含めない=既存ユーザーの復元時は常に非表示)。
# 文言・ステップ進行の純粋ロジックは tutorial.py に切り出し、ここでは
# session_state の読み書きと描画だけを行う。


def _tutorial_finish():
    st.session_state.tutorial_done = True


def _tutorial_next():
    step = tutorial.advance_step(st.session_state.get("tutorial_step", 0))
    st.session_state.tutorial_step = step
    if tutorial.is_done(step):
        _tutorial_finish()


def render_tutorial_banner():
    """新規スタート直後だけ表示する、3ステップの案内バナー。

    ステップ2(植物を植える)は、実際に1つ植えた時点で自動的に次へ進む
    (「案内されながら進める」体験。手動の「次へ」でも進められる)。
    どのステップからでも「チュートリアルをスキップ」でいつでも終了できる。
    """
    if st.session_state.get("tutorial_done", True):
        return

    step = tutorial.resolve_step(
        st.session_state.get("tutorial_step", 0), st.session_state.get("planted")
    )
    st.session_state.tutorial_step = step

    biome_name = BIOMES.get(st.session_state.biome, {}).get("name", st.session_state.biome)
    content = tutorial.step_content(step, biome_name)

    st.markdown(
        f"<div style='background:#eef6ee; padding:14px 18px; border-radius:10px; "
        f"border-left:4px solid #7ba87b; margin-bottom:14px;'>"
        f"<div style='color:#3f5f3f; font-weight:600; margin-bottom:4px;'>{content['title']}</div>"
        f"<div style='color:#4a6a4a; font-size:0.92em; line-height:1.6;'>{content['body']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    col_next, col_skip = st.columns([1, 1])
    with col_next:
        if st.button(content["next_label"], key="tutorial_next_btn", use_container_width=True):
            _tutorial_next()
            st.rerun()
    with col_skip:
        if st.button("チュートリアルをスキップ", key="tutorial_skip_btn", use_container_width=True):
            _tutorial_finish()
            st.rerun()


render_tutorial_banner()


# ============= Sidebar =============
with st.sidebar:
    # この端末だけのローカル識別子(サーバーには送らない。ログイン概念はない)
    tid = st.session_state.get("current_tester_id", "(未初期化)")
    st.markdown(f"<div style='font-size:0.85em; color:#888;'>💾 {tid}</div>",
                unsafe_allow_html=True)

    st.markdown("### 🌍 あなたの土地")
    biome = BIOMES[st.session_state.biome]
    st.markdown(f"**{biome['name']}**")
    temp_now = current_temperature(st.session_state.biome, st.session_state.month)
    st.markdown(
        f"<div class='stat-box'>"
        f"📅 {st.session_state.month}月<br>"
        f"🌡️ 気温 <b>{temp_now:.1f}℃</b><br>"
        f"💧 降水量 <b>{biome['precip_mean']}mm/年</b>"
        f"</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown("### 📊 コレクション状況")
    st.metric("図鑑登録種数", f"{len(st.session_state.discovered)} / {len(BIRDS)}")
    st.metric("現在滞在中", f"{len(st.session_state.residents)} 羽")
    st.metric("植えた植物", f"{len(st.session_state.planted)} 種")
    _total_mementos = len(mem.all_possible_mementos(BIRDS, PLANTS))
    _owned_mementos = len(st.session_state.get("mementos_set", set()))
    st.metric("落とし物", f"{_owned_mementos} / {_total_mementos}")

    st.markdown("---")
    with st.expander("💾 セーブコード(バックアップ)", expanded=False):
        st.caption(
            "進行データはこの端末に自動保存されています(次回もこのまま続きから"
            "始まります)。別の端末へ引き継ぐ・念のため保管しておきたい時だけ、"
            "下のボタンでコピーしてください。"
        )
        _save_code_str = save_code.encode_current_state(st.session_state)
        # ワンタップコピー(唯一の主要な操作。2026-07-10追記/2026-07-11整理)。
        # ボタン1つでクリップボードにコピーできる、最も信頼できる導線。
        # 他の手段(書き出し・直接表示・共有)は下の「うまくいかない場合」に格納し、
        # 通常は見えないようにする(CEO実機フィードバック:手段が並んでいて
        # 「コピーと書き込むの違いが分からない」への対応。壊さない=各手段自体は削除せず、
        # 表示位置・粒度だけ変更する)。
        _render_save_code_copy_button(_save_code_str)
        # st.expander はネスト不可(Streamlitの制約)のため、チェックボックスで
        # 折りたたみ相当の見せ方にする(通常は非表示、必要な人だけ開く)。
        if st.checkbox("うまくいかない場合はこちら", value=False, key="save_code_fallback_toggle"):
            st.download_button(
                "⬇️ セーブコードを書き出す",
                data=_save_code_str,
                file_name="toris_collection_save.txt",
                mime="text/plain",
                use_container_width=True,
                help="アプリ版(サイドロード)では反応しないことがあります。"
                     "その場合は上の「📋 セーブコードをコピー」ボタン、"
                     "右下に出る「💾 セーブコードを共有」ボタン、"
                     "または下のコピー欄をお使いください。",
            )
            # st.text_area(key=固定)だと初回描画時の値のまま更新が止まる
            # (Streamlitのウィジェット値キャッシュ)ため、st.code で読み取り専用表示にする。
            # コピー用ボタンが標準で付き、常に最新の _save_code_str を表示できる。
            # (Web版・アプリ版どちらでも確実に動く、上のdownload_buttonの主要な
            # フォールバック。2026-07-09 CEO実機報告により重要度が上がったため明記)
            st.caption("⬆️のボタンで反応がない場合は、ここから選択してコピーできます")
            st.code(_save_code_str, language=None, wrap_lines=True)
            # アプリ版(Capacitor)限定: ネイティブの共有シート経由で確実に渡せる
            # ボタンを追加で出す(download_buttonがWebView内で動かないことがある対策)。
            _inject_native_save_code_share_button(_save_code_str)

    st.markdown("---")
    # データソース状況
    try:
        from engine import _try_load_centralities
        cents = _try_load_centralities()
        if cents:
            st.caption(f"🔬 生態的な重要度スコア: {len(cents)}種で有効")
        else:
            st.caption("🔬 生態的な重要度スコア: シードrarityのみ使用")
    except Exception:
        pass

    if st.button("🌬️ ここを離れる", use_container_width=True,
                 help="滞在中の鳥をクリア。植えた植物と図鑑は保持。"):
        st.session_state.residents = set()
        st.session_state.log = []
        st.session_state.absence_events = []
        st.session_state.last_arrivals_info = {}
        tid = st.session_state.get("current_tester_id")
        if tid:
            _sheets_safe(
                sc.save_field_state, tid, st.session_state.biome,
                current_temperature(st.session_state.biome, st.session_state.month),
                f"month_{st.session_state.month}", []
            )
            _sheets_safe(sc.log_access, tid, "home", "leave_field")
        st.rerun()

    if st.button("🔄 セッションをリセット", use_container_width=True,
                 help="この端末の今のセッションを終了し、開始画面に戻ります"
                      "(ログイン概念はないため「ログアウト」ではありません)。"
                      "セーブコードを書き出していないデータは失われます。"):
        tid = st.session_state.get("current_tester_id")
        if tid:
            _sheets_safe(sc.log_access, tid, "login", "leave")
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    # ===== 開発・テスト用 =====
    # 本番リリース時にはこのブロックごと削除する想定
    st.markdown("---")
    with st.expander("🧪 開発テスト用", expanded=False):
        st.caption(
            "現実時間の経過を待たずに、生態系の進化を即座にシミュレーションします。"
            "クローズドテスト中の動作確認用。"
        )
        sim_hours = st.select_slider(
            "シミュレートする経過時間",
            options=[1, 6, 12, 24, 48],
            value=12,
            format_func=lambda h: f"{h}時間",
        )
        if st.button(f"⏩ {sim_hours}時間後をシミュレート", use_container_width=True):
            tid = st.session_state.current_tester_id
            if not st.session_state.planted:
                st.warning("先に植物を植えてください。")
            else:
                fake_last = datetime.now() - timedelta(hours=sim_hours)
                # テスト用: 24時間遅延を無視して全植物を成熟扱いで進化
                evo = absence_loop.evolve_state(
                    st.session_state.planted,
                    st.session_state.biome,
                    st.session_state.month,
                    fake_last,
                    datetime.now(),
                    st.session_state.residents,
                    st.session_state.rng,
                    item_placement=st.session_state.get("garden_item_placement"),
                )
                # 結果を反映(本番の不在中ループと同じ処理)
                st.session_state.residents = evo["residents"]
                st.session_state.absence_events = evo["events"]
                st.session_state.last_arrivals_info = {
                    ev["bird_id"]: ev["reason_text"] for ev in evo["events"]
                }
                _accumulate_eco_log(evo["events"])
                _apply_disturbances(tid, evo)
                new_mementos = []
                for ev in evo["events"]:
                    _sheets_safe(
                        sc.add_visit, tid, ev["bird_id"], "absence",
                        reason_text=ev["reason_text"],
                        related_plant_id=ev["related_plant_id"],
                        related_insect_id=ev["related_insect_id"],
                        arrived_at=ev["arrived_at"],
                    )
                    _sheets_safe(sc.upsert_collection, tid, ev["bird_id"])
                    st.session_state.discovered.add(ev["bird_id"])
                    _mark_met_today(ev["bird_id"])  # 会った日数(1日1カウント)に反映
                    # 落とし物の記録
                    mid = ev.get("memento_id")
                    if mid:
                        kind = mem.memento_category(mid)
                        target = mem.memento_target(mid) if ":" in mid else mid
                        _sheets_safe(
                            sc.add_memento, tid, mid, kind, target,
                            st.session_state.biome, ev["bird_id"],
                        )
                        if mid not in st.session_state.mementos_set:
                            st.session_state.mementos_set.add(mid)
                            new_mementos.append({
                                "memento_id": mid, "kind": kind,
                                "target_id": target,
                                "biome": st.session_state.biome,
                                "found_at": ev["arrived_at"].isoformat(timespec="seconds")
                                            if hasattr(ev["arrived_at"], "isoformat")
                                            else str(ev["arrived_at"]),
                                "via_bird_id": ev["bird_id"],
                            })
                if new_mementos:
                    st.session_state.mementos = (
                        st.session_state.get("mementos", []) + new_mementos
                    )
                st.session_state.recent_new_mementos = new_mementos
                _sheets_safe(
                    sc.save_field_state, tid, st.session_state.biome,
                    current_temperature(st.session_state.biome, st.session_state.month),
                    f"month_{st.session_state.month}",
                    list(st.session_state.residents),
                )
                _sheets_safe(
                    sc.log_access, tid, "test", "sim_evolved",
                    f"{sim_hours}h,events={len(evo['events'])},"
                    f"new_mementos={len(new_mementos)}")
                st.rerun()

        # ===== 鳴き声ライセンス監査(広告=商用モードの前提チェック) =====
        st.markdown("---")
        st.caption(
            "広告つき(商用)にすると、CC BY-NC の録音は使えません。"
            "商用可(CC0 / CC BY / BY-SA / BY-ND)の録音がある種を集計します。"
        )
        if st.button("🎙 鳴き声ライセンスを監査", use_container_width=True):
            if xc_client is None or not xc_client.is_enabled():
                st.warning("xeno-canto APIキーが未設定です。")
            else:
                import license_audit
                with st.spinner("全種の録音ライセンスを照会中(初回は数分)…"):
                    rows = license_audit.audit(BIRDS)
                    summary = license_audit.summarize(rows)
                st.session_state["_license_audit"] = {"rows": rows, "summary": summary}
        _la = st.session_state.get("_license_audit")
        if _la:
            s = _la["summary"]
            st.metric(
                "商用モードで鳴かせられる種",
                f"{s['commercial_ok']} / {s['total_species']} 種",
                help=f"商用可カバー率 {s['coverage_pct']}%",
            )
            if s["nc_only_names"]:
                st.caption("🔒 NC(非商用)録音のみ → 商用では鳴かせられない: "
                           + "、".join(s["nc_only_names"]))
            if s["no_audio_names"]:
                st.caption("🔇 そもそも録音が見つからない: "
                           + "、".join(s["no_audio_names"]))
            with st.expander("種ごとの内訳", expanded=False):
                st.dataframe(
                    [{
                        "鳥": r["name"],
                        "学名": r["scientific"],
                        "商用可": "✓" if r["commercial_ok"] else "",
                        "商用": r["counts"]["commercial"],
                        "NC": r["counts"]["noncommercial"],
                        "不明": r["counts"]["unknown"],
                        "録音数": r["total"],
                    } for r in _la["rows"]],
                    use_container_width=True, hide_index=True,
                )

        # ===== GloBI 相互作用プレビュー(種・餌台・リス・Hawk 連鎖の材料集め) =====
        st.markdown("---")
        st.caption(
            "GloBI から候補種(鳥/リス/Hawk)の eats・eatenBy・preysOn を引きます。"
            "餌台→リス→Hawk→小鳥の連鎖を GloBI エッジで組む材料。デプロイ環境で実行。"
        )
        _globi_biome = st.selectbox(
            "候補バイオーム", options=["charlotte", "kyoto"],
            format_func=lambda b: {"charlotte": "🌳 シャーロット", "kyoto": "🏯 京都"}[b],
            key="globi_expand_biome",
        )
        if st.button("🐿️ GloBI 相互作用プレビュー", use_container_width=True):
            import species_expand
            roster = species_expand.roster_for(_globi_biome)
            with st.spinner("GloBI に問い合わせ中(初回は数分)…"):
                st.session_state["_globi_preview"] = species_expand.preview_roster(roster)
        _gp = st.session_state.get("_globi_preview")
        if _gp:
            _any = any(r["interactions"] for r in _gp)
            if not _any:
                st.warning(
                    "GloBI から相互作用が取れませんでした。"
                    "この環境から GloBI に到達できない可能性があります"
                    "(デプロイ環境=Streamlit Cloud で実行してください)。"
                )
            for r in _gp:
                with st.expander(f"{r['name']}({r['role']}) — {r['scientific']}",
                                 expanded=False):
                    if not r["interactions"]:
                        st.caption("(相互作用データなし)")
                    for itype, targets in r["interactions"].items():
                        st.markdown(f"**{itype}** ({len(targets)})")
                        st.caption("、".join(targets[:30]))

        st.markdown("---")
        st.caption("⚠️ **データリセット**(取り消せません)")
        # 二段階確認: チェックボックス → ボタン押下
        confirm_reset = st.checkbox(
            "本当にすべてのデータを削除する",
            key="reset_confirm",
            help="このテスターIDの植物・図鑑・落とし物・訪問記録すべてが削除されます",
        )
        if st.button("🗑️ このテスターのデータを全削除",
                     disabled=not confirm_reset,
                     use_container_width=True):
            tid = st.session_state.current_tester_id
            try:
                with st.spinner("削除中..."):
                    result = sc.reset_tester_data(tid)
                # session_state もクリア
                for key in ["planted", "planted_at_map", "residents",
                            "discovered", "mementos", "mementos_set",
                            "absence_events", "bird_visited_biomes",
                            "last_arrivals_info", "recent_new_mementos"]:
                    if key in st.session_state:
                        if isinstance(st.session_state[key], list):
                            st.session_state[key] = []
                        elif isinstance(st.session_state[key], set):
                            st.session_state[key] = set()
                        elif isinstance(st.session_state[key], dict):
                            st.session_state[key] = {}
                        else:
                            st.session_state[key] = None
                # 削除した行数を表示
                detail = ", ".join(
                    f"{k}: {v}" for k, v in result.items()
                    if isinstance(v, int) and v > 0
                )
                st.success(f"削除完了: {detail or 'なし'}")
                sc.log_access(tid, "test", "data_reset", detail)
                st.rerun()
            except Exception as e:
                st.error(f"削除失敗: {e}")


# ============= ポップアップ(出会い・おかえり) =============
# st.dialog は Streamlit 1.37+。古い環境では tab_home のバナー表示にフォールバック。
if hasattr(st, "dialog"):

    @st.dialog("🪶 鳥に出会えました")
    def _obs_dialog(flash):
        for f in flash:
            cols = st.columns([1, 3])
            with cols[0]:
                st.markdown(
                    render_bird_sprite_html(f["id"], size_px=72),
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(f"**{f['name']}**")
                if f.get("first"):
                    st.markdown("✨ *はじめまして! 新しく図鑑に登録されました*")
                else:
                    st.caption("また会えました。図鑑の観察記録が増えます。")
        if st.button("とじる", key="obs_dialog_close", use_container_width=True):
            st.rerun()

    @st.dialog("🌿 おかえりなさい")
    def _welcome_dialog(data):
        h = data.get("hours_away", 0)
        if h >= 48:
            st.caption(f"{int(h // 24)}日ぶりです。留守のあいだに——")
        elif h >= 2:
            st.caption("しばらくぶりです。留守のあいだに——")
        arrivals = data.get("arrivals", [])
        for a in arrivals[:6]:
            cols = st.columns([1, 4])
            with cols[0]:
                st.markdown(
                    render_bird_sprite_html(a["id"], size_px=56),
                    unsafe_allow_html=True,
                )
            with cols[1]:
                if a.get("first"):
                    st.markdown(f"✨ はじめまして、**{a['name']}**! 新しく図鑑に登録されました")
                else:
                    st.markdown(f"**{a['name']}** が来ていました")
        deps = data.get("departures", [])
        if deps:
            st.caption("🕊 " + "、".join(deps[:5]) + " は旅立っていきました")
        if data.get("n_mementos"):
            st.caption(f"🎁 新しい落とし物が {data['n_mementos']} 個あります")
        # 復帰フックは軸(ラジオ)へ向ける: 留守中に来た鳥はラジオに加わっている。
        if arrivals:
            st.success("🎙 新しい声がラジオの顔ぶれに加わりました。聴きに行けます。")
        if st.button("庭を見る", key="welcome_dialog_close",
                     type="primary", use_container_width=True):
            st.rerun()

    # 1回の実行で開けるダイアログは1つ。出会い(儀式直後)を優先する。
    if st.session_state.get("ritual_flash"):
        _obs_dialog(st.session_state.pop("ritual_flash"))
    elif st.session_state.get("welcome_popup"):
        _welcome_dialog(st.session_state.pop("welcome_popup"))
else:
    # 旧Streamlit: 不在中の出来事バナー(tab_home)が同じ内容を伝えるので破棄
    st.session_state.pop("welcome_popup", None)


# ============= Tabs =============
# 製品の背骨(HANDOFF §1-1): ラジオがコア = 最前面の帰る場所。
# 庭(今の様子)は鳥に「会う」ための場所として2番目に置く。
#
# 「🗺 みんなの庭」(community.py)は MVP 公開版では非表示(企画部提案
# 2026-07-04・CEO承認)。個人データをローカル保存(セーブコード)方式へ
# 移行したため、複数ユーザー間の集合集計に必要なサーバー側データが得られない。
# community.py 自体は削除せず残置(将来、匿名集計の仕組みを別途用意した時点で
# 復活を検討する)。
tab_radio, tab_home, tab_plant, tab_sim, tab_birds, tab_mementos, tab_network, tab_help = st.tabs(
    ["🎙 ラジオ", "🏞️ 庭の様子", "🌱 植える", "🧪 シミュ", "📖 図鑑", "🎁 落とし物",
     "🕸️ ネットワーク", "❓ 使い方"]
)


# ---------- Tab: Home ----------
with tab_home:
    # 儀式終了時に保存された近距離観察の知らせ(ダイアログ非対応環境のフォールバック)
    _flash = st.session_state.pop("ritual_flash", None)
    if _flash:
        _names = "、".join(f["name"] for f in _flash)
        st.success(
            "🪶 今朝、" + _names + " に会えました。🎙 ラジオの顔ぶれに加わりました。"
        )

    # 広告リワード(実SDK視聴後)の結果通知(app._handle_ad_reward_result 参照)
    _ad_flash = st.session_state.pop("ad_reward_flash", None)
    if _ad_flash:
        _ad_kind, _ad_label = _ad_flash
        if _ad_kind == "item_success":
            st.success(
                f"🎁 広告を見てくれてありがとう。今日は「{_ad_label}」を庭に置きました(6時間)。"
            )
        elif _ad_kind == "ad_unavailable":
            st.info("この広告リワードは、アプリ版(Android)でのみご利用いただけます。")
        elif _ad_kind == "ad_fail":
            st.info(
                "広告を最後まで見られなかったため、今回は受け取れませんでした。またいつでもどうぞ。"
            )

    # ===== 儀式UI(距離メカニクス)=====
    # 滞在中の鳥がいる時だけ、ホームタブの最上部に儀式エリアを表示する
    if st.session_state.get("residents"):
        render_ritual(
            resident_ids=list(st.session_state.residents),
            biome_id=st.session_state.biome,
            birds_data=BIRDS,
        )
        st.markdown("---")

    # 庭の移ろい(不在中の撹乱→再生)。罰ではなく自然の循環として静かに伝える。
    _dist_events = st.session_state.get("disturbance_events") or []
    if _dist_events:
        _dist_rows = "".join(
            f"<div style='padding:5px 0;color:#6a5a44;font-size:0.92em;"
            f"border-bottom:1px solid #ece3d2;'>{d.get('story','')}</div>"
            for d in _dist_events
        )
        st.markdown(
            f"<div style='background:#f4efe4;padding:14px 18px;border-radius:10px;"
            f"border-left:4px solid #b8a06a;margin-bottom:18px;'>"
            f"<div style='color:#8a7048;font-size:0.95em;font-weight:500;"
            f"margin-bottom:4px;'>🌿 庭の移ろい</div>{_dist_rows}</div>",
            unsafe_allow_html=True,
        )

    # 不在中の出来事(ログイン直後に生成されたイベントがあれば表示)
    _abs_events = st.session_state.get("absence_events") or []
    _new_mems = st.session_state.get("recent_new_mementos") or []
    if _abs_events:
        _now = datetime.now()
        _summary = absence_loop.summarize_events(_abs_events)
        st.markdown(
            f"<div style='background:#f5f0e6; padding:14px 18px; border-radius:10px; "
            f"border-left:4px solid #b8a878; margin-bottom:18px;'>"
            f"<div style='color:#7a6a4a; font-size:0.95em; font-weight:500;'>"
            f"🌙 不在中の出来事: {_summary}</div></div>",
            unsafe_allow_html=True
        )

        # 新しい落とし物のサマリバナー
        if _new_mems:
            new_icons = []
            for mr in _new_mems[:8]:  # 最大8個まで
                ic, _, _, _ = mem.memento_display(
                    mr["memento_id"], BIRDS, PLANTS, BIOMES
                )
                new_icons.append(ic)
            extra = f" +{len(_new_mems)-8}" if len(_new_mems) > 8 else ""
            st.markdown(
                f"<div style='background:#fbf6e8; padding:12px 18px; "
                f"border-radius:10px; border-left:4px solid #c8a830; "
                f"margin-bottom:18px;'>"
                f"<div style='color:#a08020; font-size:0.95em; font-weight:500;'>"
                f"✨ 新しい落とし物が {len(_new_mems)} 個 "
                f"<span style='font-size:1.4em;'>{''.join(new_icons)}</span>{extra}"
                f"</div></div>",
                unsafe_allow_html=True
            )

        with st.expander("出来事を見る", expanded=False):
            for _ev in _abs_events:
                _bird = BIRDS.get(_ev["bird_id"], {})
                _bird_name = _bird.get("name", _ev["bird_id"])
                _rel = absence_loop.humanize_delta(_ev["arrived_at"], _now)
                _color = _bird.get("color", "#6a8ac8")
                _dot = (
                    f'<span style="display:inline-block; width:10px; height:10px; '
                    f'border-radius:50%; background:{_color}; margin-right:8px; '
                    f'vertical-align:middle;"></span>'
                )
                # この訪問で落とし物があったかチェック
                _drop_html = ""
                _mid = _ev.get("memento_id")
                if _mid:
                    _ic, _name, _, _mc = mem.memento_display(
                        _mid, BIRDS, PLANTS, BIOMES
                    )
                    _drop_html = (
                        f"<span style='margin-left:10px; padding:2px 8px; "
                        f"background:{_mc}22; border-radius:10px; "
                        f"font-size:0.85em; color:{_mc};'>"
                        f"{_ic} {_name}</span>"
                    )
                st.markdown(
                    f"<div style='padding:8px 0; color:#555; font-size:0.92em; "
                    f"border-bottom:1px solid #f0e9d8;'>"
                    f"{_dot}<span style='color:#999; margin-right:8px;'>{_rel}</span>"
                    f"{_ev['reason_text']}{_drop_html}</div>",
                    unsafe_allow_html=True
                )

    # 「今日の庭アイテム」バッジ(広告リワード・完全ランダム付与)。GloBI由来の「なぜ来たか」
    # 生態ログとは完全に別枠で表示する(混ぜない)。未配置・期限切れなら何も出さない。
    _garden_item = st.session_state.get("garden_item_placement")
    if garden_items.is_active(_garden_item):
        _gi_meta = garden_items.ITEMS.get(_garden_item.get("item_id"), {})
        _gi_hours = garden_items.hours_remaining(_garden_item)
        st.markdown(
            f"<div style='background:#eef6ee; padding:10px 16px; border-radius:10px; "
            f"border-left:4px solid #7ba87b; margin-bottom:14px;'>"
            f"<span style='color:#4a6a4a; font-size:0.92em;'>"
            f"{_gi_meta.get('emoji', '🎁')} 今日は「{_gi_meta.get('name', '')}」を"
            f"置いています(あと{_gi_hours:.1f}時間)。"
            f"<span style='color:#8a9a8a; font-size:0.85em;'>"
            f"({_gi_meta.get('hint', '')})</span></span></div>",
            unsafe_allow_html=True,
        )

    # フィールドの様子(全幅で表示)
    st.markdown("### 🌳 フィールドの様子")
    render_field_view(
        st.session_state.planted,
        st.session_state.residents,
        st.session_state.month,
        current_temperature(st.session_state.biome, st.session_state.month),
    )
    st.markdown("---")

    # 庭は「鳥に会う」場所。聴く体験はラジオタブ(コア)に一本化した。
    # かつてここにあった折りたたみラジオは二重コアの名残のため撤去(HANDOFF §1-1)。
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 🏞️ 土地を選ぶ")
        # 候補を選ぶ → 「ここに移る」ボタンで確定する2段階
        new_biome = st.radio(
            "バイオーム",
            options=list(BIOMES.keys()),
            format_func=lambda b: BIOMES[b]["name"],
            index=list(BIOMES.keys()).index(st.session_state.biome),
            label_visibility="collapsed",
            key="biome_candidate",
        )
        # 候補の説明を表示
        st.caption(BIOMES[new_biome]["description"])

        # 候補が現在地と異なる場合のみ確認ボタンを表示
        if new_biome != st.session_state.biome:
            st.warning(
                f"⚠️ {BIOMES[new_biome]['name']} に移ると、現在の植物と滞在中の鳥はリセットされます。",
                icon="🌬️",
            )
            if st.button(
                f"✓ {BIOMES[new_biome]['name']} に移る",
                type="primary", use_container_width=True,
            ):
                st.session_state.biome = new_biome
                st.session_state.residents = set()
                st.session_state.planted = []
                st.session_state.absence_events = []
                st.session_state.disturbance_events = []
                st.session_state.last_arrivals_info = {}
                # 庭アイテムは物理的な道具なので、土地を移ると一緒には持っていけない。
                # (1日1回の権利=日付ゲートは消費済みのまま。翌日また選べる)
                st.session_state.garden_item_placement = None
                tid = st.session_state.current_tester_id
                _sheets_safe(sc.remove_all_plantings, tid)
                _sheets_safe(
                    sc.save_field_state, tid, new_biome,
                    current_temperature(new_biome, st.session_state.month),
                    f"month_{st.session_state.month}", []
                )
                _sheets_safe(sc.log_access, tid, "home", "biome_changed", new_biome)
                st.rerun()

        st.markdown(
            "<div style='margin-top:18px; padding:14px 16px; background:#f0f4ec; "
            "border-radius:8px; color:#5a6a5a; font-size:0.9em; line-height:1.6;'>"
            "🌿 アプリを閉じている間にも、フィールドの生態系は動き続けます。"
            "次にここを訪れたとき、新しい鳥が来ているかもしれません。"
            "</div>",
            unsafe_allow_html=True
        )

    with col2:
        st.markdown("### 🐦 今、ここにいる鳥たち")
        if not st.session_state.residents:
            st.info("まだ鳥は来ていません。植物を植えて、しばらくしてからまた覗いてみましょう。")
        else:
            # 直近の到着鳥(NEWバッジ用): 今回のログインで生成された不在中イベント由来
            recent = set(st.session_state.get("last_arrivals_info", {}).keys())

            for b_id in sorted(st.session_state.residents, key=lambda b: BIRDS[b]["rarity"]):
                bird = BIRDS[b_id]
                is_new = b_id in recent
                new_label = " 🌟 <b>NEW</b>" if is_new else ""
                cls = "bird-card-new" if is_new else "bird-card"
                color = bird.get("color", "#6a8ac8")
                color_dot = (
                    f'<span style="display:inline-block; width:14px; height:14px; '
                    f'border-radius:50%; background:{color}; margin-right:6px; '
                    f'vertical-align:middle; border:2px solid white; '
                    f'box-shadow:0 0 0 1px #ccc;"></span>'
                )
                # 「なぜ来たか」の一文(NEW鳥のみ)
                reason_html = ""
                if is_new:
                    _reason = st.session_state.get("last_arrivals_info", {}).get(b_id, "")
                    if _reason:
                        reason_html = (
                            f"<br><span style='color:#7a8a5a; font-size:0.88em; "
                            f"font-style:italic;'>♪ {_reason}</span>"
                        )
                st.markdown(
                    f"<div class='{cls}'>"
                    f"{color_dot}<b>{bird['name']}</b>{new_label} "
                    f"<span style='color:#888; font-size:0.85em;'><i>{bird['scientific']}</i></span><br>"
                    f"<span style='color:#555; font-size:0.9em;'>{bird['description']}</span>"
                    f"{reason_html}"
                    f"</div>", unsafe_allow_html=True
                )
                render_bird_audio(b_id, bird, key_prefix="home_")

    # 広告スペース(ホーム下部・静かなバナー1枚のプレースホルダー)。
    # ラジオ再生中(radio_readyがTrue)は非表示にする。実SDKは未接続(ads.py参照)。
    ads.render_banner_placeholder(st.session_state)
    # Android版(Capacitorネイティブ)のみ、AdMob実バナーを配線(既定 ADMOB_ENABLED=False
    # のため現状は無効・Web版には影響なし。ads.py の解説コメント参照)。
    ads.render_admob_banner(st.session_state)

    # 広告リワード(庭アイテム・6種からランダムに1つ): 6時間だけ効く任意の
    # おまけを1つ置ける(1日1回)。CEO確定仕様(2026-07-09)により、これが
    # 唯一のリワード広告ボタン(選ぶUIは廃止・完全ランダム付与)。
    def _place_garden_item(item_id):
        st.session_state.garden_item_placement = garden_items.place_item(item_id)
    def _place_garden_item(item_id):
        st.session_state.garden_item_placement = garden_items.place_item(item_id)

    ads.render_garden_item_button(
        st.session_state, st.session_state.biome, BIRDS,
        place_fn=_place_garden_item, key_prefix="home_ads",
    )


# ---------- Tab: Radio ----------
with tab_radio:
    _radio_season = current_app_season()
    _radio_meta   = _SEASON_META[_radio_season]
    _weeks_left   = weeks_until_next_season()
    st.markdown(
        f"### 🎙 庭のラジオ &nbsp; "
        f"<span style='font-size:0.75em;font-weight:400;color:#7a9a6a;'>"
        f"{_radio_meta['icon']} 今は{_radio_meta['jp']} &nbsp;·&nbsp; "
        f"あと{_weeks_left}週で次の季節へ</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "ここはあなたのコレクション。一度会った鳥は、庭を離れても、ここではいつでも会える。"
        "会った鳥が増えるほどキャストは豊かになり、よく会った鳥は群れで鳴く。",
        help="嵐や伐採で庭の植物が倒れても、ここで鳴く鳥は減りません。"
             "渡り鳥は季節が外れると一時的に引っ込みます。"
             "よく観察した鳥ほど近くで・群れで聞こえます。",
    )
    if st.session_state.get("current_tester_id"):
        # 図鑑(訪問記録 discovered)の鳥もラジオで鳴ける。
        # 儀式での近距離観察(observed)があれば、その回数で「近さ」が決まる。
        _radio_obs = dict(st.session_state.get("observed", {}))
        for _bid in st.session_state.get("discovered", set()):
            _radio_obs.setdefault(_bid, {"count": 1, "first": "", "last": ""})
        # 今日の庭(1日1回・全員共通)。留守が空振りの日でも「今日」だけは新しい。
        daily.render_todays_garden(
            st.session_state.biome, BIRDS, _radio_obs,
            biome_label=BIOMES.get(st.session_state.biome, {}).get("name", ""),
            sprite_html_fn=render_bird_sprite_html,
            audio_render_fn=lambda bid, bd: render_bird_audio(bid, bd, key_prefix="today_"),
        )
        render_radio(
            biome_id=st.session_state.biome,
            observed=_radio_obs,
            birds_data=BIRDS,
        )
    else:
        st.info("庭をはじめると、あなたが出会った鳥たちの声が聴けます。")


# ---------- Tab: Plant ----------
with tab_plant:
    st.markdown("### 🌱 植物を植える")
    st.markdown("植物が他の生き物(昆虫・鳥)と**どう相互作用するか**が、やってくる鳥を決めます。")

    # 念のため重複を排除(収容力は「種数」。重複行が紛れても種数で数える)
    _seen = set()
    st.session_state.planted = [
        p for p in st.session_state.planted
        if not (p in _seen or _seen.add(p))
    ]
    planted_ids = set(st.session_state.planted)
    available = {pid: p for pid, p in PLANTS.items()
                 if st.session_state.biome in p["biome"]}

    biome_meta = BIOMES[st.session_state.biome]
    max_plants = biome_meta.get("max_plants", 8)
    n_now = len(st.session_state.planted)
    is_full = n_now >= max_plants

    # 本数表示
    bar_color = "#88a858" if not is_full else "#c87a4a"
    st.markdown(
        f"<div style='padding:10px 14px; margin-bottom:14px; "
        f"background:{bar_color}22; border-radius:6px; "
        f"border-left:4px solid {bar_color};'>"
        f"<b>土地の収容力: {n_now} / {max_plants} 種</b>"
        f"<span style='color:#888; margin-left:10px; font-size:0.88em;'>"
        f"({biome_meta['name'].split('(')[0]}は最大 {max_plants} 種まで植えられます)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if is_full:
        st.warning(
            "土地が一杯です。新しく植えるには、下の「植えた植物」から1つ抜いてください。",
            icon="🌾"
        )

    st.info("🧪 確率変化(鳥×植物)は「シミュ」タブで確認できます。")

    cols = st.columns(3)
    for i, (pid, plant) in enumerate(available.items()):
        with cols[i % 3]:
            is_planted = pid in planted_ids
            icon = plant.get("icon", "🌱")
            label = f"{'✅' if is_planted else icon} {plant['name']}"
            disabled = is_planted or is_full
            if st.button(label, key=f"plant_{pid}",
                         use_container_width=True, disabled=disabled):
                st.session_state.planted.append(pid)
                tid = st.session_state.current_tester_id
                _sheets_safe(sc.add_planting, tid, pid)
                _sheets_safe(sc.log_access, tid, "plant", "plant_added", pid)
                st.session_state.planted_at_map[pid] = datetime.now().isoformat(
                    timespec="seconds"
                )
                st.rerun()
            sci = plant.get("scientific", "")
            en = plant.get("english", "")
            sci_line = f"_{sci}_" + (f" / {en}" if en else "")
            st.caption(f"{sci_line}  \n適温: {plant['temp_fit'][0]}-{plant['temp_fit'][1]}℃")

    st.markdown("---")
    st.markdown("### 🌿 植えた植物")
    if st.session_state.planted:
        for idx, pid in enumerate(st.session_state.planted):
            if pid not in PLANTS:
                continue
            pl = PLANTS[pid]

            cols_p = st.columns([6, 1])
            with cols_p[0]:
                st.markdown(
                    f"<div style='padding:8px 12px; margin:3px 0; "
                    f"background:#f5f8ee; border-left:3px solid #88a858; "
                    f"border-radius:6px; display:flex; align-items:center; gap:10px;'>"
                    f"<span style='font-size:1.2em;'>{pl.get('icon', '🌱')}</span>"
                    f"<b>{pl['name']}</b>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with cols_p[1]:
                # key は行ごとに一意(同じ植物が複数植わっていても衝突しない)
                if st.button("🗑️", key=f"remove_{idx}_{pid}",
                             help=f"{pl['name']}を抜く",
                             use_container_width=True):
                    # session_state から1本除去
                    st.session_state.planted.remove(pid)
                    if pid not in st.session_state.planted:
                        st.session_state.planted_at_map.pop(pid, None)
                    tid = st.session_state.current_tester_id
                    _sheets_safe(sc.remove_planting, tid, pid)
                    _sheets_safe(sc.log_access, tid, "plant", "plant_removed", pid)
                    st.rerun()

        st.markdown("")
        if st.button("🗑️ 全部抜く"):
            st.session_state.planted = []
            st.session_state.planted_at_map = {}
            st.session_state.residents = set()
            tid = st.session_state.current_tester_id
            _sheets_safe(sc.remove_all_plantings, tid)
            _sheets_safe(sc.log_access, tid, "plant", "plant_removed_all")
            st.rerun()
    else:
        st.caption("まだ何も植えていません。")


# ---------- Tab: Simulator (鳥×植物の確率シミュ) ----------
with tab_sim:
    st.markdown("### 🧪 シミュレーター")
    st.caption(
        "「この土地に、この植物を植えたら、この鳥の出現確率がどう変わるか」を試せます。"
        "実際に植えたり植え替えたりする前に、効果を確認するためのツールです。"
    )

    # === 土地を選ぶ ===
    biome_options = list(BIOMES.keys())
    sim_biome = st.selectbox(
        "🌍 土地",
        options=biome_options,
        format_func=lambda b: BIOMES[b]["name"],
        index=biome_options.index(st.session_state.biome),
        key="sim_biome_select",
    )
    sim_temp = current_temperature(sim_biome, st.session_state.month)
    st.caption(
        f"📅 {st.session_state.month}月 · 🌡️ {sim_temp:.1f}℃"
    )

    st.markdown("")

    # === 鳥と植物のプルダウン(2列) ===
    col_bird, col_plant = st.columns(2)

    with col_bird:
        st.markdown("**🐦 鳥を選ぶ**")
        # その土地に生息する鳥を絞る
        birds_in_biome = [
            b_id for b_id, bird in BIRDS.items()
            if sim_biome in bird.get("biome_pref", [])
        ]
        # レア度順にソート
        birds_in_biome.sort(key=lambda b: BIRDS[b]["rarity"])
        sim_bird = st.selectbox(
            "鳥",
            options=birds_in_biome,
            format_func=lambda b: f"{BIRDS[b]['name']} (★{int(BIRDS[b]['rarity']*5)+1})",
            label_visibility="collapsed",
            key="sim_bird_select",
        )

    with col_plant:
        st.markdown("**🌱 追加候補の植物を選ぶ**")
        # その土地で植えられる植物のうち、現在まだ植えていないもの
        plants_in_biome = [
            p_id for p_id, plant in PLANTS.items()
            if sim_biome in plant.get("biome", [])
        ]
        # 既に植えてあるかどうかを末尾に注記
        already_planted_set = set(st.session_state.planted)
        sim_plant = st.selectbox(
            "植物",
            options=plants_in_biome,
            format_func=lambda p: (
                f"{PLANTS[p].get('icon', '🌱')} {PLANTS[p]['name']}"
                + (" (植え済み)" if p in already_planted_set else "")
            ),
            label_visibility="collapsed",
            key="sim_plant_select",
        )

    st.markdown("")

    # === 結果表示 ===
    if sim_bird and sim_plant:
        # 現状(同じバイオームで現在植えている植物のみ・他バイオームの植物は除外)
        current_planted_in_biome = [
            p for p in st.session_state.planted
            if p in PLANTS and sim_biome in PLANTS[p].get("biome", [])
        ]

        # キャッシュキーに使うタプル(順序非依存)
        before_tuple = tuple(sorted(current_planted_in_biome))

        # before: シミュレート土地で、現在植えてある植物のみ
        info_before = _cached_arrival_probability(
            sim_bird, before_tuple, sim_biome, st.session_state.month
        )
        prob_before = info_before["probability"]

        # after: その上に候補植物を追加(既に植えてあるなら同じ結果)
        if sim_plant in current_planted_in_biome:
            after_tuple = before_tuple
            note_already = True
        else:
            after_tuple = tuple(sorted(current_planted_in_biome + [sim_plant]))
            note_already = False

        info_after = _cached_arrival_probability(
            sim_bird, after_tuple, sim_biome, st.session_state.month
        )
        prob_after = info_after["probability"]

        delta = prob_after - prob_before
        bird = BIRDS[sim_bird]
        plant = PLANTS[sim_plant]
        bird_color = bird.get("color", "#888")

        # 大きな結果表示
        if note_already:
            verdict_color = "#888"
            verdict_label = "(既に植え済み・効果は反映済み)"
        elif delta > 0.001:
            verdict_color = "#3a8a3a"
            verdict_label = f"+{delta*100:.1f}%"
        elif delta < -0.001:
            verdict_color = "#c83a3a"
            verdict_label = f"{delta*100:.1f}%"
        else:
            verdict_color = "#888"
            verdict_label = "変化なし"

        # 結果を文章ベースで表示
        biome_short = BIOMES[sim_biome]['name']
        st.markdown(
            f"<div style='padding:20px; margin-top:10px; "
            f"background:linear-gradient(135deg, #fafcf2 0%, #f0f5e6 100%); "
            f"border-radius:12px; border-left:5px solid {bird_color};'>"
            f"<div style='font-size:1.0em; color:#3a4a3a; line-height:1.7;'>"
            f"今の <b>{biome_short}</b> の生態系に "
            f"<b>{plant.get('icon', '🌱')} {plant['name']}</b> を導入すると、"
            f"<b style='color:{bird_color};'>{bird['name']}</b> が来る確率は…"
            f"</div>"
            f"<div style='font-size:1.4em; margin-top:14px; "
            f"color:#3a4a3a; text-align:center;'>"
            f"<b>{prob_before*100:.1f}%</b>"
            f"<span style='color:#aaa; margin:0 14px;'>→</span>"
            f"<b style='color:{verdict_color};'>{prob_after*100:.1f}%</b>"
            f"<span style='font-size:0.7em; color:{verdict_color}; "
            f"margin-left:10px;'>({verdict_label})</span>"
            f"</div></div>",
            unsafe_allow_html=True
        )

        # 内訳: なぜこの確率になったか(after側の食物経路を表示)
        with st.expander("🔍 計算の内訳"):
            st.markdown(f"**{bird['name']} の出現確率の構成**")
            cols_inf = st.columns(2)
            with cols_inf[0]:
                st.markdown("**現状(before)**")
                st.write(f"気温適合度: {info_before['temp_fit']:.2f}")
                st.write(f"バイオーム補正: ×{info_before['biome_bonus']}")
                st.write(f"食物スコア: {info_before['food_score']:.2f}")
                st.write(f"レア度係数: {info_before['rarity_factor']:.2f}")
            with cols_inf[1]:
                st.markdown(f"**追加後(+{plant['name']})**")
                st.write(f"気温適合度: {info_after['temp_fit']:.2f}")
                st.write(f"バイオーム補正: ×{info_after['biome_bonus']}")
                st.write(f"食物スコア: {info_after['food_score']:.2f}")
                st.write(f"レア度係数: {info_after['rarity_factor']:.2f}")

            if info_after["incoming_paths"]:
                st.markdown("---")
                st.markdown("**追加後の食物経路**")
                for kind, target_id, weight in info_after["incoming_paths"][:5]:
                    name = target_id
                    if kind == "plant" and target_id in PLANTS:
                        name = PLANTS[target_id]["name"]
                    elif kind == "insect" and target_id in INSECTS:
                        name = INSECTS[target_id]["name"]
                    st.write(f"- {name} (寄与 {weight:.2f})")


# ---------- Tab: Birds ----------
with tab_birds:
    st.markdown("### 📖 鳥類図鑑")

    cols_top = st.columns([2, 3])
    with cols_top[0]:
        filter_mode = st.radio(
            "表示", ["全種", "発見済みのみ", "未発見のみ"],
            horizontal=True, label_visibility="collapsed",
        )
    with cols_top[1]:
        view_mode_dex = st.radio(
            "並び", ["地域別", "レア度順"],
            horizontal=True, label_visibility="collapsed",
        )

    G_now, _ = build_network(
        st.session_state.planted, st.session_state.biome, st.session_state.month
    )

    # バイオーム別の発見状況サマリ(地域別表示時のみ)
    if view_mode_dex == "地域別":
        sum_cols = st.columns(len(BIOMES))
        for i, (bid, biome) in enumerate(BIOMES.items()):
            birds_in = [b for b, d in BIRDS.items() if bid in d.get("biome_pref", [])]
            found = sum(1 for b in birds_in if b in st.session_state.discovered)
            total = len(birds_in)
            pct = (found / total * 100) if total > 0 else 0
            with sum_cols[i]:
                st.markdown(
                    f"<div style='text-align:center; padding:10px; "
                    f"background:#f5f8ee; border-radius:8px; "
                    f"border-top:3px solid #88a858;'>"
                    f"<div style='color:#5a7a3a; font-size:0.95em; font-weight:600;'>"
                    f"📍 {biome['name']}</div>"
                    f"<div style='font-size:1.2em; font-weight:600; margin-top:4px;'>"
                    f"{found}<span style='font-size:0.7em; color:#888;'> / {total}</span></div>"
                    f"<div style='font-size:0.75em; color:#888;'>{pct:.0f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        st.markdown("")

    # 表示順を組み立て: 地域別なら バイオーム→レア度、レア度順なら 発見済み→レア度
    if view_mode_dex == "地域別":
        sorted_birds = []
        last_biome_for = {}  # bird_id -> biome_id (for header injection)
        for bid in BIOMES.keys():
            in_biome = [
                (b, d) for b, d in BIRDS.items()
                if bid in d.get("biome_pref", [])
            ]
            in_biome.sort(key=lambda kv: kv[1]["rarity"])
            for b_id, bird_d in in_biome:
                if b_id not in last_biome_for:  # 重複防止(複数バイオーム所属の場合)
                    last_biome_for[b_id] = bid
                    sorted_birds.append((b_id, bird_d))
    else:
        sorted_birds = sorted(
            BIRDS.items(),
            key=lambda kv: (kv[0] not in st.session_state.discovered, kv[1]["rarity"])
        )
        last_biome_for = {}

    # 地域ヘッダの注入用に、各鳥が属するバイオームを把握
    current_header_biome = None

    _observed_map = st.session_state.get("observed", {})
    for b_id, bird in sorted_birds:
        observed = b_id in _observed_map  # 儀式で近くまで来た=詳細解放
        # 近くで観察できた鳥は当然「来た鳥」でもある
        discovered = (b_id in st.session_state.discovered) or observed
        obs_count = _observed_map.get(b_id, {}).get("count", 0)
        if filter_mode == "発見済みのみ" and not discovered: continue
        if filter_mode == "未発見のみ" and discovered: continue

        # 地域別表示で、新しいバイオームに入ったらヘッダ表示
        if view_mode_dex == "地域別":
            this_biome = last_biome_for.get(b_id)
            if this_biome and this_biome != current_header_biome:
                current_header_biome = this_biome
                biome_name = BIOMES[this_biome]["name"]
                st.markdown(
                    f"<h4 style='margin-top:18px; padding-top:8px; "
                    f"border-top:2px solid #d8e5c8; color:#3a5a3a;'>"
                    f"🌍 {biome_name}</h4>",
                    unsafe_allow_html=True
                )

        _icon = "🪶" if observed else ("🐦" if discovered else "❓")
        # 会った日数(1日1カウント)。節目で静かな称号を添える(競争でなく愛着)。
        _met_days = st.session_state.get("bird_days", {}).get(b_id, {}).get("days", 0)
        if _met_days >= 100:
            _days_label = f"　🏅 会った日数 {_met_days}日・皆勤の友"
        elif _met_days >= 30:
            _days_label = f"　🌿 会った日数 {_met_days}日・常連"
        elif _met_days >= 10:
            _days_label = f"　🌱 会った日数 {_met_days}日・おなじみ"
        elif _met_days >= 1:
            _days_label = f"　会った日数 {_met_days}日"
        else:
            _days_label = ""
        with st.expander(
            f"{_icon} "
            f"{bird['name'] if discovered else '???'} "
            f"(レア度 {'★' * (1 + int(bird['rarity'] * 5))})"
            + (_days_label if discovered else ""),
            expanded=False,
        ):
            if observed:
                # 詳細ドット絵(高解像度)があれば、種の詳細表示にのみ大きく表示。
                # ファイルが無い種は何も描画しない(今まで通りの表示のまま)。
                _detail_img_html = render_bird_detail_image_html(b_id)
                if _detail_img_html:
                    st.markdown(_detail_img_html, unsafe_allow_html=True)

                # スプライト(ドット絵)を表示。ファイルがなければ Emoji。
                sprite_html = render_bird_sprite_html(
                    b_id, size_px=128, fallback_emoji="🐦"
                )
                bird_color = bird.get("color", "#888")
                st.markdown(
                    f"<div style='display:flex; align-items:center; gap:16px; "
                    f"padding:14px; margin-bottom:8px; "
                    f"background:linear-gradient(135deg, {bird_color}11, {bird_color}22); "
                    f"border-radius:10px; border-left:4px solid {bird_color};'>"
                    f"<div style='flex-shrink:0;'>{sprite_html}</div>"
                    f"<div style='flex-grow:1;'>"
                    f"<div style='font-size:1.4em; font-weight:600; color:#2a3a2a;'>"
                    f"{bird['name']}</div>"
                    f"<div style='color:#666; font-style:italic;'>"
                    f"{bird['scientific']}"
                    f"{' / ' + bird.get('english', '') if bird.get('english') else ''}"
                    f"</div></div></div>",
                    unsafe_allow_html=True,
                )
                # 節目バッジ(会った日数 10/30/100日)。静かな一言のみ、数値の
                # 進捗バーやカウントダウンは出さない(HANDOFF §8 の精神を踏襲)。
                _badge = badges.badge_for_days(_met_days)
                if _badge:
                    st.markdown(
                        f"<div style='display:inline-block; margin:2px 0 10px; "
                        f"padding:4px 12px; background:#fff6d8; border-radius:14px; "
                        f"font-size:0.88em; color:#7a6a2a;'>"
                        f"{_badge['icon']} {bird['name']}とは{_badge['message']}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                if obs_count:
                    st.caption(f"🪶 近くで観察できた回数: {obs_count}回")
                # 観察済みの鳥の鳴き声を図鑑で聴ける(儀式で近づいた報酬)
                render_bird_audio(b_id, bird)
                st.write(bird["description"])

                # 外部リンク: 名前で Google画像検索 / Wikipedia を開く
                import urllib.parse as _urlparse
                _q_jp = _urlparse.quote(bird['name'])
                _q_sci = _urlparse.quote(bird['scientific'])
                _links_html = (
                    f"<div style='margin:6px 0 14px 0;'>"
                    f"<a href='https://www.google.com/search?tbm=isch&q={_q_jp}+{_q_sci}' "
                    f"target='_blank' rel='noopener' "
                    f"style='display:inline-block; margin-right:8px; padding:4px 10px; "
                    f"background:#f0f4ec; border-radius:12px; "
                    f"text-decoration:none; color:#3a5a3a; font-size:0.85em;'>"
                    f"🖼️ 実物の画像を見る</a>"
                    f"<a href='https://en.wikipedia.org/wiki/Special:Search?search={_q_sci}' "
                    f"target='_blank' rel='noopener' "
                    f"style='display:inline-block; margin-right:8px; padding:4px 10px; "
                    f"background:#f0f4ec; border-radius:12px; "
                    f"text-decoration:none; color:#3a5a3a; font-size:0.85em;'>"
                    f"📖 Wikipedia(英)</a>"
                    f"</div>"
                )
                st.markdown(_links_html, unsafe_allow_html=True)

                # 食べるもの: 学名併記で表示
                if bird["eats_plants"] or bird["eats_insects"]:
                    st.markdown("**食べるもの:**")
                    if bird["eats_plants"]:
                        plant_lines = []
                        for p in bird["eats_plants"]:
                            if p in PLANTS:
                                pl = PLANTS[p]
                                en2 = f" / {pl['english']}" if pl.get("english") else ""
                                plant_lines.append(
                                    f"🌱 {pl['name']} _({pl['scientific']}{en2})_"
                                )
                        if plant_lines:
                            for line in plant_lines:
                                st.markdown(f"  - {line}")
                    if bird["eats_insects"]:
                        for i in bird["eats_insects"]:
                            if i in INSECTS:
                                ins = INSECTS[i]
                                en2 = f" / {ins['english']}" if ins.get("english") else ""
                                st.markdown(
                                    f"  - 🐛 {ins['name']} _({ins['scientific']}{en2})_"
                                )

                st.write(f"**適温域:** {bird['temp_fit'][0]}〜{bird['temp_fit'][1]}℃")
                st.write(f"**好む環境:** {', '.join(BIOMES[b]['name'] for b in bird['biome_pref'])}")

                info = calculate_arrival_probability(
                    b_id, G_now, st.session_state.biome, st.session_state.month
                )

                st.progress(info["probability"], text=f"現状の出現確率: {info['probability']:.0%}")
                with st.expander("なぜこの確率?"):
                    st.write(f"- 気温適合度: {info['temp_fit']:.2f}")
                    st.write(f"- バイオーム補正: ×{info['biome_bonus']}")
                    st.write(f"- 食物スコア: {info['food_score']:.2f} → 係数 {info['food_factor']:.2f}")
                    st.write(f"- レア度係数: {info['rarity_factor']:.2f}")
                    if info.get("centrality_used"):
                        st.write(
                            f"- GloBI補正済PageRank: **{info['centrality_used']:.2e}** "
                            f"(生態的な重要度スコアを使用)"
                        )
                    if info["incoming_paths"]:
                        paths = "、".join(
                            f"{p[1]}({p[2]:.2f})" for p in info["incoming_paths"]
                        )
                        st.write(f"- 食物経路: {paths}")

                # ===== 「呼ぶには」セクション =====
                _sugg = suggest_for_bird(
                    b_id, st.session_state.planted,
                    st.session_state.biome, st.session_state.month
                )
                if _sugg and _sugg["suggestions"]:
                    st.markdown("**🎯 この鳥を呼ぶには**")
                    cur_prob = _sugg["current_prob"]
                    for s in _sugg["suggestions"][:6]:  # 上位6件まで
                        pl = PLANTS.get(s["plant_id"])
                        if not pl:
                            continue
                        # 仮想シミュレーション: その植物を追加した場合の確率
                        from engine import simulate_with_added_plant
                        sim_prob = simulate_with_added_plant(
                            b_id, st.session_state.planted, s["plant_id"],
                            st.session_state.biome, st.session_state.month
                        )
                        delta = sim_prob - cur_prob
                        delta_color = (
                            "#3a8a3a" if delta > 0.001 else "#888"
                        )
                        delta_str = f"+{delta*100:.1f}%" if delta > 0.001 else "—"
                        tag = "🌟" if s["directness"] == "direct" else "🔗"
                        st.markdown(
                            f"<div style='padding:8px 12px; margin:4px 0; "
                            f"background:#f5f7e8; border-left:3px solid #88a858; "
                            f"border-radius:6px; font-size:0.9em; "
                            f"display:flex; align-items:center; gap:10px;'>"
                            f"<div style='flex-grow:1;'>"
                            f"<b>{tag} {pl.get('icon', '🌱')} {pl['name']}を植える</b>"
                            f"<span style='color:#888; font-size:0.82em; "
                            f"margin-left:6px;'>{s['reason']}</span></div>"
                            f"<div style='font-size:0.85em; color:{delta_color}; "
                            f"font-weight:600; white-space:nowrap;'>"
                            f"{cur_prob*100:.1f}% → {sim_prob*100:.1f}% "
                            f"<span style='font-size:0.9em;'>({delta_str})</span>"
                            f"</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                elif _sugg and _sugg["has_food_path"]:
                    st.caption("✓ 食物条件は満たされています。あとは時間とレア度次第。")

                # この鳥から得た落とし物
                _owned_set_dex = st.session_state.get("mementos_set", set())
                # この鳥の落とし物候補(全鳥共通の小枝・羽根、一部の鳥のみ羽冠)
                possible = mem.possible_mementos_from_bird(b_id, BIRDS)
                _from_this_bird = [
                    m for m in st.session_state.get("mementos", [])
                    if m.get("via_bird_id") == b_id
                ]
                if _from_this_bird or any(p in _owned_set_dex for p in possible):
                    st.markdown("**🎁 この鳥にまつわる落とし物**")
                    # 入手済みのうち、この鳥由来のもの
                    seen_ids = set()
                    icons_md = []
                    for m_rec in _from_this_bird:
                        mid = m_rec["memento_id"]
                        if mid in seen_ids:
                            continue
                        seen_ids.add(mid)
                        icon, name, _, color = mem.memento_display(
                            mid, BIRDS, PLANTS, BIOMES
                        )
                        icons_md.append(
                            f"<span style='display:inline-block; padding:4px 10px; "
                            f"margin:2px 4px 2px 0; background:{color}22; "
                            f"border-radius:14px; font-size:0.88em;'>"
                            f"{icon} {name}</span>"
                        )
                    if icons_md:
                        st.markdown(
                            "<div style='line-height:2;'>" + "".join(icons_md) + "</div>",
                            unsafe_allow_html=True
                        )
                    # 未入手の羽根があれば「次の目標」として表示
                    feather_mid = mem.feather_id(b_id)
                    if feather_mid not in _owned_set_dex:
                        st.caption(f"🪶 まだ {bird['name']} の羽根は手に入っていません。")

                # これまで出会った土地(bird_visits 由来、自動表示)
                _visited_biomes = st.session_state.get("bird_visited_biomes", {})
                _auto_locs = _visited_biomes.get(b_id, set())
                if _auto_locs:
                    loc_chips = " ".join(
                        f"<span style='display:inline-block; padding:3px 10px; "
                        f"margin-right:6px; background:#eef2e8; "
                        f"border-radius:12px; font-size:0.85em;'>"
                        f"📍 {BIOMES[bb]['name'].split('(')[0]}</span>"
                        for bb in _auto_locs if bb in BIOMES
                    )
                    if loc_chips:
                        st.markdown(
                            f"<div style='margin:8px 0;'>"
                            f"<span style='color:#888; font-size:0.85em; margin-right:6px;'>"
                            f"これまで出会った土地:</span>{loc_chips}</div>",
                            unsafe_allow_html=True
                        )

                # 生態ログ: これまでに記録された「なぜ来たか」を重複除去して蓄積表示。
                # あなたが組んだ関係(食物網)が実際に鳥を呼んだ証拠として、短文のみ
                # 3〜4行程度に抑えて見せる(撹乱で植物が失われても消さない)。
                _eco_entries = eco_log.entries_for_bird(
                    st.session_state.get("eco_log", []), b_id
                )
                if _eco_entries:
                    st.markdown("**🌤 これまでの来訪理由**")
                    _obs_first = _observed_map.get(b_id, {}).get("first")
                    for _entry in _eco_entries[:4]:
                        _founding = eco_log.is_founding_record(
                            _entry, _eco_entries, _obs_first
                        )
                        _mark = " 🌱" if _founding else ""
                        st.markdown(
                            f"<div style='font-size:0.86em; color:#5a6a4a; "
                            f"margin:2px 0;'>・{_entry['text']}{_mark}</div>",
                            unsafe_allow_html=True,
                        )
            elif discovered:
                # 来た鳥(名前・学名・外部リンクは解放、詳細生態は伏せる)
                import urllib.parse as _urlparse
                _q_jp2 = _urlparse.quote(bird['name'])
                _q_sci2 = _urlparse.quote(bird['scientific'])
                sprite_html = render_bird_sprite_html(
                    b_id, size_px=96, fallback_emoji="🐦"
                )
                bird_color = bird.get("color", "#888")
                en_str = f" / {bird['english']}" if bird.get("english") else ""
                st.markdown(
                    f"<div style='display:flex; align-items:center; gap:16px; "
                    f"padding:14px; margin-bottom:8px; "
                    f"background:linear-gradient(135deg, {bird_color}11, {bird_color}22); "
                    f"border-radius:10px; border-left:4px solid {bird_color};'>"
                    f"<div style='flex-shrink:0; opacity:0.85;'>{sprite_html}</div>"
                    f"<div style='flex-grow:1;'>"
                    f"<div style='font-size:1.3em; font-weight:600; color:#2a3a2a;'>"
                    f"{bird['name']}</div>"
                    f"<div style='color:#888; font-style:italic; font-size:0.88em;'>"
                    f"{bird['scientific']}{en_str}</div>"
                    f"<div style='color:#888; font-size:0.83em; margin-top:4px;'>"
                    f"あなたの土地に来たことがあります</div>"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div style='margin:4px 0 12px 0;'>"
                    f"<a href='https://www.google.com/search?tbm=isch&q={_q_jp2}+{_q_sci2}' "
                    f"target='_blank' rel='noopener' "
                    f"style='display:inline-block; margin-right:8px; padding:4px 10px; "
                    f"background:#f0f4ec; border-radius:12px; "
                    f"text-decoration:none; color:#3a5a3a; font-size:0.85em;'>"
                    f"🖼️ 画像を見る</a>"
                    f"<a href='https://en.wikipedia.org/wiki/Special:Search?search={_q_sci2}' "
                    f"target='_blank' rel='noopener' "
                    f"style='display:inline-block; padding:4px 10px; "
                    f"background:#f0f4ec; border-radius:12px; "
                    f"text-decoration:none; color:#3a5a3a; font-size:0.85em;'>"
                    f"📖 Wikipedia(英)</a>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.info("🔭 まだ遠くから気配を感じただけ。近くまで来てくれたら、詳しい生態が記録されます。")
            else:
                st.write("???")
                st.caption("環境を整えて、出会えるのを待ちましょう。")


# ---------- Tab: Mementos (落とし物) ----------
with tab_mementos:
    st.markdown("### 🎁 鳥たちの落とし物")
    st.caption("鳥が立ち寄ったとき、ときどき小さな宝物を残していくことがあります。")

    # 全候補と入手済み
    _all_mementos = mem.all_possible_mementos(BIRDS, PLANTS)
    _owned_set = st.session_state.get("mementos_set", set())
    _owned_list = st.session_state.get("mementos", [])

    # サマリ
    by_cat_total = {}
    by_cat_owned = {}
    for m in _all_mementos:
        c = m["category"]
        by_cat_total[c] = by_cat_total.get(c, 0) + 1
    for mid in _owned_set:
        c = mem.memento_category(mid)
        by_cat_owned[c] = by_cat_owned.get(c, 0) + 1

    # サマリ表示: 現行3カテゴリのみ表示(seed/nutは旧データ用に内部処理は残す)
    cat_meta = [
        ("twig",    "🌿 小枝",  "#8a6a4a"),
        ("feather", "🪶 羽根",  "#9a8a6a"),
        ("plume",   "✨ 羽冠",  "#c8a830"),
    ]
    cols = st.columns(len(cat_meta))
    for i, (cat_id, cat_label, cat_color) in enumerate(cat_meta):
        owned = by_cat_owned.get(cat_id, 0)
        total = by_cat_total.get(cat_id, 0)
        pct = (owned / total * 100) if total > 0 else 0
        with cols[i]:
            st.markdown(
                f"<div style='text-align:center; padding:12px; "
                f"background:{cat_color}22; border-radius:8px; "
                f"border-top:3px solid {cat_color};'>"
                f"<div style='color:{cat_color}; font-weight:600; "
                f"font-size:0.95em;'>{cat_label}</div>"
                f"<div style='font-size:1.3em; font-weight:600; margin-top:4px;'>"
                f"{owned}<span style='font-size:0.7em; color:#888;'> / {total}</span></div>"
                f"<div style='font-size:0.75em; color:#888;'>{pct:.0f}%</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ビュー切り替え
    view_mode = st.radio(
        "表示",
        options=["落とし物別", "鳥別"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if view_mode == "落とし物別":
        # カテゴリ別に折りたたみで表示
        for cat_id, cat_label, cat_color in cat_meta:
            cat_items = [m for m in _all_mementos if m["category"] == cat_id]
            owned_in_cat = sum(1 for it in cat_items if it["id"] in _owned_set)
            with st.expander(
                f"{cat_label}　{owned_in_cat} / {len(cat_items)}",
                expanded=(cat_id in ("feather", "seed")),
            ):
                # グリッド表示
                items_per_row = 4
                for row_start in range(0, len(cat_items), items_per_row):
                    row = cat_items[row_start:row_start + items_per_row]
                    grid_cols = st.columns(items_per_row)
                    for j, item in enumerate(row):
                        with grid_cols[j]:
                            mid = item["id"]
                            owned = mid in _owned_set
                            icon, name, desc, color = mem.memento_display(
                                mid, BIRDS, PLANTS, BIOMES
                            )
                            # 入手済み: カラフル / 未入手: グレースケール風
                            if owned:
                                bg = f"{color}22"
                                border = f"2px solid {color}"
                                opacity = "1"
                                icon_size = "2.2em"
                            else:
                                bg = "#f0f0f0"
                                border = "2px dashed #ccc"
                                opacity = "0.35"
                                icon_size = "2.0em"
                            display_name = name if owned else "???"
                            st.markdown(
                                f"<div style='background:{bg}; padding:12px 8px; "
                                f"border-radius:8px; border:{border}; "
                                f"text-align:center; min-height:90px; "
                                f"opacity:{opacity}; margin-bottom:8px;'>"
                                f"<div style='font-size:{icon_size};'>{icon}</div>"
                                f"<div style='font-size:0.82em; color:#555; "
                                f"margin-top:4px; line-height:1.2;'>{display_name}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
    else:
        # 鳥別ビュー: 各鳥の落とし物進捗を可視化
        # 入手済みアイテムのバケット(via_bird_id でひける)
        owned_by_bird = {}
        for m_rec in _owned_list:
            via = m_rec.get("via_bird_id", "")
            if via:
                owned_by_bird.setdefault(via, set()).add(m_rec["memento_id"])

        # 図鑑登録済みの鳥のみ表示(未発見の鳥は隠す)
        discovered = st.session_state.get("discovered", set())
        if not discovered:
            st.info("まだ鳥が来ていません。先にホーム画面で鳥との出会いを待ちましょう。")
        else:
            # レア度順
            sorted_birds = sorted(
                [b for b in BIRDS if b in discovered],
                key=lambda x: BIRDS[x].get("rarity", 0)
            )
            for bird_id in sorted_birds:
                bird = BIRDS[bird_id]
                color = bird.get("color", "#888")
                possible = mem.possible_mementos_from_bird(bird_id, BIRDS)
                owned_here = owned_by_bird.get(bird_id, set())
                owned_count = len(set(possible) & owned_here)
                total_count = len(possible)
                pct = (owned_count / total_count * 100) if total_count > 0 else 0

                # 各候補のアイコンを入手済み/未入手で表示
                icons_html = ""
                for mid in possible:
                    icon, name, _, ic_color = mem.memento_display(
                        mid, BIRDS, PLANTS, BIOMES
                    )
                    is_owned = mid in owned_here
                    if is_owned:
                        icons_html += (
                            f"<span title='{name}' style='display:inline-block; "
                            f"margin:0 4px; font-size:1.4em;'>{icon}</span>"
                        )
                    else:
                        icons_html += (
                            f"<span title='{name}(未入手)' style='display:inline-block; "
                            f"margin:0 4px; font-size:1.4em; opacity:0.25; "
                            f"filter:grayscale(1);'>{icon}</span>"
                        )

                # 進捗バー
                bar_html = (
                    f"<div style='width:100%; height:5px; background:#eee; "
                    f"border-radius:3px; margin-top:6px; overflow:hidden;'>"
                    f"<div style='width:{pct}%; height:100%; background:{color};'></div>"
                    f"</div>"
                )

                st.markdown(
                    f"<div style='padding:14px 16px; margin-bottom:10px; "
                    f"background:{color}11; border-left:4px solid {color}; "
                    f"border-radius:6px;'>"
                    f"<div style='display:flex; align-items:center;'>"
                    f"<div style='flex-grow:1;'>"
                    f"<b style='font-size:1.05em;'>{bird['name']}</b>"
                    f"<span style='color:#888; font-size:0.85em; margin-left:10px;'>"
                    f"{owned_count} / {total_count} 種 ({pct:.0f}%)</span>"
                    f"</div>"
                    f"<div>{icons_html}</div>"
                    f"</div>"
                    f"{bar_html}"
                    f"</div>",
                    unsafe_allow_html=True
                )


# ---------- Tab: Network (力学モデル) ----------
with tab_network:
    st.markdown("### 🕸️ 生態系ネットワーク")
    st.markdown(
        "あなたの土地で今、活きている**種のつながり**を可視化します。"
        "**中心にあるほどハブ種**(多くの種とつながる重要な種)です。"
        "植物・昆虫・食物経路がある鳥のみ表示しています。"
    )

    # ネットワーク図用のキャッシュ済みデータを取得
    _planted_tuple = tuple(sorted(st.session_state.planted))
    _residents_tuple = tuple(sorted(st.session_state.residents))
    _net_data = _cached_network_layout(
        _planted_tuple, st.session_state.biome,
        st.session_state.month, _residents_tuple
    )

    # キャッシュ結果から NetworkX グラフを再構築 (既存ロジック互換)
    import networkx as nx
    G_net = nx.DiGraph()
    for nd in _net_data["nodes"]:
        G_net.add_node(
            nd["id"],
            kind=nd["kind"], label=nd["label"], color=nd["color"]
        )
    for ed in _net_data["edges"]:
        G_net.add_edge(ed["src"], ed["tgt"], weight=ed["weight"])
    pos = {k: tuple(v) for k, v in _net_data["pos"].items()}
    temp_net = _net_data["temp"]

    if G_net.number_of_nodes() == 0:
        st.info("まだネットワークがありません。植物を植えてみましょう。")
    else:
        W, H = 1200, 900
        # pos は既にキャッシュから取得済み

        # ノードの実座標範囲を測る
        if pos:
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
        else:
            min_x, max_x, min_y, max_y = 0, W, 0, H

        # ラベル分のpadding(左右に150px、上下に60px)
        PAD_X, PAD_Y = 150, 60
        VB_X = min_x - PAD_X
        VB_Y = min_y - PAD_Y
        VB_W = (max_x - min_x) + PAD_X * 2
        VB_H = (max_y - min_y) + PAD_Y * 2

        # iframe表示幅 (1100px) と viewBox の縦横比から、必要な iframe 高さを算出
        DISPLAY_WIDTH = 1100
        component_height = int(DISPLAY_WIDTH * VB_H / VB_W) + 20

        n_plants = sum(1 for n in G_net.nodes if G_net.nodes[n].get("kind") == "plant")
        n_insects = sum(1 for n in G_net.nodes if G_net.nodes[n].get("kind") == "insect")
        n_birds_reachable = sum(
            1 for n in G_net.nodes
            if G_net.nodes[n].get("kind") == "bird" and G_net.in_degree(n) > 0
        )
        n_birds_total = sum(1 for n in G_net.nodes if G_net.nodes[n].get("kind") == "bird")

        # === ネットワーク複雑性のインジケーター ===
        stats = _net_data["stats"]

        cols = st.columns(4)
        with cols[0]:
            st.metric("🌱 植物", f"{stats['n_plants']}種")
        with cols[1]:
            st.metric("🐛 昆虫", f"{stats['n_insects']}種")
        with cols[2]:
            st.metric(
                "🐦 来うる鳥",
                f"{stats['n_birds_active']}種",
                help="食物経路がつながっている鳥の数"
            )
        with cols[3]:
            st.metric("🔗 相互作用", f"{stats['n_edges']}本")

        if stats["hub"] and stats["n_edges"] > 0:
            n_id, n_kind, n_label, n_deg = stats["hub"]
            kind_label = {"plant": "植物", "insect": "昆虫", "bird": "鳥"}.get(n_kind, "")
            st.caption(
                f"💡 今のハブ種: **{n_label}** ({kind_label}, {n_deg}本のつながり)"
            )

        # 凡例
        st.markdown(
            "<div style='display:flex; gap:16px; font-size:0.85em; margin:8px 0; flex-wrap:wrap;'>"
            "<span style='color:#3a5a3a;'><b>●</b> 植えた植物(入力)</span>"
            "<span style='color:#2a4a6a;'><b>●</b> 来た鳥(出力)</span>"
            "<span style='color:#88a0b8;'>● 未訪問の鳥</span>"
            "<span style='color:#c08060;'>● 昆虫</span>"
            "</div>",
            unsafe_allow_html=True
        )

        # SVG組み立て
        svg = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
               f'style="background:#fafcf7; border-radius:8px; width:100%; height:auto;">']

        # エッジ (背景)
        for u, v, d in G_net.edges(data=True):
            if u not in pos or v not in pos: continue
            x1, y1 = pos[u]; x2, y2 = pos[v]
            w = d.get("weight", 0.5)
            svg.append(
                f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                f'stroke="#c8d8c8" stroke-width="{0.5 + w * 0.9:.1f}" stroke-opacity="0.5"/>'
            )

        # ノードスタイル: 入力/出力は濃く大きく、それ以外は淡く小さく
        resident_set = st.session_state.residents

        def node_style(n):
            kind = G_net.nodes[n].get("kind")
            deg = G_net.degree(n)

            if kind == "plant":
                r = 16 + min(deg * 1.0, 8)
                return ("#4a8a4a", r, "#2a4a2a", 2.5)
            if kind == "insect":
                r = 9 + min(deg * 0.4, 4)
                return ("#e8c0a0", r, "#c08060", 1.2)
            # bird - 個別の色を優先
            if n in resident_set:
                # 来た鳥: data.py の color を使う
                color = BIRDS.get(n, {}).get("color", "#2a5aa8")
                r = 18 + min(deg * 0.8, 8)
                return (color, r, "#ffffff", 2.5)
            elif deg > 0:
                r = 10
                return ("#c8d4e4", r, "#ffffff", 1.2)
            else:
                r = 6
                return ("#ececec", r, "#cccccc", 1.0)

        # SVG組み立て(インタラクティブ版、エッジにdata属性)
        svg = [f'<svg viewBox="{VB_X} {VB_Y} {VB_W} {VB_H}" '
               f'xmlns="http://www.w3.org/2000/svg" '
               f'style="background:#fafcf7; border-radius:8px; width:100%; height:auto;">']

        # エッジ(各エッジに class と data-src, data-tgt を設定しホバー時にハイライト可能に)
        for u, v, d in G_net.edges(data=True):
            if u not in pos or v not in pos: continue
            x1, y1 = pos[u]; x2, y2 = pos[v]
            w = d.get("weight", 0.5)
            svg.append(
                f'<line class="edge" data-src="{u}" data-tgt="{v}" '
                f'x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                f'stroke="#c8d8c8" stroke-width="{0.5 + w * 0.9:.1f}" stroke-opacity="0.5"/>'
            )

        # ノード本体(idと data-node を設定、マウスイベント用)
        for n, (x, y) in pos.items():
            color, r, stroke, sw = node_style(n)
            kind = G_net.nodes[n].get("kind", "?")
            svg.append(
                f'<circle class="node node-{kind}" data-node="{n}" '
                f'cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" '
                f'fill="{color}" stroke="{stroke}" stroke-width="{sw}" '
                f'style="cursor:pointer;"/>'
            )

        # ラベル表示対象を決める
        labeled = set()
        for n in G_net.nodes:
            if G_net.nodes[n].get("kind") == "plant":
                labeled.add(n)
        for n in resident_set:
            if n in G_net:
                labeled.add(n)
        for n in G_net.nodes:
            if G_net.nodes[n].get("kind") == "insect":
                labeled.add(n)

        for n, (x, y) in pos.items():
            if n not in labeled: continue
            label = G_net.nodes[n].get("label", n)
            kind = G_net.nodes[n].get("kind")
            _, r, _, _ = node_style(n)

            if kind == "plant":
                lx = x; ly = y + r + 16
                anchor = "middle"; fsize = 13; weight = "700"; fill = "#1a3a1a"
            elif n in resident_set:
                lx = x; ly = y - r - 6
                anchor = "middle"; fsize = 13; weight = "700"; fill = "#1a3a6a"
            elif kind == "insect":
                lx = x + r + 3; ly = y + 3
                anchor = "start"; fsize = 10; weight = "400"; fill = "#8a6a50"
            else:
                lx = x + r + 3; ly = y + 3
                anchor = "start"; fsize = 10; weight = "400"; fill = "#8090a8"

            svg.append(
                f'<text x="{lx:.0f}" y="{ly:.0f}" text-anchor="{anchor}" '
                f'font-family="sans-serif" font-size="{fsize}" font-weight="{weight}" '
                f'fill="{fill}" '
                f'style="paint-order:stroke; stroke:#fafcf7; stroke-width:3; pointer-events:none;">{label}</text>'
            )

        svg.append("</svg>")
        svg_string = "".join(svg)

        wrapped_html = f"""
        <div style="width:100%; height:100%; display:flex; align-items:flex-start; justify-content:center;">
            <div style="width:100%; max-width:1100px;">
                {svg_string}
            </div>
        </div>
        <style>
            svg {{ max-width:100%; height:auto; display:block; }}
        </style>
        <script>
        (function() {{
            const nodes = document.querySelectorAll('.node');
            const edges = document.querySelectorAll('.edge');
            function highlight(nodeId) {{
                edges.forEach(e => {{
                    const related = (e.dataset.src === nodeId || e.dataset.tgt === nodeId);
                    if (related) {{
                        e.setAttribute('stroke', '#ff8a3a');
                        e.setAttribute('stroke-width', '3');
                        e.setAttribute('stroke-opacity', '1');
                    }} else {{
                        e.setAttribute('stroke-opacity', '0.1');
                    }}
                }});
                nodes.forEach(n => {{
                    if (n.dataset.node !== nodeId) n.style.opacity = '0.35';
                }});
            }}
            function resetAll() {{
                edges.forEach(e => {{
                    e.setAttribute('stroke', '#c8d8c8');
                    e.setAttribute('stroke-width', '1');
                    e.setAttribute('stroke-opacity', '0.5');
                }});
                nodes.forEach(n => {{ n.style.opacity = '1'; }});
            }}
            nodes.forEach(node => {{
                node.addEventListener('mouseenter', () => highlight(node.dataset.node));
                node.addEventListener('mouseleave', resetAll);
            }});
        }})();
        </script>
        """
        # 縦横比に基づいた高さ(viewBoxとiframeを一致させる)
        components.html(wrapped_html, height=component_height)

        st.caption(
            "濃い緑=植えた植物 / 色付き大=来た鳥 / 淡色=未訪問の鳥や昆虫"
        )


# ---------- Tab: Community (みんなの庭 = 集合アトラス) ----------
# MVP公開版では非表示(企画部提案 2026-07-04・CEO承認)。community.py は削除せず残置。
# with tab_community:
#     community.render_community_atlas(default_biome=st.session_state.get("biome", "kyoto"))


# ---------- Tab: Help (使い方) ----------
with tab_help:
    st.markdown("## ❓ Toris Collection の使い方")

    st.markdown("### 基本のサイクル")
    st.markdown("""
    1. **土地(都市)を選ぶ**: 京都・シャーロットの2つから選びます。それぞれ気候と生息する鳥が違います。
    2. **植物を植える**: その土地に合う植物を選んで植えます。植物が昆虫を呼び、植物と昆虫が鳥を呼び寄せます。
    3. **しばらく待つ**: アプリを閉じている間にも、生態系は時間とともに動きます。次に開いたとき、新しい鳥が来ているかもしれません。
    4. **鳥を眺める・聴く**: フィールドに来た鳥たちのキャストを聴いたり、図鑑で詳細を確認したりできます。
       はじめて出会った鳥・久しぶりに来た鳥は、ポップアップでお知らせします。
    5. **落とし物を集める**: 鳥はときどき羽根や小枝などの宝物を残します。集めるごとに図鑑が充実します。
    6. **庭のラジオを聴く**: 図鑑に載った鳥たちが掛け合いで鳴くアンビエントラジオ。出会った鳥が多いほどキャストが豊かになります。季節は1週間ごとに巡り、渡り鳥はいない季節はラジオから消えます。
    """)

    st.markdown("### 鳥に出会えた時")
    st.markdown("""
    庭で鳥に出会う(留守のあいだに来ていた・「♪ 耳を澄ます」で近くまで来てくれた)と、
    ポップアップでお知らせします。

    - **はじめての種**: 「はじめまして! 新しく図鑑に登録されました」と表示され、図鑑にすぐ反映されます。
    - **すでに図鑑にいる種**: 「また会えました」と、再会をやわらかく伝えます。

    「♪ 耳を澄ます」で鳥に近づいているときは、しばらく待つと自動的に記録されます
    (止めるボタンを押さなくても大丈夫です)。
    """)

    st.markdown("### 出現確率の仕組み(図鑑の「なぜこの確率?」)")
    st.markdown("""
    各鳥の出現確率は、4つの係数の積で計算されます。

    ```
    確率 = 気温適合度 × バイオーム補正 × 食物係数 × レア度係数 × 0.5
    ```

    - **気温適合度 (temp_fit)**: 0〜1の値。その鳥の好む気温域の中心に近いほど1に近い、外れるほど0に近い。
    - **バイオーム補正 (biome_bonus)**: 1.0(好む土地) または 0.15(それ以外)。
    - **食物係数 (food_factor)**: 食物スコア(植物・昆虫からのエサ経路の合計重み)から計算。経路が太いほど高い。
    - **レア度係数 (rarity_factor)**: 1 - rarity*0.85 で、レアな種ほど1未満に下がる。生態ネットワーク上の重要度(補正済PageRank)を反映。
    - 末尾の **× 0.5** は、滞在2-4種に落ち着かせるための全体倍率。

    **食物経路** の表示は、その鳥が来る原因となった「植物 → 昆虫 → 鳥」または「植物 → 鳥」の経路と、各経路の重み(寄与度)です。
    """)

    st.markdown("### 不在中ループ")
    st.markdown("""
    アプリを閉じていた時間に応じて、自動で生態系が複数サイクル進化します。

    | 経過時間   | 進化サイクル数 |
    |-----------|--------------|
    | 5分未満    | 0            |
    | 5-30分     | 1            |
    | 30分-2時間 | 2            |
    | 2-6時間    | 3            |
    | 6-12時間   | 4            |
    | 12-24時間  | 5            |
    | 24時間以上 | 6 (上限)     |

    各サイクルでは滞在中の鳥について退去判定、その後新規到着判定(1サイクル最大1羽、滞在最大4羽)が走ります。
    """)

    st.markdown("### 落とし物のしくみ")
    st.markdown("""
    鳥が立ち寄ったとき、低確率で3カテゴリのいずれか1つを落とします。
    すべての鳥が同じ「小枝」「羽根」の2種類を持ち、一部の鳥だけが特別な「羽冠」も持ちます。

    | カテゴリ | 確率 | 内容 |
    |---------|-----|------|
    | 🌿 小枝   | 10% | その鳥が止まっていた小枝(一番出やすい) |
    | 🪶 羽根   | 5% | その鳥の羽根 |
    | ✨ 羽冠   | 4% | 一部の鳥だけが持つ冠羽(隠しレア・出会いのご褒美) |

    判定はレア順(羽冠→羽根→小枝)に行われ、最初に当選したカテゴリを返します(複数同時には出ない)。
    合わせて約16.5%、つまり訪問6回に1回くらい何か出ます。

    全コンプリートで **小枝26種 + 羽根26種 + 羽冠(一部の鳥のみ)** のコレクションになります。
    """)

    st.markdown("### 土地と気温(月による変化)")
    st.markdown("""
    気温は次の式で決まります。

    ```
    気温 = バイオームの平均気温 + 月ごとのオフセット
    ```

    月オフセット(北半球): 1月=-6、2月=-5、3月=-2、4月=+1、5月=+4、6月=+6、7月=+8、8月=+8、9月=+5、10月=+1、11月=-2、12月=-5

    現在の土地(京都・シャーロット)はどちらも北半球のため、このオフセットがそのまま使われます。

    月は現実時間と同期します(プレイヤーは時間を進める操作はできません)。
    """)

    st.markdown("### データの所在(この端末にのみ保存)")
    st.markdown("""
    進行データ(バイオーム・植えた植物・図鑑・会った日数・落とし物・メモなど)は、
    この端末のこのブラウザにのみ保存されます。サーバーには送られません。

    - **同じ端末・同じブラウザなら、開くだけで自動的に続きから始まります**
      (裏でセーブコードを自動保存しているため、毎回読み込み直す必要はありません)。
    - ブラウザのデータを消す・別の端末や別のブラウザで開く時は、記録は自動では
      引き継がれません。サイドバーの「💾 セーブコード(バックアップ)」から、
      いつでも進行データを1本のコードとして書き出せます。書き出したコードは、
      開始画面の「セーブコードを読み込んで再開」から読み込むと復元できます。
    - 「📋 セーブコードをコピー」ボタンを押すだけで、クリップボードに
      コピーされます(メモアプリなどに貼り付けて保管してください)。
      うまくいかない場合は、同じ場所にある「⬇️ セーブコードを書き出す」、
      「💾 セーブコードを共有」ボタン(共有シート経由)、
      コードを直接選択してコピーする欄もお使いいただけます。
    - セーブコードは手元で保管するものです(サーバーには送信されません)。
      失くすと復元できないので、大事な節目でときどき書き出しておくのがおすすめです。
    """)

    st.markdown("### 広告について(すべて任意)")
    st.markdown("""
    広告は庭の下部にある、完全に任意の応援広告だけです。

    - 鳥の声・ラジオ・図鑑は、広告を見ても見なくても、いつもどおり無料で楽しめます。
    - 「🎁 応援広告(庭に道具をひとつ)」を見ると、アメリカの裏庭バードウォッチング
      文化の道具(バードフィーダー・バードバス等、全6種)から**ランダムで1つ**、
      庭に6時間だけ置けます。1日1回だけの、完全に任意のおまけです。
    - 広告を見なくても、鳥の来やすさやコレクションの進み方は一切変わりません。
    """)

    st.caption(
        "クローズドテスト中のためフィードバックを歓迎しています。"
    )


# ============= Footer =============
st.markdown(
    "<br><hr><p style='text-align:center; color:#888; font-size:0.85em;'>"
    "#Toris Collection# · Small Start prototype · "
    "相互作用データは生態学的知見に基づくシード / 将来的にGloBI連携予定"
    "</p>",
    unsafe_allow_html=True
)
