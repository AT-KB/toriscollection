"""
ritual.py - 鳥たちのコーラス UI (ステップ5a+5b)

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
    # Python 3.14 の並行インポートバグへの保険
    import importlib
    xc_client = importlib.import_module("xc_client")


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
    鳥たちのコーラスUI(4本枝・ホップメカニクス)をホームタブに描画する。

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

    # 枝レイアウト: b4=奥(上・小) 〜 b1=手前(下・大)
    # (top%, width%, stroke_w, color, opacity, with_twig)
    _BRANCH_SPECS = [
        (14, 52,  3, "#9B7050", 0.45, False),  # b4: 奥
        (33, 67,  5, "#7a5030", 0.62, False),  # b3
        (52, 82,  7, "#5e3c16", 0.80, True),   # b2
        (71, 97, 10, "#4a2c06", 0.95, True),   # b1: 手前
    ]
    branch_parts = []
    for bnum_idx, (tp, wp, sw, col, op, with_twig) in enumerate(_BRANCH_SPECS):
        lp = (100 - wp) / 2
        twig = (
            f'<path d="M148,14 Q163,7 178,4" stroke="{col}" '
            f'stroke-width="{max(1, sw // 2)}" fill="none" stroke-linecap="round"/>'
            if with_twig else ""
        )
        branch_parts.append(
            f'<div style="position:absolute;top:{tp}%;left:{lp:.1f}%;width:{wp}%;'
            f'opacity:{op};z-index:1;pointer-events:none;">'
            f'<svg viewBox="0 0 200 28" preserveAspectRatio="none" '
            f'style="width:100%;height:16px;display:block;overflow:visible;">'
            f'<path d="M2,18 Q55,11 100,15 Q148,19 198,13" '
            f'stroke="{col}" stroke-width="{sw}" fill="none" stroke-linecap="round"/>'
            f'{twig}'
            f'</svg></div>'
        )
    branch_html = "".join(branch_parts)

    # スプライト: 最初は b4(奥)の枝にとまった状態
    sprite_divs = []
    for i, b in enumerate(birds):
        lp = 24.0 + (i + 0.5) / n * 52.0  # b4 のレーン: 24%〜76%
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
            f'style="position:absolute;left:{lp:.1f}%;top:14%;'
            f'transform:translate(-50%,0) scale(0.52);opacity:0.45;z-index:4;'
            f'transition:top 0.75s cubic-bezier(.36,.07,.19,.97),'
            f'left 0.75s ease,transform 0.75s cubic-bezier(.36,.07,.19,.97),'
            f'opacity 0.75s ease;">'
            f'{inner}</div>'
        )
    scene_html = branch_html + "".join(sprite_divs)

    html = f"""
    {audio_tags}
    <style>
      @keyframes rite_bob {{
        0%, 100% {{ margin-top: 0px; }}
        50%      {{ margin-top: -5px; }}
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
            position: relative; height: 195px; margin-top: 12px;
            background: linear-gradient(180deg, #c4dab8 0%, #d4e8c0 55%, #c0dca8 100%);
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

        // 音響パラメータ: b1=手前(クリア) ～ b4=奥(くもった)
        const D = {{
            b4:   {{ gain: 0.22, freq: 1200, wet: 0.50 }},
            b3:   {{ gain: 0.50, freq: 3500, wet: 0.28 }},
            b2:   {{ gain: 0.88, freq: 7000, wet: 0.12 }},
            b1:   {{ gain: 1.40, freq: 12000, wet: 0.00 }},
            gone: {{ gain: 0.00, freq: 400,  wet: 0.00 }}
        }};
        // 視覚パラメータ(top% = シーン上端からの位置)
        const BR = {{
            b4: {{ top: 14, scale: 0.52, opacity: 0.45 }},
            b3: {{ top: 33, scale: 0.70, opacity: 0.68 }},
            b2: {{ top: 52, scale: 0.90, opacity: 0.85 }},
            b1: {{ top: 71, scale: 1.18, opacity: 1.00 }}
        }};
        // 各枝のレーン幅 [left%, right%]
        const LANE = {{
            b4: [24, 76], b3: [16, 84], b2: [9, 91], b1: [1.5, 98.5]
        }};
        // 枝間の隣接関係
        const NEXT = {{ b4: 'b3', b3: 'b2', b2: 'b1' }};
        const PREV = {{ b3: 'b4', b2: 'b3', b1: 'b2' }};
        // 各枝でのホップ確率(基準値、wariness で調整)
        const ADV  = {{ b4: 0.32, b3: 0.26, b2: 0.20 }};   // 手前方向(b1へ)
        const BACK = {{ b3: 0.12, b2: 0.14, b1: 0.10 }};    // 奥方向(b4へ)
        const FLEE = {{ b4: 0.06, b3: 0.05, b2: 0.04, b1: 0.03 }}; // 飛び去り

        const RAMP    = 1.4;
        const STEP_MS = 3800;
        const WARY_MS = 5000;
        const SPOOK_P = 0.16;
        const n = BIRDS.length;

        let ctx = null, master = null, running = false, timer = null, waryUntil = 0;
        let saved = false;
        const nodes    = [];
        const sprites  = [];
        const birdLeft = [];   // 各鳥の現在の left%
        const met = new Set();

        // 初期 left% を b4 レーン内に均等配置
        for (let i = 0; i < n; i++) {{
            sprites.push(document.getElementById('rite_bird_' + i));
            const [lmin, lmax] = LANE.b4;
            birdLeft.push(lmin + (i + 0.5) / n * (lmax - lmin));
        }}

        function saveObservations() {{
            if (saved || met.size === 0) return;
            saved = true;
            const ids = [...met].map(j => BIRDS[j].id).join(',');
            try {{
                const url = new URL(window.top.location.href);
                url.searchParams.set('ritual_obs', ids);
                window.top.location.href = url.toString();
            }} catch(e) {{}}
        }}

        function buildNode(i) {{
            const audioEl = document.getElementById('rite_audio_' + i);
            const src    = ctx.createMediaElementSource(audioEl);
            const filter = ctx.createBiquadFilter(); filter.type = 'lowpass';
            const gain   = ctx.createGain();
            const delay  = ctx.createDelay(1.0); delay.delayTime.value = 0.28;
            const fb     = ctx.createGain(); fb.gain.value = 0.32;
            const wet    = ctx.createGain();
            src.connect(filter); filter.connect(gain); gain.connect(master);
            gain.connect(delay); delay.connect(fb); fb.connect(delay);
            delay.connect(wet); wet.connect(master);
            return {{ audioEl, filter, gain, wet, branch: 'b4' }};
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

        // ホップ先のレーン内でランダムな left% を返す
        function hopLeft(branch, i) {{
            const [lmin, lmax] = LANE[branch];
            const base = lmin + (i + 0.3 + Math.random() * 0.4) / n * (lmax - lmin);
            return Math.max(lmin + 2, Math.min(lmax - 2, base + (Math.random() * 12 - 6)));
        }}

        function applyVisual(i, branch) {{
            const sp = sprites[i];
            if (!sp) return;
            const v = BR[branch];
            sp.style.left      = birdLeft[i].toFixed(1) + '%';
            sp.style.top       = v.top + '%';
            sp.style.transform = 'translate(-50%,0) scale(' + v.scale + ')';
            sp.style.opacity   = v.opacity;
            sp.style.zIndex    = Math.round(v.top);
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
            if (branch === 'gone') {{ flyAwayUp(i); markGone(i); return; }}
            // 新しい枝でのランダムな着地位置
            birdLeft[i] = hopLeft(branch, i);
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
            metEl.textContent = '🪶 出会えた鳥: ' + [...met].map(j => BIRDS[j].name).join('、');
        }}

        function markGone(i) {{
            goneEl.textContent = '🕊 ' + BIRDS[i].name + ' は庭の向こうへ去った';
            goneEl.style.opacity = '1';
            if (goneTimer) clearTimeout(goneTimer);
            goneTimer = setTimeout(function() {{ goneEl.style.opacity = '0'; }}, 3000);
        }}

        function step() {{
            // 自然なスプーク: 警戒時は飛び去り確率が上がる(後退はしない)
            if (Math.random() < SPOOK_P) waryUntil = Math.max(waryUntil, Date.now() + 2500);
            const waryMult = Date.now() < waryUntil ? 2.5 : 1.0;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.branch === 'gone') continue;
                const w = BIRDS[i].wariness;
                // 1) 飛び去り: 距離と警戒度に応じた確率
                const pFlee = (FLEE[nd.branch] || 0.05) * (1 + w * 1.2) * waryMult;
                if (Math.random() < pFlee) {{ moveBird(nd, i, 'gone'); continue; }}
                // 2) 枝間ホップ: 手前へ or 奥へ(ぴょんぴょん)
                const nextB = NEXT[nd.branch];
                const prevB = PREV[nd.branch];
                const pAdv  = nextB ? (ADV[nd.branch]  || 0) * (1 - w * 0.5) : 0;
                const pBack = prevB ? (BACK[nd.branch] || 0) : 0;
                const r = Math.random();
                if (nextB && r < pAdv) {{
                    moveBird(nd, i, nextB);
                    if (nextB === 'b1') markMet(i);  // 手前に来た瞬間に観察記録
                }} else if (prevB && r < pAdv + pBack) {{
                    moveBird(nd, i, prevB);
                }}
                // else: 同じ枝で bob アニメーションのみ
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
            master = ctx.createDynamicsCompressor();
            master.threshold.value = -10;
            master.knee.value      = 10;
            master.ratio.value     = 4;
            master.attack.value    = 0.003;
            master.release.value   = 0.25;
            master.connect(ctx.destination);
            for (let i = 0; i < n; i++) {{
                const nd = buildNode(i);
                nodes.push(nd);
                // b4 の初期値を直接セット(ランプ不要)
                nd.gain.gain.value       = D.b4.gain;
                nd.filter.frequency.value = D.b4.freq;
                nd.wet.gain.value        = D.b4.wet;
                applyVisual(i, 'b4');
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
