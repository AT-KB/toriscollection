"""
ritual.py - 鳥たちのキャスト UI (ステップ5a+5b)

これまでの積み上げ:
  - ステップ3: 「♪ 耳を澄ます」で音を鳴らす(自動再生制限の突破)
  - ステップ4: 最大4羽を同時再生し、距離で音量・ローパス・エコーを変化
  - ステップ5a: 各鳥のドット絵スプライトを距離に応じて表示
  - ステップ5b: 儀式終了時に近距離観察を Sheets に保存
  - 改善第一弾: 近距離を驚くほどクリアに(gain増+コンプレッサー+エコー0)、
    遠近の対比を強化。
  - 改善第二弾: 奥から手前に4本の枝(SVG)が並び、鳥が枝を行き来する。
    手前の枝(b1)に来た瞬間に観察記録。飛び立ちはどの枝からでも起こりうる。
    隣の枝への往復ホップで「ぴょんぴょん」感を表現。
  - 2026-07-11追記(P1修正): 儀式で会った鳥が図鑑に反映されないことがある
    という不具合の根本原因対応。`saveObservations()` は以前、出会いの
    確定イベントの「その場」で window.top.document への <script> 要素注入に
    よりトップウィンドウを直接ナビゲーションしていたが、ads.py の広告結果
    伝達で判明したのと同じ理由(ads.py モジュールdocstring
    「2026-07-10 追記(P1修正)」参照)で不安定だった。ナビゲーションは行わず
    window.top.localStorage への同期的な書き込みだけに留め、実際に
    Python 側へ届けるナビゲーションは app.py の
    `_inject_ritual_result_check()`(毎回のrerunで動き続ける独立したポーリング、
    `_inject_ad_result_check()` と同じパターン)に委譲するよう変更した。

このファイルで使っている技術:
  - Web Audio API(音量・フィルター・エコーの距離変化)
  - components.v1.html(html, ...)(streamlit.components.v1 をモジュールとして import して
    呼ぶ経路)でHTML文字列をiframeに埋め込む。`st.iframe()` という同名APIは存在しない
    (2026-07-04 バグ修正: 以前ここに書かれていた「st.iframe へ移行済み」は事実誤認だった。
    非推奨/削除予定なのは `st.components.v1.html` という直接属性アクセスの経路のみで、
    `import streamlit.components.v1 as components; components.html(...)` は現役でサポートされる)
  - lazy loading(音源取得は「耳を澄ます」ボタン押下後にのみ実行、ホームタブを即時表示)
  - window.top.localStorage への書き込み(観察記録)を、app.py 側の独立した
    ポーリング(`_inject_ritual_result_check()`)が top window クエリパラメータ
    経由の片道リロードとして Python に渡す(ads.py と同じパターン)

設計原則(仕様§3-3):
  - 距離レベルの数値・メーター・進捗バーは出さない。変化は音と絵で伝える。
  - 「逃げた」は罰ではなく自然現象。安全モードは作らない。
"""
from __future__ import annotations
import json
import base64
import concurrent.futures
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from species_loader import PLANTS as _PLANTS
import audio_engine as ae

try:
    import xc_client
except (KeyError, AttributeError):
    # Python 3.14 の並行インポートバグへの保険
    import importlib
    xc_client = importlib.import_module("xc_client")

try:
    import freesound_client
except Exception:
    freesound_client = None  # type: ignore


_COMPONENT_HEIGHT = 390
_MAX_BIRDS = 4
_SPRITE_DIR = Path(__file__).parent / "designbird"


@st.cache_data(show_spinner=False)
def _get_audio_b64(scientific_name: str) -> str | None:
    """鳴き声mp3をbase64文字列で返す。ダウンロード済みならキャッシュから即返す。"""
    path = xc_client.download_audio(scientific_name)
    if path and path.exists():
        return base64.b64encode(path.read_bytes()).decode("ascii")
    return None


@st.cache_data(show_spinner=False)
def _get_sprite_b64(bird_id: str) -> str | None:
    """ドット絵スプライト(png)をbase64で返す。なければ None(色丸で代替)。

    新種は SPRITE_ALIASES で既存のドット絵を流用する(app.py/radio.py と同じ解決順)。
    """
    from data import SPRITE_ALIASES
    sprite_id = SPRITE_ALIASES.get(bird_id, bird_id)
    p = _SPRITE_DIR / f"{sprite_id}.png"
    if p.exists():
        try:
            return base64.b64encode(p.read_bytes()).decode("ascii")
        except Exception:
            return None
    return None


def _hex_to_color_label(hex_color: str) -> str:
    """HEX → 日本語色ラベル(例: '#3a7ac8' → '青い')"""
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    except Exception:
        return "小さな"
    mx, mn = max(r, g, b), min(r, g, b)
    lum = (mx + mn) / 2
    if mx - mn < 0.12:                  # 無彩色
        return "白い" if lum > 0.72 else ("灰色の" if lum > 0.42 else "黒い")
    hue = 0.0
    if mx == r:   hue = ((g - b) / (mx - mn)) % 6
    elif mx == g: hue = (b - r) / (mx - mn) + 2
    else:         hue = (r - g) / (mx - mn) + 4
    hue *= 60
    if lum < 0.22:          return "黒い"
    if hue < 22 or hue >= 338: return "赤い"
    if hue < 42:            return "橙色の"
    if hue < 72:            return "黄色い"
    if hue < 162:           return "緑の"
    if hue < 202:           return "青緑の"
    if hue < 252:           return "青い"
    if hue < 292:           return "紫の"
    return "ピンクの"


def _bird_hint(bird_id: str, bird: dict, biome_id: str) -> str:
    """「サクラにとまっていた赤い鳥」形式のヒント文を生成(bird_id で決定的に固定)。"""
    col = _hex_to_color_label(bird.get("color", "#888"))
    plants = [p for p in bird.get("eats_plants", []) if p in _PLANTS]
    if plants:
        idx = hash(bird_id + biome_id) % len(plants)
        plant_name = _PLANTS[plants[idx]]["name"]
        return f"{plant_name}にとまっていた{col}鳥"
    return f"{col}鳥"


