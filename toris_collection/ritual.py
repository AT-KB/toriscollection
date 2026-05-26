"""
ritual.py - 鳥たちのコーラス UI (ステップ5a+5b)

これまでの積み上げ:
  - ステップ3: 「♪ 耳を澄ます」で音を鳴らす(自動再生制限の突破)
  - ステップ4: 最大4羽を同時再生し、距離で音量・ローパス・エコーを変化
  - ステップ5a: 各鳥のドット絵スプライトを距離に応じて表示
  - ステップ5b: 儀式終了時に近距離観察を Sheets に保存

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


_COMPONENT_HEIGHT = 330
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


def render_ritual(resident_ids, biome_id: str, birds_data: dict):
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
                    birds.append({
                        "id":       bid,
                        "name":     bird.get("name", bid),
                        "color":    bird.get("color", "#888"),
                        "wariness": float(bird.get("wariness", 0.5)),
                        "b64":      b64,
                        "sprite":   _get_sprite_b64(bid),
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
            f'style="position:absolute;left:{left_pct:.1f}%;top:8%;'
            f'transform:translate(-50%,0) scale(0.5);opacity:0.35;'
            f'transition:top 2.5s ease,transform 2.5s ease,opacity 2.5s ease;">'
            f'{inner}</div>'
        )
    scene_html = "".join(sprite_divs)

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
            position: relative; height: 150px; margin-top: 12px;
            background: linear-gradient(180deg, #e8f0dd 0%, #d6e4c8 100%);
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
            far:  {{ gain: 0.05, freq: 450,  wet: 0.45 }},
            mid:  {{ gain: 0.45, freq: 2200, wet: 0.15 }},
            near: {{ gain: 1.00, freq: 12000, wet: 0.02 }},
            gone: {{ gain: 0.0,  freq: 400,  wet: 0.0  }}
        }};
        const V = {{
            far:  {{ scale: 0.5,  opacity: 0.35, top: 8  }},
            mid:  {{ scale: 0.8,  opacity: 0.7,  top: 32 }},
            near: {{ scale: 1.15, opacity: 1.0,  top: 54 }},
            gone: {{ scale: 0.4,  opacity: 0.0,  top: 4  }}
        }};
        const RAMP    = 2.5;
        const STEP_MS = 4000;
        const WARY_MS = 5000;
        const SPOOK_P = 0.18;

        let ctx = null, running = false, timer = null, waryUntil = 0;
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
            src.connect(filter); filter.connect(gain); gain.connect(ctx.destination);
            gain.connect(delay); delay.connect(fb); fb.connect(delay);
            delay.connect(wet);  wet.connect(ctx.destination);
            return {{ audioEl, filter, gain, wet, dist: 'far' }};
        }}

        function ramp(param, target) {{
            const t = ctx.currentTime;
            param.cancelScheduledValues(t);
            param.setValueAtTime(param.value, t);
            param.linearRampToValueAtTime(target, t + RAMP);
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

        function applyDist(nd, i, dist) {{
            const p = D[dist];
            ramp(nd.gain.gain, p.gain);
            ramp(nd.filter.frequency, p.freq);
            ramp(nd.wet.gain, p.wet);
            nd.dist = dist;
            applyVisual(i, dist);
            if (dist === 'gone') markGone(i);
        }}

        function markMet(i) {{
            if (met.has(i)) return;
            met.add(i);
            metEl.textContent = '🪶 出会えた鳥: ' +
                [...met].map(j => BIRDS[j].name).join('、');
        }}

        function markGone(i) {{
            goneEl.textContent = '🕊 ' + BIRDS[i].name + ' が飛び立ってしまった…';
            goneEl.style.opacity = '1';
            if (goneTimer) clearTimeout(goneTimer);
            goneTimer = setTimeout(function() {{
                goneEl.style.opacity = '0';
            }}, 3000);
        }}

        function step() {{
            if (Math.random() < SPOOK_P) {{
                waryUntil = Math.max(waryUntil, Date.now() + 2500);
            }}
            const wary = Date.now() < waryUntil;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.dist === 'gone') continue;
                const w = BIRDS[i].wariness, r = Math.random();
                if (wary) {{
                    if      (nd.dist === 'far'  && r < 0.30) applyDist(nd, i, 'gone');
                    else if (nd.dist === 'mid'  && r < 0.45) applyDist(nd, i, 'far');
                    else if (nd.dist === 'near' && r < 0.55) applyDist(nd, i, 'mid');
                }} else {{
                    if (nd.dist === 'far') {{
                        if      (r < 0.22) applyDist(nd, i, 'mid');
                        else if (r < 0.27) applyDist(nd, i, 'gone');
                    }} else if (nd.dist === 'mid') {{
                        const pNear = 0.18 * (1 - w * 0.8);
                        if      (r < pNear)        {{ applyDist(nd, i, 'near'); markMet(i); }}
                        else if (r < pNear + 0.04) applyDist(nd, i, 'gone');
                    }} else if (nd.dist === 'near') {{
                        if      (r < 0.10) applyDist(nd, i, 'mid');
                        else if (r < 0.12) applyDist(nd, i, 'gone');
                    }}
                }}
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
