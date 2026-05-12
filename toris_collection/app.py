"""
Toris Collection - Streamlit アプリ (v2)
変更点:
  - ネットワーク図を力学モデル(放射状)に変更 - ハブが見える
  - 資源ノードを除去 (GloBI互換)
  - 渡り鳥表示を廃止 (気温で自動表現)
  - 未訪問の鳥もネットワーク図に表示 (学習効果)
"""
import streamlit as st
import random
import math
from datetime import datetime, timedelta
from data import BIOMES, BIOME_MIGRATION, PLANTS, INSECTS, BIRDS, SEASON_TEMP_OFFSET
from engine import (
    build_network, calculate_arrival_probability, run_turn,
    current_temperature, force_directed_layout,
    suggest_for_bird, network_stats,
)
import absence_loop
import mementos as mem
from pathlib import Path
import base64


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
    path = SPRITES_DIR / f"{bird_id}.png"
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


# 植えてから効果が出るまでの時間 - 廃止(0時間=即効果)
# 当面は本数制限(BIOMES.max_plants)のみで植えすぎを防ぐ方針
PLANT_MATURATION_HOURS = 0


def _get_mature_plants(planted=None, planted_at_map=None):
    """24時間ペナルティを廃止したため、すべての植物を成熟扱いとする。
    関数自体は他箇所からの参照互換のため残す。
    """
    if planted is None:
        planted = st.session_state.get("planted", [])
    return list(planted)


def _get_immature_plants(planted=None, planted_at_map=None):
    """準備中の植物は常に空(ペナルティ廃止)"""
    return []

# Google Sheets バックエンド(クローズドテスト用)
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