@st.cache_data(show_spinner=False)
def _get_audio_b64_variants(scientific_name: str,
                            max_n: int = 3) -> list[tuple[str, str]]:
    """同一種の複数録音を (base64, 鳴き方) のリストで返す。
    鳴き方は "song"(さえずり) / "call"(地鳴き)。
    iframe のHTML肥大を防ぐため、1種あたりの合計サイズに上限を設ける(軽さ優先)。
    """
    paths = xc_client.download_audio_variants(scientific_name, max_n=max_n)
    out: list[tuple[str, str]] = []
    total = 0
    _BUDGET = 2_000_000  # base64文字数(≒1.5MBバイナリ)/種
    for p, sound_type in paths:
        if not (p and p.exists()):
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        if out and total + len(b64) > _BUDGET:
            continue  # 1件目は必ず入れる、以降は予算内のもののみ追加
        out.append((b64, sound_type))
        total += len(b64)
    return out


@st.cache_data(show_spinner=False)
def _get_ambient_b64() -> str | None:
    """Freesound から取得した森の環境音を base64 で返す。キーなしは None。"""
    if freesound_client is None or not freesound_client.is_enabled():
        return None
    path = freesound_client.get_ambient_path()
    if path and path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return b64
    return None


def _fetch_bird_audio(args: tuple) -> tuple:
    """(bid, bird_dict) → (bid, b64リスト or None)  並列実行用"""
    bid, bird = args
    sci = bird.get("scientific", "")
    if not sci:
        return bid, None
    return bid, _get_audio_b64_variants(sci) or None


