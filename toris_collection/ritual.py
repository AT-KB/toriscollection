"""
ritual.py - 鳥たちのコーラス UI (ステップ5a+5b)

これまでの積み上げ:
  - ステップ3: 「♪ 耳を澄ます」で音を鳴らす(自動再生制限の突破)
  - ステップ4: 最大4羽を同時再生し、距離で音量・ローパス・エコーを変化
  - ステップ5a: 各鳥のドット絵スプライトを距離に応じて表示
  - ステップ5b: 儀式終了時に近距離観察を Sheets に保存
  - 改善第一弾: 近距離を驚くほどクリアに(gain増+コンプレッサー+エコー0)、
    遠近の対比を強化。
  - 改善第二弾: 鳥は食物網でつながりの強い「木」にとまった状態から始まる。
    接近は一方向(far→mid→near、後退なし)。距離と警戒度に応じた確率で
    「飛び去る(gone)」のみが退場経路。横揺れ演出を廃止し、木から手前へ
    まっすぐ降りてくる自然な動きに。

このファイルで使っている技術:
  - Web Audio API(音量・フィルター・エコーの距離変化)
  - st.iframe(html, ...) — components.v1.html は2026-06-01削除予定のため移行済み
  - lazy loading(音源取得は「耳を澄ます」ボタン押下後にのみ実行、ホームタブを即時表示)
  - top window クエリパラメータで観察記録を Python に渡す

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

try:
    import xc_client
except (KeyError, AttributeError):
    # Python 3.14 の並行インポートバグへの保険(他セッションが同時 import した時の KeyError)
    import importlib
    xc_client = importlib.import_module("xc_client")


_COMPONENT_HEIGHT = 352
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
    """ドット絵スプライト(png)をbase64で返す。なければ None(色丸で代替)。"""
    p = _SPRITE_DIR / f"{bird_id}.png"
    if p.exists():
        try:
            return base64.b64encode(p.read_bytes()).decode("ascii")
        except Exception:
            return None
    return None


def _fetch_bird_audio(args: tuple) -> tuple:
    """(bid, bird_dict) → (bid, b64_or_None)  並列実行用"""
    bid, bird = args
    sci = bird.get("scientific", "")
    if not sci:
        return bid, None
    return bid, _get_audio_b64(sci)


def _perch_for_bird(bird, planted_ids, plants_data, insects_data):
    """鳥が最初にとまる「木」を食物網のつながりから選ぶ。

    優先順位(つながりが強いほど優先):
      1. 鳥が直接食べる植物で、いま植えてあるもの
      2. 鳥の獲物(昆虫)が食べる植物で、いま植えてあるもの
      3. 鳥が直接食べる植物(未植栽でも)
      4. 鳥の獲物が食べる植物(未植栽でも)
      5. どれも無ければ汎用の木 🌳

    Returns: (icon_emoji, plant_name)
    """
    planted = set(planted_ids or [])
    plants_data = plants_data or {}
    insects_data = insects_data or {}

    def _pick(pid):
        pl = plants_data.get(pid)
        if pl:
            return pl.get("icon", "🌳"), pl.get("name", "")
        return None

    # 1) 直接食 × 植栽済み
    for pid in bird.get("eats_plants", []):
        if pid in planted:
            r = _pick(pid)
            if r:
                return r
    # 2) 間接食(獲物が食べる) × 植栽済み
    for ins in bird.get("eats_insects", []):
        for pid in insects_data.get(ins, {}).get("eats_plants", []):
            if pid in planted:
                r = _pick(pid)
                if r:
                    return r
    # 3) 直接食(未植栽でも)
    for pid in bird.get("eats_plants", []):
        r = _pick(pid)
        if r:
            return r
    # 4) 間接食(未植栽でも)
    for ins in bird.get("eats_insects", []):
        for pid in insects_data.get(ins, {}).get("eats_plants", []):
            r = _pick(pid)
            if r:
                return r
    return "🌳", ""


def render_ritual(resident_ids, biome_id: str, birds_data: dict,
                  planted_ids=None, plants_data=None, insects_data=None):
    """
    鳥たちのコーラスUI(距離メカニクス)をホームタブに描画する。

    ロード戦略(遅延読み込み):
      - 初回: 軽量な招待ボタンだけ表示(xeno-canto アクセスなし → ホームタブ即時表示)
      - ボタン押下後のみ音源を取得してフル儀式UIを描画
      - 2回目以降: @st.cache_data でキャッシュ済み → 即時表示
    """
    if not resident_ids:
        return
    if not xc_client.is_enabled():
        return

    # ── フェーズ1: 招待ボタン(音源未取得・軽量) ────────────────────────────────
    if not st.session_state.get("ritual_ready"):
        n = min(len(resident_ids), _MAX_BIRDS)
        names = "、".join(
            birds_data[bid].get("name", bid)
            for bid in resident_ids[:n]
            if bid in birds_data
        )
        st.markdown(
            f"""<div style="background:linear-gradient(180deg,#f7faf2,#eef4e6);
            padding:14px 20px;border-radius:12px;border-left:4px solid #7ba87b;
            margin-bottom:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
            <div style="color:#5a7a5a;font-size:0.95em;font-weight:500;">
                ♪ 鳥たちのコーラス ({n}羽)</div>
            <div style="color:#888;font-size:0.82em;margin-top:3px;">{names}</div>
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
                bid, b64 = future.result()
                if b64 and len(birds) < _MAX_BIRDS:
                    bird = birds_data[bid]
                    perch_icon, perch_name = _perch_for_bird(
                        bird, planted_ids, plants_data, insects_data
                    )
                    birds.append({
                        "id":         bid,
                        "name":       bird.get("name", bid),
                        "color":      bird.get("color", "#888"),
                        "wariness":   float(bird.get("wariness", 0.5)),
                        "b64":        b64,
                        "sprite":     _get_sprite_b64(bid),
                        "perch_icon": perch_icon,
                        "perch_name": perch_name,
                    })

    if not birds:
        st.session_state.ritual_ready = False
        return

    # 元の順序(resident_ids の並び)を維持する
    id_order = {bid: i for i, bid in enumerate(resident_ids)}
    birds.sort(key=lambda b: id_order.get(b["id"], 999))

    n = len(birds)
    names_text = "、".join(b["name"] for b in birds)
    birds_meta = [
        {"id": b["id"], "name": b["name"], "wariness": b["wariness"]}
        for b in birds
    ]
    birds_json = json.dumps(birds_meta, ensure_ascii=False)

    audio_tags = "".join(
        f'<audio id="rite_audio_{i}" preload="auto" loop style="display:none">'
        f'<source src="data:audio/mp3;base64,{b["b64"]}" type="audio/mp3"></audio>'
        for i, b in enumerate(birds)
    )

    # 止まり木: 各鳥のレーン上部に、つながりの強い植物アイコンを描く。
    # 鳥はこの木にとまった状態(far)から始まり、手前へ降りてくる。
    tree_divs = []
    for i, b in enumerate(birds):
        left_pct = (i + 0.5) / n * 100.0
        tree_divs.append(
            f'<div class="rite_tree" '
            f'style="position:absolute;left:{left_pct:.1f}%;top:2px;'
            f'transform:translateX(-50%);font-size:42px;line-height:1;'
            f'opacity:0.9;z-index:0;pointer-events:none;'
            f'filter:drop-shadow(0 2px 2px rgba(60,80,50,0.18));">'
            f'{b["perch_icon"]}</div>'
        )

    sprite_divs = []
    for i, b in enumerate(birds):
        left_pct = (i + 0.5) / n * 100.0
        if b["sprite"]:
            inner = (
                f'<img src="data:image/png;base64,{b["sprite"]}" '
                f'style="width:60px;height:60px;image-rendering:pixelated;'
                f'animation:rite_bob {3.0 + i * 0.4:.1f}s ease-in-out infinite;">'
            )
        else:
            inner = (
                f'<div style="width:46px;height:46px;border-radius:50%;'
                f'background:{b["color"]};'
                f'animation:rite_bob {3.0 + i * 0.4:.1f}s ease-in-out infinite;"></div>'
            )
        sprite_divs.append(
            f'<div class="rite_bird" id="rite_bird_{i}" '
            f'style="position:absolute;left:{left_pct:.1f}%;top:12%;'
            f'transform:translate(-50%,0) scale(0.5);opacity:0.45;z-index:4;'
            f'transition:top 1.5s ease,left 1.5s ease,transform 1.5s ease,opacity 1.5s ease;">'
            f'{inner}</div>'
        )
    scene_html = "".join(tree_divs) + "".join(sprite_divs)

    html = f"""
    {audio_tags}
    <style>
      @keyframes rite_bob {{
        0%, 100% {{ margin-top: 0px; }}
        50%      {{ margin-top: -4px; }}
      }}
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
                    ♪ 鳥たちのコーラス ({n}羽)
                </div>
                <div style="color: #888; font-size: 0.82em; margin-top: 3px;">
                    {names_text}
                </div>
            </div>
        </div>
        <div id="rite_scene" style="
            position: relative; height: 172px; margin-top: 12px;
            background: linear-gradient(180deg, #eaf2e0 0%, #d6e4c8 100%);
            border-radius: 8px; overflow: hidden;
        ">{scene_html}</div>
        <div id="rite_met" style="
            margin-top: 10px; min-height: 18px;
            color: #5a7a5a; font-size: 0.82em;
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
        const btn    = document.getElementById('rite_btn');
        const metEl  = document.getElementById('rite_met');
        const goneEl = document.getElementById('rite_gone');
        let goneTimer = null;

        const D = {{
            far:  {{ gain: 0.38, freq: 1800,  wet: 0.35 }},
            mid:  {{ gain: 0.80, freq: 5000,  wet: 0.12 }},
            near: {{ gain: 1.40, freq: 12000, wet: 0.00 }},
            gone: {{ gain: 0.0,  freq: 400,   wet: 0.0  }}
        }};
        const V = {{
            far:  {{ scale: 0.5,  opacity: 0.45, top: 12 }},
            mid:  {{ scale: 0.85, opacity: 0.8,  top: 40 }},
            near: {{ scale: 1.2,  opacity: 1.0,  top: 62 }},
            gone: {{ scale: 0.4,  opacity: 0.0,  top: 4  }}
        }};
        const RAMP    = 1.6;
        const STEP_MS = 4000;
        const WARY_MS = 5000;
        const SPOOK_P = 0.18;
        // 接近は一方向。各ステップで「近づく確率」と「飛び去る確率」だけを判定する。
        const ADV  = {{ far: 0.34, mid: 0.24 }};   // 一段近づく基礎確率(警戒度で減衰)
        const FLEE = {{ far: 0.05, mid: 0.09, near: 0.02 }}; // 飛び去る基礎確率(距離依存)

        let ctx = null, master = null, running = false, timer = null, waryUntil = 0;
        let saved = false;
        const nodes = [];
        const sprites = [];
        const met = new Set();

        for (let i = 0; i < BIRDS.length; i++) {{
            sprites.push(document.getElementById('rite_bird_' + i));
        }}

        function saveObservations() {{
            if (saved || met.size === 0) return;
            saved = true;
            const ids = [...met].map(j => BIRDS[j].id).join(',');
            try {{
                const url = new URL(window.top.location.href);
                url.searchParams.set('ritual_obs', ids);
                window.top.location.href = url.toString();
            }} catch (e) {{}}
        }}

        function buildNode(i) {{
            const audioEl = document.getElementById('rite_audio_' + i);
            const src    = ctx.createMediaElementSource(audioEl);
            const filter = ctx.createBiquadFilter(); filter.type = 'lowpass';
            const gain   = ctx.createGain();
            const delay  = ctx.createDelay(1.0);    delay.delayTime.value = 0.28;
            const fb     = ctx.createGain();         fb.gain.value = 0.32;
            const wet    = ctx.createGain();
            src.connect(filter); filter.connect(gain); gain.connect(master);
            gain.connect(delay); delay.connect(fb); fb.connect(delay);
            delay.connect(wet);  wet.connect(master);
            return {{ audioEl, filter, gain, wet, dist: 'far' }};
        }}

        function rampLin(param, target) {{
            const t = ctx.currentTime;
            param.cancelScheduledValues(t);
            param.setValueAtTime(param.value, t);
            param.linearRampToValueAtTime(target, t + RAMP);
        }}

        // 周波数は対数知覚なので指数カーブの方が自然に「近づく」感じになる
        function rampExp(param, target) {{
            const t = ctx.currentTime;
            param.cancelScheduledValues(t);
            param.setValueAtTime(Math.max(param.value, 1), t);
            param.exponentialRampToValueAtTime(Math.max(target, 1), t + RAMP);
        }}

        function applyVisual(i, dist) {{
            const sp = sprites[i];
            if (!sp) return;
            const v = V[dist];
            sp.style.top = v.top + '%';
            sp.style.opacity = v.opacity;
            sp.style.transform = 'translate(-50%,0) scale(' + v.scale + ')';
            sp.style.zIndex = Math.round(v.top);
        }}

        // 退場: 翼を広げ、画面上端の外へ斜めに飛び去る軌跡(後退ではなく一度きりの離脱)。
        function flyAwayUp(i) {{
            const sp = sprites[i];
            if (!sp) return;
            const cur = parseFloat(sp.style.left) || 50;
            const drift = Math.max(0, Math.min(100, cur + (Math.random() * 24 - 12)));
            sp.style.transition =
                'top 1.6s ease-in, left 1.6s ease-in, transform 1.6s ease-in, opacity 1.6s ease-in';
            sp.style.zIndex = 99;
            sp.style.left = drift.toFixed(1) + '%';
            sp.style.top = '-35%';
            sp.style.transform = 'translate(-50%,0) scale(0.3) scaleX(1.25)';
            sp.style.opacity = '0';
        }}

        function applyDist(nd, i, dist) {{
            const p = D[dist];
            rampLin(nd.gain.gain, p.gain);
            rampExp(nd.filter.frequency, p.freq);
            rampLin(nd.wet.gain, p.wet);
            nd.dist = dist;
            if (dist === 'gone') {{
                flyAwayUp(i);
                markGone(i);
            }} else {{
                // 一方向の接近: 木から手前へまっすぐ降りて大きくなる(横揺れなし)。
                applyVisual(i, dist);
            }}
        }}

        function markMet(i) {{
            if (met.has(i)) return;
            met.add(i);
            metEl.textContent = '🪶 出会えた鳥: ' +
                [...met].map(j => BIRDS[j].name).join('、');
        }}

        function markGone(i) {{
            goneEl.textContent = '🕊 ' + BIRDS[i].name + ' は庭の向こうへ去った';
            goneEl.style.opacity = '1';
            if (goneTimer) clearTimeout(goneTimer);
            goneTimer = setTimeout(function() {{
                goneEl.style.opacity = '0';
            }}, 3000);
        }}

        function step() {{
            // 自然なスプーク: たまに警戒が高まる。後退はせず「飛び去りやすさ」だけが上がる。
            if (Math.random() < SPOOK_P) {{
                waryUntil = Math.max(waryUntil, Date.now() + 2500);
            }}
            const waryMult = Date.now() < waryUntil ? 3.0 : 1.0;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.dist === 'gone') continue;
                const w = BIRDS[i].wariness;
                // 1) 飛び去り判定: 距離(近いほど落ち着く)と警戒度に応じた確率。
                const pFlee = FLEE[nd.dist] * (1 + w * 1.4) * waryMult;
                if (Math.random() < pFlee) {{ applyDist(nd, i, 'gone'); continue; }}
                // 2) 接近判定: 一方向のみ。警戒度が高い鳥ほど近づきにくい。
                if (nd.dist === 'far') {{
                    if (Math.random() < ADV.far * (1 - w * 0.6)) applyDist(nd, i, 'mid');
                }} else if (nd.dist === 'mid') {{
                    if (Math.random() < ADV.mid * (1 - w * 0.7)) {{
                        applyDist(nd, i, 'near'); markMet(i);
                    }}
                }}
                // near は観察済みとして留まる(退場は飛び去りのみ)。
            }}
        }}

        function playAll() {{ nodes.forEach(nd => nd.audioEl.play().catch(()=>{{}})); }}

        function startRunning() {{
            timer = setInterval(step, STEP_MS);
            running = true;
            btn.textContent = '■ 終わる';
            btn.style.background = '#b8c8a0';
        }}

        function start() {{
            ctx = new (window.AudioContext || window.webkitAudioContext)();
            // マスターにコンプレッサー: 近距離 gain>1.0 でもクリップせず音量感を安定
            master = ctx.createDynamicsCompressor();
            master.threshold.value = -10;
            master.knee.value = 10;
            master.ratio.value = 4;
            master.attack.value = 0.003;
            master.release.value = 0.25;
            master.connect(ctx.destination);
            for (let i = 0; i < BIRDS.length; i++) {{
                const nd = buildNode(i);
                nodes.push(nd);
                applyDist(nd, i, 'far');
            }}
            playAll();
            startRunning();
        }}

        function stop() {{
            if (timer) clearInterval(timer);
            timer = null;
            nodes.forEach(nd => {{ try {{ nd.audioEl.pause(); }} catch(e) {{}} }});
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
            else if (ctx) {{ ctx.resume(); playAll(); startRunning(); }}
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

    st.iframe(html, height=_COMPONENT_HEIGHT)