def render_bird_audio(b_id: str, bird: dict):
    """
    鳥の鳴き声を再生するUIコンポーネント。
    初回クリックでダウンロード、2回目以降はキャッシュから即再生。
    エラー時は静かにフォールバック(アプリを落とさない)。
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
        if st.button("🔊 聴く", key=f"play_{b_id}"):
            st.session_state[key] = True

    if st.session_state.get(key):
        with st.spinner(f"{bird['name']}の鳴き声を取得中..."):
            audio_bytes, cit = _cached_audio_bytes(sci)

        if audio_bytes:
            try:
                # ループ再生で軽量化(短い音源を繰り返す)
                st.audio(audio_bytes, format="audio/mp3", loop=True)
                if cit:
                    st.caption(
                        f"出典: xeno-canto [XC{cit['xc_id']}]({cit['url']}) "
                        f"by {cit['recordist']} · {cit['country']} · CC"
                    )
            except Exception as e:
                st.caption(f"再生エラー: {e}")
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


def render_chorus_button(resident_ids):
    """
    ハーモニー: 滞在中の鳥の鳴き声を、自然な合唱として再生する。

    設計:
      - 60秒のタイムラインに各鳥をランダムに2〜4回スポット配置
      - 各スポットでは音源の一部だけを再生(currentTime で位置調整、3-6秒間)
      - 音量は全鳥均等(特定の鳥が目立たないように)
      - 60秒ごとに新しいパターンでループ
    """
    import base64
    import random

    if not resident_ids:
        return

    # 各鳥の音源を base64 で集める(キャッシュ版を使うので2回目以降は速い)
    with st.spinner("..."):
        audio_items = []
        for b_id in resident_ids:
            bird = BIRDS[b_id]
            sci = bird.get("scientific")
            if not sci:
                continue
            audio_bytes, _ = _cached_audio_bytes(sci)
            if audio_bytes:
                try:
                    data = base64.b64encode(audio_bytes).decode("ascii")
                    audio_items.append((bird["name"], data))
                except Exception:
                    pass

    if not audio_items:
        return

    n = len(audio_items)

    # 各鳥のスポット配置を組み立てる(60秒の周期内)
    # スポットを長め(8-15秒)・回数多め(3-5回)にして、自然な重なりを作る
    rng = random.Random(sum(hash(b) for b in resident_ids) % 10000)
    PERIOD_MS = 60000  # 60秒の周期
    FADE_IN_MS = 1500   # フェードイン 1.5秒
    FADE_OUT_MS = 2000  # フェードアウト 2秒

    spots_per_bird = []  # [[(start_ms, duration_ms), ...], ...]
    for i in range(n):
        # 鳥ごとのスポット数: 3-5回
        num_spots = rng.randint(3, 5)
        # 開始時刻は完全ランダムに分散(スロット制限を緩めて重なりやすく)
        spots = []
        for s in range(num_spots):
            start = rng.randint(0, PERIOD_MS - 10000)
            duration = rng.randint(8000, 15000)  # 8-15秒
            spots.append((start, duration))
        # 開始順にソート(視認性のため)
        spots.sort(key=lambda x: x[0])
        spots_per_bird.append(spots)

    # 全鳥の最大同時鳴き数を抑えるための調整は不要(60秒に分散しているため自然)

    bird_names_str = "、".join(name for name, _ in audio_items)
    audio_tags = []
    for i, (name, b64) in enumerate(audio_items):
        # loop は使わず、play/pause を JS で制御
        audio_tags.append(
            f'<audio id="chorus_audio_{i}" preload="auto" muted '
            f'data-name="{name}">'
            f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        )

    # JS 側に渡す JSON データ
    import json
    schedule_json = json.dumps({
        "period": PERIOD_MS,
        "spots": spots_per_bird,  # [[(start, dur), ...], ...]
    })

    html = f"""
    <div style="background:linear-gradient(180deg,#f7faf2 0%,#eef4e6 100%);
                padding:14px 18px; border-radius:10px;
                border-left:4px solid #7ba87b; margin-bottom:8px;">
        <div style="display:flex; align-items:center; gap:14px;">
            <button id="chorus_toggle"
                    style="background:#cfd9b8; color:#3a5a3a; border:none;
                           padding:10px 18px; border-radius:8px; cursor:pointer;
                           font-size:0.95em; font-weight:600; min-width:140px;">
                🔇 音を出す
            </button>
            <div style="flex-grow:1;">
                <div style="color:#5a7a5a; font-size:0.95em; font-weight:500;">
                    ♪ 鳥たちのコーラス ({n}羽)
                </div>
                <div style="color:#888; font-size:0.8em; margin-top:2px;">
                    {bird_names_str}
                </div>
            </div>
        </div>
        <div style="margin-top:8px; font-size:0.78em; color:#888;">
            60秒の周期で各鳥が交代に鳴きあいます。音量はスマホ・PC本体のボリュームで。
        </div>
    </div>
    {''.join(audio_tags)}
    <script>
    (function() {{
        const schedule = {schedule_json};
        const n = {n};
        const TARGET_VOLUME = 0.4;  // 全鳥均等の音量
        let muted = true;
        let cycleStartTime = Date.now();
        let activeTimers = [];

        function getAudio(i) {{
            return document.getElementById('chorus_audio_' + i);
        }}

        function playOneSpot(i, durationMs) {{
            const a = getAudio(i);
            if (!a || muted) return;
            try {{
                // 音源のランダムな位置から再生(0〜長さの 60% から開始)
                const totalDur = a.duration || 10;
                const startPos = Math.random() * Math.max(0.5, totalDur * 0.6);
                a.currentTime = startPos;
                a.volume = 0;  // 音量0から始めてフェードイン
                a.play().catch(function(e) {{}});

                // フェードイン: 0 → TARGET_VOLUME を 1.5秒かけて(60ステップ、25ms間隔)
                const fadeInSteps = 60;
                const fadeInInterval = 1500 / fadeInSteps;  // 25ms
                let fadeInStep = 0;
                const fadeInId = setInterval(function() {{
                    fadeInStep++;
                    a.volume = TARGET_VOLUME * (fadeInStep / fadeInSteps);
                    if (fadeInStep >= fadeInSteps) {{
                        a.volume = TARGET_VOLUME;
                        clearInterval(fadeInId);
                    }}
                }}, fadeInInterval);

                // フェードアウト: duration の最後 2秒をかけて 0 へ
                const fadeOutStart = Math.max(0, durationMs - 2000);
                setTimeout(function() {{
                    const fadeOutSteps = 80;
                    const fadeOutInterval = 2000 / fadeOutSteps;  // 25ms
                    let fadeOutStep = 0;
                    const startVol = a.volume;
                    const fadeOutId = setInterval(function() {{
                        fadeOutStep++;
                        a.volume = startVol * (1 - fadeOutStep / fadeOutSteps);
                        if (fadeOutStep >= fadeOutSteps) {{
                            a.volume = 0;
                            a.pause();
                            clearInterval(fadeOutId);
                        }}
                    }}, fadeOutInterval);
                }}, fadeOutStart);
            }} catch (e) {{}}
        }}

        function scheduleCycle() {{
            // 既存のタイマーをクリア
            activeTimers.forEach(function(t) {{ clearTimeout(t); }});
            activeTimers = [];

            // 各鳥のスポットをスケジュール
            for (let i = 0; i < n; i++) {{
                const spots = schedule.spots[i];
                for (let s = 0; s < spots.length; s++) {{
                    const startMs = spots[s][0];
                    const durationMs = spots[s][1];
                    const tid = setTimeout(function() {{
                        playOneSpot(i, durationMs);
                    }}, startMs);
                    activeTimers.push(tid);
                }}
            }}

            // 周期の最後に再スケジュール
            const cycleTid = setTimeout(scheduleCycle, schedule.period);
            activeTimers.push(cycleTid);
        }}

        function setMuted(state) {{
            muted = state;
            const btn = document.getElementById('chorus_toggle');
            if (state) {{
                // ミュート: 全停止
                for (let i = 0; i < n; i++) {{
                    const a = getAudio(i);
                    if (a) {{
                        a.pause();
                        a.muted = true;
                    }}
                }}
                activeTimers.forEach(function(t) {{ clearTimeout(t); }});
                activeTimers = [];
                btn.textContent = '🔇 音を出す';
                btn.style.background = '#cfd9b8';
            }} else {{
                // 再生開始
                for (let i = 0; i < n; i++) {{
                    const a = getAudio(i);
                    if (a) a.muted = false;
                }}
                cycleStartTime = Date.now();
                scheduleCycle();
                btn.textContent = '🔊 音を消す';
                btn.style.background = '#a8c890';
            }}
        }}

        const btn = document.getElementById('chorus_toggle');
        btn.addEventListener('click', function() {{
            setMuted(!muted);
        }});
    }})();
    </script>
    """

    import streamlit.components.v1 as components
    components.html(html, height=120)


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


# ============= State =============
def render_login_screen():
    """テスター選択画面。current_tester_id が未設定の時に表示する"""
    st.markdown("# 🐦 Toris Collection")
    st.markdown(
        "<p style='color:#5a7a5a;'>クローズドテスト版。テスター名を選んで開始してください。</p>",
        unsafe_allow_html=True
    )

    if not SHEETS_AVAILABLE:
        st.error(f"Google Sheets 連携が利用できません: {_sheets_error}")
        st.stop()

    try:
        testers = sc.list_testers()
    except Exception as e:
        st.error(f"スプレッドシート接続エラー: {e}")
        st.caption("credentials.json の配置と、サービスアカウントへの共有設定をご確認ください。")
        st.stop()

    if not testers:
        st.warning("テスターが登録されていません。スプレッドシートの testers シートを確認してください。")
        st.stop()

    name_map = dict(testers)
    options = [t[0] for t in testers]

    selected = st.selectbox(
        "テスター",
        options=options,
        format_func=lambda t: (
            f"{name_map[t]}" if name_map[t] != t else t
        ),
    )

    if st.button("▶ 開始", type="primary", use_container_width=True):
        st.session_state.current_tester_id = selected
        load_state_from_sheets(selected)
        sc.log_access(selected, "login", "enter")
        st.rerun()

    st.stop()


def load_state_from_sheets(tester_id):
    """選択されたテスターの状態を Sheets から読み込み、
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
        st.session_state.planted = [pid for pid, _ in valid_planted]
        # plant_id -> 最初に植えた日時(同じ植物を複数回植えた場合は最古を採用)
        planted_at_map = {}
        for pid, ts in valid_planted:
            if pid not in planted_at_map and ts:
                planted_at_map[pid] = ts
        st.session_state.planted_at_map = planted_at_map
        # 不整合があれば Sheets 側もクリーンアップ
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
    # 前回アクセス時刻 → 現在時刻 で生態系を時間進化させる
    # 24時間以上前に植えた植物のみ確率計算に使う(準備中の植物は影響を持たない)
    _mature_for_evo = _get_mature_plants()
    if fs and _mature_for_evo:
        last_at = absence_loop.parse_iso(fs.get("last_access_at"))
        if last_at:
            try:
                evo = absence_loop.evolve_state(
                    _mature_for_evo,
                    st.session_state.biome,
                    st.session_state.month,
                    last_at,
                    now,
                    st.session_state.residents,
                    st.session_state.rng,
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

            # 各イベントを Sheets に記録
            new_mementos = []
            for ev in evo["events"]:
                try:
                    sc.add_visit(
                        tester_id, ev["bird_id"], "absence",
                        reason_text=ev["reason_text"],
                        related_plant_id=ev["related_plant_id"],
                        related_insect_id=ev["related_insect_id"],
                        arrived_at=ev["arrived_at"],
                    )
                    sc.upsert_collection(tester_id, ev["bird_id"])
                    st.session_state.discovered.add(ev["bird_id"])

                    # 落とし物の記録
                    mid = ev.get("memento_id")
                    if mid:
                        kind = mem.memento_category(mid)
                        target = mem.memento_target(mid) if ":" in mid else mid
                        sc.add_memento(
                            tester_id, mid, kind, target,
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

            # 進化が起きていれば field_state を現在時刻で更新
            if evo["n_ticks"] > 0:
                try:
                    sc.save_field_state(
                        tester_id, st.session_state.biome,
                        current_temperature(st.session_state.biome,
                                            st.session_state.month),
                        f"month_{st.session_state.month}",
                        list(st.session_state.residents),
                    )
                except Exception:
                    pass


def init_state():
    if st.session_state.get("current_tester_id") is None:
        render_login_screen()
        return  # render_login_screen が st.stop() を呼ぶので到達しない
    if "initialized" not in st.session_state:
        load_state_from_sheets(st.session_state.current_tester_id)


def _sheets_safe(fn, *args, **kwargs):
    """書き戻しの共通ラッパ。失敗してもアプリは止めず、警告だけ出す"""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        st.warning(f"Sheets同期に失敗(処理は続行されます): {e}", icon="⚠️")

init_state()


# ============= Header =============
st.markdown("# 🐦 #Toris Collection#")
st.markdown(
    "<p style='color:#5a7a5a; font-size:1.05em;'>"
    "土地を選び、植物を植え、時間が経つのを待つ。やってきた鳥たちの声に耳を澄まそう。</p>",
    unsafe_allow_html=True
)


# ============= Sidebar =============
with st.sidebar:
    # 現在のテスター情報(クローズドテスト用)
    tid = st.session_state.get("current_tester_id", "(未選択)")
    st.markdown(f"<div style='font-size:0.85em; color:#888;'>👤 {tid}</div>",
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
    # データソース状況
    try:
        from engine import _try_load_centralities
        cents = _try_load_centralities()
        if cents:
            st.caption(f"🔬 Sony CSL中心性: {len(cents)}種で有効")
        else:
            st.caption("🔬 Sony CSL中心性: シードrarityのみ使用")
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
            sc.log_access(tid, "home", "leave_field")
        st.rerun()

    if st.button("👤 ログアウト", use_container_width=True):
        tid = st.session_state.get("current_tester_id")
        if tid:
            sc.log_access(tid, "login", "leave")
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
                )
                # 結果を反映(本番の不在中ループと同じ処理)
                st.session_state.residents = evo["residents"]
                st.session_state.absence_events = evo["events"]
                st.session_state.last_arrivals_info = {
                    ev["bird_id"]: ev["reason_text"] for ev in evo["events"]
                }
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
                sc.log_access(tid, "test", "sim_evolved",
                              f"{sim_hours}h,events={len(evo['events'])},"
                              f"new_mementos={len(new_mementos)}")
                st.rerun()

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


# ============= Tabs =============
tab_home, tab_plant, tab_sim, tab_birds, tab_mementos, tab_network, tab_help = st.tabs(
    ["🏞️ 今の様子", "🌱 植える", "🧪 シミュ", "📖 図鑑", "🎁 落とし物",
     "🕸️ ネットワーク", "❓ 使い方"]
)


# ---------- Tab: Home ----------
with tab_home:
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

    # フィールドの様子(全幅で表示)
    st.markdown("### 🌳 フィールドの様子")
    render_field_view(
        st.session_state.planted,
        st.session_state.residents,
        st.session_state.month,
        current_temperature(st.session_state.biome, st.session_state.month),
    )
    st.markdown("---")

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
                st.session_state.last_arrivals_info = {}
                tid = st.session_state.current_tester_id
                _sheets_safe(sc.remove_all_plantings, tid)
                _sheets_safe(
                    sc.save_field_state, tid, new_biome,
                    current_temperature(new_biome, st.session_state.month),
                    f"month_{st.session_state.month}", []
                )
                sc.log_access(tid, "home", "biome_changed", new_biome)
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

            # ハーモニー: ミュート自動再生(画面を開いた瞬間から鳥が鳴いている)
            if XC_AVAILABLE:
                render_chorus_button(st.session_state.residents)

            st.markdown("")

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
                # 鳴き声の再生
                render_bird_audio(b_id, bird)


# ---------- Tab: Plant ----------
with tab_plant:
    st.markdown("### 🌱 植物を植える")
    st.markdown("植物が他の生き物(昆虫・鳥)と**どう相互作用するか**が、やってくる鳥を決めます。")

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
                sc.log_access(tid, "plant", "plant_added", pid)
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
        for pid in st.session_state.planted:
            if pid not in PLANTS:
                continue
            pl = PLANTS[pid]
            ts_str = st.session_state.planted_at_map.get(pid, "")

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
                if st.button("🗑️", key=f"remove_{pid}_{ts_str}",
                             help=f"{pl['name']}を抜く",
                             use_container_width=True):
                    # session_state から1本除去
                    st.session_state.planted.remove(pid)
                    if pid not in st.session_state.planted:
                        st.session_state.planted_at_map.pop(pid, None)
                    tid = st.session_state.current_tester_id
                    _sheets_safe(sc.remove_planting, tid, pid)
                    sc.log_access(tid, "plant", "plant_removed", pid)
                    st.rerun()

        st.markdown("")
        if st.button("🗑️ 全部抜く"):
            st.session_state.planted = []
            st.session_state.planted_at_map = {}
            st.session_state.residents = set()
            tid = st.session_state.current_tester_id
            _sheets_safe(sc.remove_all_plantings, tid)
            sc.log_access(tid, "plant", "plant_removed_all")
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

    for b_id, bird in sorted_birds:
        discovered = b_id in st.session_state.discovered
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

        with st.expander(
            f"{'🐦' if discovered else '❓'} "
            f"{bird['name'] if discovered else '???'} "
            f"(レア度 {'★' * (1 + int(bird['rarity'] * 5))})",
            expanded=False,
        ):
            if discovered:
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
                st.write(bird["description"])

                # 外部リンク: 名前で Google / Wikipedia を検索
                import urllib.parse as _urlparse
                _q_jp = _urlparse.quote(bird['name'])
                _q_sci = _urlparse.quote(bird['scientific'])
                _links_html = (
                    f"<div style='margin:6px 0 14px 0;'>"
                    f"<a href='https://www.google.com/search?q={_q_jp}+{_q_sci}' "
                    f"target='_blank' rel='noopener' "
                    f"style='display:inline-block; margin-right:8px; padding:4px 10px; "
                    f"background:#f0f4ec; border-radius:12px; "
                    f"text-decoration:none; color:#3a5a3a; font-size:0.85em;'>"
                    f"🔍 Google で検索</a>"
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
                            f"(Sony CSL補正値を使用)"
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
                # この鳥の落とし物候補(全鳥共通の5カテゴリ)
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
                from data import BIRDS as _BIRDS
                color = _BIRDS.get(n, {}).get("color", "#2a5aa8")
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

        # components.html で固定高さの iframe に埋め込み、SVG はその中で
        # max-height で収まるようにする。これで確実に画面内に収まる。
        import streamlit.components.v1 as components

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
        components.html(wrapped_html, height=component_height, scrolling=False)

        st.caption(
            "濃い緑=植えた植物 / 色付き大=来た鳥 / 淡色=未訪問の鳥や昆虫"
        )


# ---------- Tab: Help (使い方) ----------
with tab_help:
    st.markdown("## ❓ Toris Collection の使い方")

    st.markdown("### 基本のサイクル")
    st.markdown("""
    1. **土地(都市)を選ぶ**: 京都・シドニー・シャーロットの3つから選びます。それぞれ気候と生息する鳥が違います。
    2. **植物を植える**: その土地に合う植物を選んで植えます。植物が昆虫を呼び、植物と昆虫が鳥を呼び寄せます。
    3. **しばらく待つ**: アプリを閉じている間にも、生態系は時間とともに動きます。次に開いたとき、新しい鳥が来ているかもしれません。
    4. **鳥を眺める・聴く**: フィールドに来た鳥たちのコーラスを聴いたり、図鑑で詳細を確認したりできます。
    5. **落とし物を集める**: 鳥はときどき羽根や種などの宝物を残します。集めるごとに図鑑が充実します。
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
    - **レア度係数 (rarity_factor)**: 1 - rarity*0.85 で、レアな種ほど1未満に下がる。Sony CSL補正済PageRankを反映。
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
    鳥が立ち寄ったとき、低確率で5カテゴリのいずれか1つを落とします。
    すべての鳥が同じ5カテゴリ・5種類の落とし物を持ちます(各カテゴリは鳥種ごとに固有)。

    | カテゴリ | 確率 | 内容 |
    |---------|-----|------|
    | 🪶 羽根   | 5% | その鳥の羽根 |
    | 🌱 種     | 5% | その鳥が体に付けて運んできた種 |
    | 🌿 小枝   | 7% | その鳥が止まっていた小枝(やや出やすい) |
    | 🌰 木の実 | 4% | その鳥が嘴で運んだ木の実 |
    | ✨ 羽冠   | 2% | その鳥の冠羽(超レア・最終目標) |

    判定はレア順に行われ、最初に当選したカテゴリを返します(複数同時には出ない)。
    全カテゴリ合わせて約23%、つまり訪問4回に1回くらい何か出ます。

    全コンプリートで **5 × 26 = 130種** のコレクションになります。
    """)

    st.markdown("### 土地と気温(月による変化)")
    st.markdown("""
    気温は次の式で決まります。

    ```
    気温 = バイオームの平均気温 + 月ごとのオフセット
    ```

    月オフセット(北半球): 1月=-6、2月=-5、3月=-2、4月=+1、5月=+4、6月=+6、7月=+8、8月=+8、9月=+5、10月=+1、11月=-2、12月=-5

    **南半球(シドニー)** はオフセットが6ヶ月反転します。
    つまり北半球の5月(+4)が、シドニーでは11月(-2)相当になります。

    月は現実時間と同期します(プレイヤーは時間を進める操作はできません)。
    """)

    st.markdown("### データの所在(Google Sheets)")
    st.markdown("""
    すべての記録は Google Sheets に保存されます。
    - `field_state`: 各テスターの現在のバイオーム・滞在中の鳥・最終アクセス時刻
    - `plantings`: 植えた植物の履歴
    - `bird_visits`: 鳥の訪問記録(滞在中・不在中)とその「なぜ来たか」
    - `collection`: 図鑑(各鳥の初回観測・最終観測・累計訪問回数)
    - `mementos`: 落とし物の獲得履歴
    - `bird_notes`: 各鳥への発見地メモ・自由メモ
    - `access_logs`: 画面遷移と操作の行動ログ
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