def render_ritual(resident_ids, biome_id: str, birds_data: dict):
    """
    鳥たちのキャストUI(4本枝・ホップメカニクス)をホームタブに描画する。

    ロード戦略(遅延読み込み):
      - 初回: 軽量な招待ボタンだけ表示(xeno-canto アクセスなし → ホームタブ即時表示)
      - ボタン押下後のみ音源を取得してフル儀式UIを描画
      - 2回目以降: @st.cache_data でキャッシュ済み → 即時表示
    """
    if not resident_ids:
        return
    if not xc_client.is_enabled():
        return

    # 2026-07-12追記(CEO指示): 直前の儀式と滞在メンバーが1羽も変わっていなければ、
    # 再度「耳を澄ます」を差し出さない(次に鳥が入れ替わるまで待ってもらう)。
    # 図鑑・観察カウントは既に確定済みでここでは一切触らない(交渉不能の原則2:
    # 罰しない。減るものは無い)。あくまで「もう一度同じ相手に儀式をやり直せて
    # しまう」入り口だけを閉じる(app.py `_handle_ritual_observation()` 参照)。
    _done_for = st.session_state.get("ritual_done_for_residents")
    if _done_for is not None and _done_for == frozenset(resident_ids):
        st.markdown(
            """<div style="background:linear-gradient(180deg,#f7faf2,#eef4e6);
            padding:14px 20px;border-radius:12px;border-left:4px solid #b7c7a3;
            margin-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <div style="color:#6b7a63;font-size:0.95em;">
                🌙 今日はもう十分に耳を澄ませました。新しい鳥が来たら、また会いに行けます。</div>
            </div>""",
            unsafe_allow_html=True,
        )
        return

    # ── フェーズ1: 招待ボタン(音源未取得・軽量) ────────────────────────────────
    if not st.session_state.get("ritual_ready"):
        n = min(len(resident_ids), _MAX_BIRDS)
        st.markdown(
            f"""<div style="background:linear-gradient(180deg,#f7faf2,#eef4e6);
            padding:14px 20px;border-radius:12px;border-left:4px solid #7ba87b;
            margin-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <div style="color:#5a7a5a;font-size:0.95em;font-weight:500;">
                ♪ 鳥に会いに行く ({n}羽)</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button("♪ 耳を澄ます", key="ritual_init_btn"):
            st.session_state.ritual_ready = True
            st.rerun()
        return

    # ── フェーズ2: 音源取得(初回のみネットワーク、以後キャッシュ) ──────────────
    candidates = [
        (bid, birds_data[bid])
        for bid in resident_ids
        if bid in birds_data and birds_data[bid].get("scientific")
    ][:_MAX_BIRDS * 2]

    birds = []
    with st.spinner("鳥の声を呼び込んでいます…"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_BIRDS) as ex:
            futures = {ex.submit(_fetch_bird_audio, c): c[0] for c in candidates}
            for future in concurrent.futures.as_completed(futures):
                bid, b64s = future.result()
                if b64s and len(birds) < _MAX_BIRDS:
                    bird = birds_data[bid]
                    birds.append({
                        "id":       bid,
                        "name":     bird.get("name", bid),
                        "hint":     _bird_hint(bid, bird, biome_id),
                        "color":    bird.get("color", "#888"),
                        "wariness": float(bird.get("wariness", 0.5)),
                        "b64s":     b64s,
                        "sprite":   _get_sprite_b64(bid),
                    })

    if not birds:
        if xc_client.COMMERCIAL_ONLY and any(
            xc_client.is_nc_only(b.get("scientific", "")) for _, b in candidates
        ):
            st.info(
                "🔒 ここにいる鳥の声はNC(非商用)音源のため、録音準備中です。"
                "図鑑や庭での観察はこれまでどおり楽しめます。"
            )
        st.session_state.ritual_ready = False
        return

    id_order = {bid: i for i, bid in enumerate(resident_ids)}
    birds.sort(key=lambda b: id_order.get(b["id"], 999))

    # 森の環境音(Freesound): キーがあれば実録音、なければ JS でシンセ合成
    ambient_b64 = _get_ambient_b64()

    n = len(birds)
    birds_meta = [
        {"id": b["id"], "name": b["name"], "hint": b["hint"],
         "wariness": b["wariness"], "nv": len(b["b64s"]),
         "vt": [t for _, t in b["b64s"]]}   # 各バリエーションの鳴き方(song/call)
        for b in birds
    ]
    birds_json = json.dumps(birds_meta, ensure_ascii=False)

    # 森の環境音タグ(Freesound がある場合のみ)
    ambient_tag = ""
    if ambient_b64:
        ambient_tag = (
            '<audio id="rite_ambient" preload="auto" loop style="display:none">'
            f'<source src="data:audio/mp3;base64,{ambient_b64}" type="audio/mp3"></audio>'
        )

    # 鳴き声バリエーション: 1羽につき複数の録音(さえずり/地鳴き)を埋め込む。
    # id は rite_audio_{鳥index}_{バリエーションindex}
    audio_tags = "".join(
        f'<audio id="rite_audio_{i}_{v}" preload="auto" loop style="display:none">'
        f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        for i, b in enumerate(birds)
        for v, (b64, _t) in enumerate(b["b64s"])
    )

    # 木のレイアウト:
    #   幹が地面から生えていて、その幹から水平枝(鳥が止まる場所)が出ている構造。
    #   幹の上には丸い葉の塊(キャノピー)。奥→手前で遠近感を付ける。
    # (branch_top%, half_width%, trunk_w_px, branch_h_px, canopy_dia_px, opacity, z)
    _TREE_SPECS = [
        (37, 27, 16,  6,  74, 0.70, 20),  # b3: 奥
        (54, 35, 22,  9,  98, 0.86, 30),  # b2
        (70, 43, 30, 13, 126, 1.00, 40),  # b1: 手前
    ]
    _GAP_HALF = 5.0  # 枝中央の切れ目: 50% を中心に左右 _GAP_HALF% を空ける
    _TRUNK_GRAD = (
        "linear-gradient(to right,"
        "#3d1f08 0%,#6b3a18 22%,#915a30 48%,#5a2e10 76%,#2a1205 100%)"
    )
    _CANOPY_GRAD = (
        "radial-gradient(ellipse at 38% 32%,"
        "#a8e060 0%,#62b828 38%,#2d8010 72%,#1a5006 100%)"
    )
    _SCENE_H = 195  # scene の実 px 高さ(CSS overflow:hidden で隠れる部分込み)
    scene_parts = []
    for (tp, half, tw, bh, cd, op, z) in _TREE_SPECS:
        lx = 50 - half       # 左の幹の中心 %
        rx = 50 + half       # 右の幹の中心 %
        th = 116 - tp        # 幹の高さ %(地面まで)
        bw = 2 * half        # 水平枝の幅 %
        rad = max(2, tw // 3)
        tp_px = tp / 100 * _SCENE_H
        # キャノピーの天頂: 枝バーより cd*0.75px 上(上端より外にはみ出してもOK)
        ctop_px = tp_px - cd * 0.82
        ctop_pct = ctop_px / _SCENE_H * 100
        half_cd = cd // 2

        # ① キャノピー(z = branch-1 で枝の奥に重なる)
        for cx in (lx, rx):
            scene_parts.append(
                f'<div style="position:absolute;top:{ctop_pct:.1f}%;'
                f'left:calc({cx:.1f}% - {half_cd}px);'
                f'width:{cd}px;height:{cd}px;'
                f'background:{_CANOPY_GRAD};border-radius:50%;'
                f'opacity:{op:.2f};z-index:{z - 1};pointer-events:none;'
                f'box-shadow:inset -4px -6px 12px rgba(0,50,0,0.32),'
                f'0 3px 6px rgba(0,40,0,0.15);"></div>'
            )
        # ② 水平枝バー(中央に切れ目を入れて左右の木を分離)
        # 左枝: lx〜(50-_GAP_HALF)、右枝: (50+_GAP_HALF)〜rx
        bar_style = (
            f'height:{bh}px;background:linear-gradient(180deg,#7a5830,#3a2410);'
            f'border-radius:{bh}px;opacity:{op:.2f};z-index:{z};pointer-events:none;'
            f'box-shadow:0 2px 4px rgba(35,22,8,0.35);'
        )
        left_w = (50 - _GAP_HALF) - lx
        right_w = rx - (50 + _GAP_HALF)
        scene_parts.append(
            f'<div style="position:absolute;top:{tp}%;left:{lx:.1f}%;'
            f'width:{left_w:.1f}%;{bar_style}"></div>'
        )
        scene_parts.append(
            f'<div style="position:absolute;top:{tp}%;left:{50 + _GAP_HALF:.1f}%;'
            f'width:{right_w:.1f}%;{bar_style}"></div>'
        )
        # ③ 左右の幹(地面まで、キャノピーの上から出て枝バーを貫く)
        for cx in (lx, rx):
            scene_parts.append(
                f'<div style="position:absolute;top:{tp}%;left:{cx:.1f}%;width:{tw}px;'
                f'height:{th}%;transform:translateX(-50%);background:{_TRUNK_GRAD};'
                f'border-radius:{rad}px {rad}px 2px 2px;opacity:{op:.2f};z-index:{z};'
                f'pointer-events:none;box-shadow:inset 0 0 7px rgba(15,8,2,0.55),'
                f'2px 0 6px rgba(10,5,0,0.2);"></div>'
            )
    branch_html = "".join(scene_parts)

    # スプライト: 最初は b3(新たな最奥)にとまった状態。
    # b3 のレーン [26, 74] から中央のギャップ [45, 55] を除いた範囲に等間隔配置。
    sprite_divs = []
    _SPAWN_LMIN, _SPAWN_LMAX = 26.0, 74.0
    _SPAWN_MID = (_SPAWN_LMIN + _SPAWN_LMAX) / 2
    _SPAWN_LEFT_W = (_SPAWN_MID - _GAP_HALF) - _SPAWN_LMIN
    _SPAWN_RIGHT_W = _SPAWN_LMAX - (_SPAWN_MID + _GAP_HALF)
    _SPAWN_COMBINED = _SPAWN_LEFT_W + _SPAWN_RIGHT_W
    for i, b in enumerate(birds):
        v = (i + 0.5) / n * _SPAWN_COMBINED
        if v < _SPAWN_LEFT_W:
            lp = _SPAWN_LMIN + v
        else:
            lp = _SPAWN_MID + _GAP_HALF + (v - _SPAWN_LEFT_W)
        bob = 3.0 + i * 0.4
        idle = 8.5 + i * 1.3
        anim = (
            f'animation:rite_bob {bob:.1f}s ease-in-out infinite,'
            f'rite_idle {idle:.1f}s ease-in-out infinite -{i * 0.7:.1f}s;'
        )
        if b["sprite"]:
            inner = (
                f'<img src="data:image/png;base64,{b["sprite"]}" '
                f'style="width:60px;height:60px;image-rendering:pixelated;{anim}">'
            )
        else:
            inner = (
                f'<div style="width:46px;height:46px;border-radius:50%;'
                f'background:{b["color"]};{anim}"></div>'
            )
        sprite_divs.append(
            f'<div class="rite_bird" id="rite_bird_{i}" '
            f'style="position:absolute;left:{lp:.1f}%;top:11%;'
            f'transform:translate(-50%,0) scale(0.70);opacity:0.72;z-index:22;'
            f'transition:top 0.75s cubic-bezier(.36,.07,.19,.97),'
            f'left 0.75s ease,transform 0.75s cubic-bezier(.36,.07,.19,.97),'
            f'opacity 0.75s ease;">'
            f'{inner}</div>'
        )
    # 雲: 木より奥(z=2)をゆっくり横切る。負のdelayで初期位置を散らす。
    # (top%, width_px, height_px, dur_s, delay_s, opacity)
    _CLOUDS = [
        (8,  64, 20, 38, 4,  0.72),
        (18, 92, 26, 54, 24, 0.55),
        (5,  46, 15, 31, 14, 0.62),
    ]
    cloud_parts = []
    for (tp, w, h, dur, delay, op) in _CLOUDS:
        cloud_parts.append(
            f'<div style="position:absolute;top:{tp}%;left:0;width:{w}px;height:{h}px;'
            f'background:rgba(255,255,255,{op});border-radius:{h}px;filter:blur(2px);'
            f'z-index:2;pointer-events:none;'
            f'box-shadow:{w * 0.28:.0f}px {h * 0.18:.0f}px 0 -2px rgba(255,255,255,{op}),'
            f'{w * 0.55:.0f}px -{h * 0.10:.0f}px 0 -4px rgba(255,255,255,{op});'
            f'animation:rite_cloud {dur}s linear infinite;animation-delay:-{delay}s;"></div>'
        )
    cloud_html = "".join(cloud_parts)
    scene_html = cloud_html + branch_html + "".join(sprite_divs)

    has_ambient_js = "true" if ambient_b64 else "false"

    html = f"""
    {ambient_tag}
    {audio_tags}
    <style>
      @keyframes rite_bob {{
        0%, 100% {{ margin-top: 0px; }}
        50%      {{ margin-top: -5px; }}
      }}
      /* 待機モーション: 時々首をかしげ、時々羽繕い(膨らむ)。大半は静止。 */
      @keyframes rite_idle {{
        0%   {{ transform: rotate(0deg)  scale(1, 1); }}
        46%  {{ transform: rotate(0deg)  scale(1, 1); }}
        50%  {{ transform: rotate(7deg)  scale(1, 1); }}
        57%  {{ transform: rotate(7deg)  scale(1, 1); }}
        62%  {{ transform: rotate(0deg)  scale(1, 1); }}
        72%  {{ transform: rotate(0deg)  scale(1, 1); }}
        75%  {{ transform: rotate(0deg)  scale(1.14, 0.9); }}
        79%  {{ transform: rotate(0deg)  scale(1.14, 0.9); }}
        83%  {{ transform: rotate(0deg)  scale(1, 1); }}
        100% {{ transform: rotate(0deg)  scale(1, 1); }}
      }}
      /* 雲が画面を横切る(GPU加速の translateX、再描画なし) */
      @keyframes rite_cloud {{
        from {{ transform: translateX(-170px); }}
        to   {{ transform: translateX(calc(100vw + 90px)); }}
      }}
      /* 出会い行のフェードイン */
      @keyframes rite_met_in {{
        from {{ opacity: 0; transform: translateY(5px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
      }}
      .rite_bird > * {{ transform-origin: 50% 90%; }}
    </style>
    <div style="
        background: linear-gradient(180deg, #f7faf2 0%, #eef4e6 100%);
        padding: 16px 20px; border-radius: 12px; border-left: 4px solid #7ba87b;
        margin-bottom: 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
        <div style="display: flex; align-items: center; gap: 14px;">
            <button id="rite_btn" style="
                background: #cfd9b8; color: #3a5a3a; border: none;
                padding: 12px 22px; border-radius: 8px; cursor: pointer;
                font-size: 1em; font-weight: 600; min-width: 140px;
            ">♪ 耳を澄ます</button>
            <div style="flex-grow: 1;">
                <div style="color: #5a7a5a; font-size: 0.95em; font-weight: 500;">
                    ♪ 鳥に会いに行く ({n}羽)
                </div>
            </div>
        </div>
        <div id="rite_scene" style="
            position: relative; height: 195px; margin-top: 12px;
            background: linear-gradient(180deg, #b8d8f4 0%, #d8eec0 52%, #82c04a 100%);
            border-radius: 8px; overflow: hidden;
        ">{scene_html}</div>
        <div id="rite_met" style="
            margin-top: 10px; min-height: 20px; max-height: 72px; overflow-y: auto;
            color: #3a6a3a; font-size: 0.84em; line-height: 1.5;
        "></div>
        <div id="rite_gone" style="
            min-height: 16px; margin-top: 4px;
            color: #a08060; font-size: 0.80em;
            opacity: 0; transition: opacity 0.5s ease;
        "></div>
    </div>
    <script>
    (function() {{
        const BIRDS = {birds_json};
        const HAS_AMBIENT = {has_ambient_js};
        const btn    = document.getElementById('rite_btn');
        const metEl  = document.getElementById('rite_met');
        const goneEl = document.getElementById('rite_gone');
        let goneTimer = null;

        // 音響パラメータ: 距離差を控えめに(グラデーションを弱く)
        const D = {{
            b3:   {{ gain: 0.58, freq: 4200, wet: 0.20 }},
            b2:   {{ gain: 0.90, freq: 8000, wet: 0.09 }},
            b1:   {{ gain: 1.25, freq: 12000, wet: 0.01 }},
            gone: {{ gain: 0.00, freq: 400,  wet: 0.00 }}
        }};
        // 視覚パラメータ: 鳥の足が枝バー(37/54/70%)の上に乗る top% を逆算。
        // 60px×scale のスプライトをセンター原点で縮小するため、
        //   feet_pct = top + 15.38 * (scale + 1) となる。
        const BR = {{
            b3: {{ top: 11,   scale: 0.70, opacity: 0.72, z: 22 }},
            b2: {{ top: 24,   scale: 0.92, opacity: 0.88, z: 32 }},
            b1: {{ top: 36,   scale: 1.18, opacity: 1.00, z: 42 }}
        }};
        // 各枝のレーン幅 [left%, right%] — 各枝の両端の幹の内側
        const LANE = {{
            b3: [26, 74], b2: [19, 81], b1: [12, 88]
        }};
        const GAP_HALF = 5;   // 枝中央の切れ目: 50±GAP_HALF% は避ける
        // 枝間の隣接関係
        const NEXT = {{ b3: 'b2', b2: 'b1' }};
        const PREV = {{ b2: 'b3', b1: 'b2' }};
        // 各枝でのホップ確率(基準値、wariness で調整)
        const ADV  = {{ b3: 0.26, b2: 0.20 }};           // 手前方向(やや慎重に)
        const BACK = {{ b2: 0.12, b1: 0.12 }};          // 奥方向
        const FLEE = {{ b3: 0.03, b2: 0.025, b1: 0.045 }}; // 逃げにくく、ゆっくり滞在

        const RAMP    = 1.4;
        const STEP_MS = 6000;   // 3800→6000: ゆっくり枝に留まる
        const WARY_MS = 5000;
        const SPOOK_P = 0.16;
        const n = BIRDS.length;

        let ctx = null, master = null, running = false, timer = null, waryUntil = 0;
        let rafId = null;
        let saved = false;
        let ambient = null;
        let reverb = null;        // 共有リバーブバス(ConvolverNode)
        const nodes    = [];
        const sprites  = [];
        const birdLeft = [];   // 各鳥の現在の left%
        const b1Dwell  = [];   // b1 連続滞在ステップ数(2以上で観察成立)
        const met = new Set();

        // ── AGC(自動音量正規化)/ 呼応(かけあい)の状態 ──────────────
        // 録音ごとの音量差を吸収するため各鳥のピーク RMS を追跡し、
        // フレーズの切れ目(休符)を検知して別の鳥にゆっくりバトンを渡す。
        // 数値定数(AGC_TARGET 等)は audio_engine.py に集約。
        const peakRMS = [];          // 各鳥のピーク RMS 推定値
        const phraseOn = [];         // 各鳥が現在フレーズ中か
        const silentF  = [];         // 連続無音フレーム数
        let activeIdx  = 0;          // 現在フォアグラウンドの鳥インデックス
        let activeSince = 0;         // activeIdx になった時刻(ms)
        {ae.AUDIO_CONSTANTS_JS}

        // 初期 left% を b3(最奥)レーン内に等間隔配置(中央のギャップは避ける)
        for (let i = 0; i < n; i++) {{
            sprites.push(document.getElementById('rite_bird_' + i));
            b1Dwell.push(0);
            const [lmin, lmax] = LANE.b3;
            const mid = (lmin + lmax) / 2;
            const leftW = (mid - GAP_HALF) - lmin;
            const rightW = lmax - (mid + GAP_HALF);
            const v = (i + 0.5) / n * (leftW + rightW);
            birdLeft.push(v < leftW ? lmin + v : mid + GAP_HALF + (v - leftW));
        }}

        function ritLog(msg) {{
            // 2026-07-11追記(CEO実機報告調査用): 儀式で会った鳥が図鑑に反映されない
            // 不具合の原因特定用。"[TorisRitual]" タグで
            // `adb logcat | Select-String "TorisRitual"` から追える。
            try {{ console.log('[TorisRitual]', msg); }} catch (e) {{}}
        }}

        function saveObservations() {{
            if (saved || met.size === 0) return;
            saved = true;
            if (autoSaveTimer) {{ clearTimeout(autoSaveTimer); autoSaveTimer = null; }}
            const ids = [...met].map(j => BIRDS[j].id).join(',');
            ritLog('saveObservations: met=' + ids);
            // 2026-07-11追記(P1修正): 以前はここでトップwindowのdocumentへの
            // <script> 要素注入によりトップウィンドウを直接ナビゲーションしていたが、
            // ads.py の広告結果伝達で判明したのと同じ理由(モジュールdocstring
            // 「2026-07-10 追記(P1修正)」参照)——タブ切り替え・バックグラウンド化
            // など、コールバックが発火するタイミングそのものでナビゲーションを
            // 試みる操作は不安定になりうる——により、ここでのナビゲーションは
            // やめる。window.top.localStorage への同期的な書き込みだけに留め、
            // 実際にPython側へ届けるナビゲーションは app.py の
            // _inject_ritual_result_check()(毎回のrerunで動き続ける独立した
            // ポーリング、ads.py の _inject_ad_result_check() と同じパターン)
            // に委譲する。
            try {{
                const payload = JSON.stringify({{ ids: ids, ts: Date.now() }});
                window.top.localStorage.setItem('toris_ritual_pending_obs', payload);
                ritLog('pending obs written to localStorage: ' + ids);
            }} catch(e) {{ ritLog('failed: ' + e); }}
        }}

        // 2026-07-09追記(P1修正): 以前は「♪ 耳を澄ます」を明示的に止める・
        // ページを離れる、まで図鑑への反映(=保存の往復)を待っていたため、
        // 「会えたのに図鑑に反映されない」という報告につながっていた
        // (ユーザーはタブを切り替えるだけで、止めるボタンを押すとは限らない)。
        // 出会いから少し余韻を置いた後、自動的に保存の往復を行うことで、
        // 図鑑への反映と「出会えました」ポップアップ(app.py _obs_dialog)を
        // すぐに出す。複数羽がほぼ同時に出会った場合はタイマーを延長して
        // まとめて1回の往復にする(不要な連続リロードを避ける)。
        let autoSaveTimer = null;
        function scheduleAutoSave() {{
            if (autoSaveTimer) clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(saveObservations, 4000);
        }}

        // ── 3D音響(HRTF) ─────────────────────────────────────
        // 鳥の左右(x)と枝の奥行き(z)を頭部伝達関数で定位する。
        // 距離減衰は既存の D[branch].gain に任せるため rolloff は 0。
        // 構築に失敗する古い環境では左右だけの StereoPanner にフォールバック。
        {ae.MAKE_PANNER_JS}
        function setPan(nd, left, branch, t) {{
            const x = (left - 50) / 50 * 4;
            if (nd.pan.hrtf) {{
                const z = DEPTH_Z[branch] !== undefined ? DEPTH_Z[branch] : -5;
                try {{
                    nd.pan.node.positionX.setTargetAtTime(x, t, 0.25);
                    nd.pan.node.positionZ.setTargetAtTime(z, t, 0.25);
                }} catch (e) {{
                    try {{ nd.pan.node.setPosition(x, 0, z); }} catch (e2) {{}}
                }}
            }} else {{
                const p = Math.max(-0.85, Math.min(0.85, x / 4 * 0.8));
                nd.pan.node.pan.setTargetAtTime(p, t, 0.25);
            }}
        }}
        // 飛び去り: 音が頭上を抜けて遠ざかる
        function panGone(nd) {{
            if (!nd.pan.hrtf) return;
            const t = ctx.currentTime;
            try {{
                nd.pan.node.positionY.setTargetAtTime(7, t, 0.6);
                nd.pan.node.positionZ.setTargetAtTime(-16, t, 0.6);
            }} catch (e) {{}}
        }}

        // ── 鳴き方の時間帯連動 ─────────────────────────────────
        // 朝(4-10時)はさえずり中心の「朝のコーラス」、夕方〜夜は地鳴きが増える。
        function preferredType() {{
            const h = new Date().getHours();
            if (h >= 4 && h < 10)  return 'song';
            if (h >= 16 || h < 4)  return 'call';
            return null;  // 昼はどちらでも
        }}
        {ae.PICK_VARIANT_JS}

        function buildNode(i) {{
            // 鳴き声バリエーション: 同じ鳥の複数録音を同一チェーンにつなぎ、
            // 再生するのは常に1本(els[cur])。切り替えで鳴き方が変わる。
            const els = [];
            const nv = BIRDS[i].nv || 1;
            // ハイパス: 風・ハンドリングノイズなど低域のゴーッという音を除去
            const hp     = ctx.createBiquadFilter(); hp.type = 'highpass';
            hp.frequency.value = 520; hp.Q.value = 0.7;
            for (let v = 0; v < nv; v++) {{
                const el = document.getElementById('rite_audio_' + i + '_' + v);
                if (!el) continue;
                els.push(el);
                ctx.createMediaElementSource(el).connect(hp);
            }}
            // ローパス: 距離でこもり具合を変える(D[branch].freq)
            const filter = ctx.createBiquadFilter(); filter.type = 'lowpass';
            // ノイズゲート用ゲイン: 鳴き声の合間のサーッというヒスを絞る
            const gate    = ctx.createGain(); gate.gain.value = 1.0;
            // AGCゲイン: 録音ごとの音量差を正規化する
            const agcGain = ctx.createGain(); agcGain.gain.value = 1.0;
            // 距離ゲイン: 枝の遠近で音量を変える
            const gain    = ctx.createGain();
            // 呼応ゲイン: フォアグラウンド(1.0) / バックグラウンド(CALL_FLOOR)
            const chGain  = ctx.createGain(); chGain.gain.value = 1.0;
            // 3D定位(HRTF、フォールバックでStereoPanner)
            const pan     = makePanner();
            // リバーブ送り: 遠い枝ほど多く送り、森の奥行きを表現
            const wet     = ctx.createGain();
            // レベル監視用アナライザ(出力には接続しない)
            const ana     = ctx.createAnalyser(); ana.fftSize = 512;
            // チェーン: hp → filter → ana → gate → agcGain → gain → chGain → pan / wet
            hp.connect(filter);
            filter.connect(ana);
            filter.connect(gate);
            gate.connect(agcGain); agcGain.connect(gain);
            gain.connect(chGain);
            chGain.connect(pan.node); pan.node.connect(master);
            chGain.connect(wet); wet.connect(reverb);
            // 初期の鳴き方も時間帯の好みで選ぶ
            const cur = els.length > 1 ? pickVariant(i, -1) : 0;
            return {{ els, cur, filter, gain, agcGain, chGain, wet, gate, ana, pan,
                      buf: new Float32Array(ana.fftSize), branch: 'b3' }};
        }}

        // 鳴き方を別の録音に切り替える(さえずり⇄地鳴き、時間帯の好み付き)
        function switchCall(nd, i) {{
            if (nd.els.length < 2) return;
            const next = pickVariant(i, nd.cur);
            if (next === nd.cur) return;
            try {{ nd.els[nd.cur].pause(); }} catch(e) {{}}
            nd.cur = next;
            try {{ nd.els[next].play().catch(()=>{{}}); }} catch(e) {{}}
        }}

        // 森の残響をブラウザ内で合成: 減衰ノイズに初期反射を混ぜたインパルス応答。
        // 短め(1.6秒)・控えめにして、鳴き声を濁らせず奥行きだけ足す。
        {ae.MAKE_REVERB_IR_JS}

        // 環境音BGM: Freesound の実録音があればそれを、なければノイズ合成にフォールバック。
        {ae.MAKE_NOISE_BUFFER_JS}
        function buildAmbient() {{
            const ambEl = document.getElementById('rite_ambient');
            if (HAS_AMBIENT && ambEl) {{
                // 実録音パス: Freesound の森の環境音をループ再生
                const src   = ctx.createMediaElementSource(ambEl);
                const alp   = ctx.createBiquadFilter(); alp.type = 'lowpass';
                alp.frequency.value = 6000;  // 高域を少し丸める
                const again = ctx.createGain(); again.gain.value = 0.0;
                src.connect(alp); alp.connect(again); again.connect(master);
                ambEl.volume = 1.0;
                ambEl.play().catch(() => {{}});
                const t = ctx.currentTime;
                again.gain.setTargetAtTime(0.22, t, 3.5);  // ゆっくりフェードイン
                return {{ wind: ambEl, air: null, lfo: null, wgain: again, again }};
            }}
            // 合成フォールバック: 層1=低い風(ブラウンノイズ) + 層2=空気のざわめき
            const wind = ctx.createBufferSource();
            wind.buffer = makeNoiseBuffer(true); wind.loop = true;
            const wlp = ctx.createBiquadFilter(); wlp.type = 'lowpass';
            wlp.frequency.value = 420; wlp.Q.value = 0.3;
            const wgain = ctx.createGain(); wgain.gain.value = 0.0;
            wind.connect(wlp); wlp.connect(wgain); wgain.connect(master);
            const lfo = ctx.createOscillator(); lfo.frequency.value = 0.06;
            const lfoG = ctx.createGain(); lfoG.gain.value = 200;
            lfo.connect(lfoG); lfoG.connect(wlp.frequency);
            const air = ctx.createBufferSource();
            air.buffer = makeNoiseBuffer(false); air.loop = true;
            const abp = ctx.createBiquadFilter(); abp.type = 'bandpass';
            abp.frequency.value = 2600; abp.Q.value = 0.6;
            const again = ctx.createGain(); again.gain.value = 0.0;
            air.connect(abp); abp.connect(again); again.connect(master);
            wind.start(); air.start(); lfo.start();
            const t = ctx.currentTime;
            wgain.gain.setTargetAtTime(0.075, t, 2.5);
            again.gain.setTargetAtTime(0.012, t, 2.5);
            return {{ wind, air, lfo, wgain, again }};
        }}

        function rampLin(param, target) {{
            const t = ctx.currentTime;
            param.cancelScheduledValues(t);
            param.setValueAtTime(param.value, t);
            param.linearRampToValueAtTime(target, t + RAMP);
        }}
        function rampExp(param, target) {{
            const t = ctx.currentTime;
            param.cancelScheduledValues(t);
            param.setValueAtTime(Math.max(param.value, 1), t);
            param.exponentialRampToValueAtTime(Math.max(target, 1), t + RAMP);
        }}

        // ホップ先のレーン内でランダムな left% を返す(中央のギャップは避ける)
        function hopLeft(branch, i) {{
            const [lmin, lmax] = LANE[branch];
            const mid = (lmin + lmax) / 2;
            // 元の left に近い側に着地しやすく
            const preferLeft = birdLeft[i] !== undefined ? birdLeft[i] < mid : (i % 2 === 0);
            const useLeft = Math.random() < (preferLeft ? 0.65 : 0.35);
            const sideMin = useLeft ? lmin + 2 : mid + GAP_HALF + 1;
            const sideMax = useLeft ? mid - GAP_HALF - 1 : lmax - 2;
            return sideMin + Math.random() * (sideMax - sideMin);
        }}

        function applyVisual(i, branch) {{
            const sp = sprites[i];
            if (!sp) return;
            const v = BR[branch];
            sp.style.left      = birdLeft[i].toFixed(1) + '%';
            sp.style.top       = v.top + '%';
            sp.style.transform = 'translate(-50%,0) scale(' + v.scale + ')';
            sp.style.opacity   = v.opacity;
            sp.style.zIndex    = v.z;
        }}

        // 飛び去り: 斜めに画面外へ(どの枝からでも)
        function flyAwayUp(i) {{
            const sp = sprites[i];
            if (!sp) return;
            const drift = Math.max(5, Math.min(95, birdLeft[i] + (Math.random() * 24 - 12)));
            sp.style.transition =
                'top 1.5s ease-in, left 1.5s ease-in, transform 1.5s ease-in, opacity 1.5s ease-in';
            sp.style.zIndex    = 99;
            sp.style.left      = drift.toFixed(1) + '%';
            sp.style.top       = '-35%';
            sp.style.transform = 'translate(-50%,0) scale(0.28) scaleX(1.3)';
            sp.style.opacity   = '0';
        }}

        // 枝を移動(音響+視覚を同時更新)
        function moveBird(nd, i, branch) {{
            nd.branch = branch;
            rampLin(nd.gain.gain,      D[branch].gain);
            rampExp(nd.filter.frequency, D[branch].freq);
            rampLin(nd.wet.gain,       D[branch].wet);
            if (branch === 'gone') {{
                panGone(nd); flyAwayUp(i); markGone(i);
                // フォアグラウンドの鳥が飛び去ったら次の鳥に引き継ぐ
                if (i === activeIdx) {{
                    const alives = [];
                    for (let j = 0; j < nodes.length; j++) {{
                        if (j !== i && nodes[j].branch !== 'gone') alives.push(j);
                    }}
                    if (alives.length > 0) {{
                        const next = alives[Math.floor(Math.random() * alives.length)];
                        activeIdx = next; activeSince = Date.now();
                        nodes[next].chGain.gain.setTargetAtTime(1.0, ctx.currentTime, 0.8);
                    }}
                }}
                return;
            }}
            // 新しい枝でのランダムな着地位置
            birdLeft[i] = hopLeft(branch, i);
            // 3D定位を新しい位置(左右+奥行き)へなめらかに移動
            setPan(nd, birdLeft[i], branch, ctx.currentTime);
            const sp = sprites[i];
            if (sp) {{
                sp.style.transition =
                    'top 0.75s cubic-bezier(.36,.07,.19,.97),' +
                    'left 0.75s ease,' +
                    'transform 0.75s cubic-bezier(.36,.07,.19,.97),' +
                    'opacity 0.75s ease';
                applyVisual(i, branch);
            }}
        }}

        function markMet(i) {{
            if (met.has(i)) return;
            met.add(i);
            scheduleAutoSave();  // 図鑑へすぐ反映(P1修正、上のコメント参照)
            // テキスト: hint + 名前、フェードインして残す
            const line = document.createElement('div');
            line.style.cssText = 'animation:rite_met_in 0.5s ease-out;';
            line.textContent = '🪶 ' + BIRDS[i].hint + '、' + BIRDS[i].name + ' に出会えた！';
            metEl.appendChild(line);
            // 鳥スプライトをキラッと光らせる
            const sp = sprites[i];
            if (sp) {{
                sp.style.transition = 'filter 0.12s ease-out';
                sp.style.filter = 'brightness(2.6) drop-shadow(0 0 10px #fff8a0)';
                setTimeout(function() {{
                    sp.style.transition = 'filter 0.7s ease-out';
                    sp.style.filter = 'brightness(1)';
                    setTimeout(function() {{ sp.style.filter = ''; sp.style.transition = ''; }}, 750);
                }}, 130);
            }}
        }}

        function markGone(i) {{
            goneEl.textContent = '🕊 ' + BIRDS[i].hint + ' は庭の向こうへ去った';
            goneEl.style.opacity = '1';
            if (goneTimer) clearTimeout(goneTimer);
            goneTimer = setTimeout(function() {{ goneEl.style.opacity = '0'; }}, 7000);
        }}

        function step() {{
            // 自然なスプーク: 警戒時は飛び去り確率が上がる(後退はしない)
            if (Math.random() < SPOOK_P) waryUntil = Math.max(waryUntil, Date.now() + 2500);
            const waryMult = Date.now() < waryUntil ? 2.5 : 1.0;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.branch === 'gone') continue;
                const w = BIRDS[i].wariness;
                // 1) 飛び去り
                const pFlee = (FLEE[nd.branch] || 0.06) * (1 + w * 1.2) * waryMult;
                if (Math.random() < pFlee) {{ b1Dwell[i] = 0; moveBird(nd, i, 'gone'); continue; }}
                // 2) 枝間ホップ
                const nextB = NEXT[nd.branch];
                const prevB = PREV[nd.branch];
                const pAdv  = nextB ? (ADV[nd.branch]  || 0) * (1 - w * 0.5) : 0;
                const pBack = prevB ? (BACK[nd.branch] || 0) : 0;
                const r = Math.random();
                if (nextB && r < pAdv) {{
                    b1Dwell[i] = 0;
                    moveBird(nd, i, nextB);
                }} else if (prevB && r < pAdv + pBack) {{
                    b1Dwell[i] = 0;
                    moveBird(nd, i, prevB);
                }} else if (nd.branch === 'b1') {{
                    // b1 に留まり続けた回数をカウント。2ステップで観察成立(約8秒)
                    b1Dwell[i]++;
                    if (b1Dwell[i] >= 2) markMet(i);
                }}
                // 3) ときどき鳴き方を変える(さえずり⇄地鳴き)
                if (Math.random() < 0.18) switchCall(nd, i);
            }}
        }}

        function playAll() {{
            nodes.forEach(nd => {{
                const el = nd.els[nd.cur];
                if (el) el.play().catch(()=>{{}});
            }});
        }}

        // ノイズゲート + AGC + 呼応(かけあい)を1ループで処理する。
        // (GATE_THRESH / GATE_FLOOR は audio_engine.py で定義)
        function gateTick() {{
            if (!running || !ctx) return;
            const t = ctx.currentTime;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.branch === 'gone') continue;
                nd.ana.getFloatTimeDomainData(nd.buf);
                let sum = 0;
                for (let k = 0; k < nd.buf.length; k++) sum += nd.buf[k] * nd.buf[k];
                const rms = Math.sqrt(sum / nd.buf.length);

                // ① ノイズゲート: 休符中のヒスノイズを絞る
                nd.gate.gain.setTargetAtTime(rms < GATE_THRESH ? GATE_FLOOR : 1.0, t, 0.06);

                // ② AGC: 録音ごとの音量差を正規化する
                // 鳴き声中: ピークを速く追従。無音中: ゆっくり減衰。
                if (rms > GATE_THRESH) {{
                    peakRMS[i] = peakRMS[i] * 0.92 + rms * 0.08;  // 速いアタック
                }} else {{
                    peakRMS[i] *= 0.9998;                           // ゆっくり減衰
                }}
                const agcT = Math.min(Math.max(AGC_TARGET / Math.max(peakRMS[i], 0.003),
                                               AGC_MIN), AGC_MAX);
                nd.agcGain.gain.setTargetAtTime(agcT, t, 3.0);     // 3秒でゆっくり追従

                // ③ 呼応: フォアグラウンド鳥のフレーズ末尾でバトン渡し
                if (i === activeIdx) {{
                    if (rms > GATE_THRESH * 0.6) {{
                        phraseOn[i] = true;
                        silentF[i]  = 0;
                    }} else if (phraseOn[i]) {{
                        silentF[i]++;
                        // 休符が SILENT_NEED フレーム続いたら候補を探す
                        if (silentF[i] === SILENT_NEED
                                && Date.now() - activeSince > MIN_SOLO_MS
                                && Math.random() < 0.40) {{
                            const cands = [];
                            for (let j = 0; j < nodes.length; j++) {{
                                if (j !== i && nodes[j].branch !== 'gone') cands.push(j);
                            }}
                            if (cands.length > 0) {{
                                const next = cands[Math.floor(Math.random() * cands.length)];
                                // 現在の鳥: 2秒かけてバックグラウンドへ
                                nd.chGain.gain.setTargetAtTime(CALL_FLOOR, t, 1.5);
                                // 次の鳥: 0.35秒の「間」を置いてから1秒でフォアグラウンドへ
                                nodes[next].chGain.gain.setTargetAtTime(1.0, t + 0.35, 0.8);
                                activeIdx  = next;
                                activeSince = Date.now();
                                phraseOn[next] = false;
                                silentF[next]  = 0;
                            }}
                        }}
                    }}
                }}
            }}
            rafId = requestAnimationFrame(gateTick);
        }}

        function startRunning() {{
            timer = setInterval(step, STEP_MS);
            running = true;
            btn.textContent = '■ 終わる';
            btn.style.background = '#b8c8a0';
            if (rafId) cancelAnimationFrame(rafId);
            rafId = requestAnimationFrame(gateTick);
        }}

        function start() {{
            ctx = new (window.AudioContext || window.webkitAudioContext)();
            master = ctx.createDynamicsCompressor();
            master.threshold.value = -10;
            master.knee.value      = 10;
            master.ratio.value     = 4;
            master.attack.value    = 0.003;
            master.release.value   = 0.25;
            master.connect(ctx.destination);
            // 共有リバーブバス(全鳥が送る → 1つのConvolverで処理して軽量)
            reverb = ctx.createConvolver();
            reverb.buffer = makeReverbIR();
            const reverbReturn = ctx.createGain();
            reverbReturn.gain.value = 0.9;
            reverb.connect(reverbReturn); reverbReturn.connect(master);
            ambient = buildAmbient();
            for (let i = 0; i < n; i++) {{
                peakRMS.push(0.01);
                phraseOn.push(false);
                silentF.push(0);
                const nd = buildNode(i);
                nodes.push(nd);
                // b3 の初期値を直接セット(ランプ不要)
                nd.gain.gain.value        = D.b3.gain;
                nd.filter.frequency.value = D.b3.freq;
                nd.wet.gain.value         = D.b3.wet;
                setPan(nd, birdLeft[i], 'b3', ctx.currentTime);
                applyVisual(i, 'b3');
            }}
            // 呼応初期化: 鳥0をフォアグラウンド、他はバックグラウンドに設定
            activeIdx = 0; activeSince = Date.now();
            for (let i = 1; i < nodes.length; i++) {{
                nodes[i].chGain.gain.setValueAtTime(CALL_FLOOR, ctx.currentTime);
            }}
            playAll();
            startRunning();
        }}

        function stop() {{
            if (timer) clearInterval(timer);
            timer = null;
            if (rafId) {{ cancelAnimationFrame(rafId); rafId = null; }}
            nodes.forEach(nd => nd.els.forEach(el => {{ try {{ el.pause(); }} catch(e) {{}} }}));
            if (ctx) ctx.suspend();
            running = false;
            btn.textContent = '♪ 耳を澄ます';
            btn.style.background = '#cfd9b8';
            saveObservations();
        }}

        document.addEventListener('visibilitychange', function() {{
            if (document.hidden && running) saveObservations();
        }});

        btn.addEventListener('click', function() {{
            if (running) {{ stop(); }}
            else if (ctx) {{
                ctx.resume();
                // 再開時: 生き残っている鳥の中からフォアグラウンドを復元
                const alives = nodes.map((nd, j) => j).filter(j => nodes[j].branch !== 'gone');
                if (alives.length > 0 && !alives.includes(activeIdx)) {{
                    activeIdx = alives[0]; activeSince = Date.now();
                    nodes[activeIdx].chGain.gain.setValueAtTime(1.0, ctx.currentTime);
                }}
                playAll(); startRunning();
            }}
            else {{ start(); }}
        }});

        ['pointerdown', 'touchstart', 'wheel', 'keydown'].forEach(ev =>
            document.addEventListener(ev, function(e) {{
                if (running && e.target !== btn) waryUntil = Date.now() + WARY_MS;
            }}, {{ passive: true }})
        );
    }})();
    </script>
    """

    components.html(html, height=_COMPONENT_HEIGHT)
