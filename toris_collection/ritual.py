"""
ritual.py - 鳥たちのコーラス UI (ステップ4: 複数鳥 + 距離による音響変化)

ステップ4の中身:
  - 滞在鳥のうち最大4羽を同時再生(各鳥が個別の Audio + Filter + Gain + Delay)
  - 全鳥は「遠く」から始まる(小音量・こもった音・エコー強め)
  - 4秒ごとに各鳥の距離状態を確率的に遷移(遠→中→近、たまに不在)
  - 距離が変わると音量・ローパス・エコー量を2.5秒かけて滑らかに変化
  - iframe内をタップ/スクロールすると数秒「警戒モード」になり、鳥が遠ざかりやすい
  - さらに確率的な「突然の驚き」で自然に警戒を体験できる
  - 近距離まで来た鳥は「出会えた鳥」として控えめに表示(記録の保存はステップ5)

設計原則(仕様§3-3):
  - 距離レベルの数値・メーター・進捗バーは出さない(情報を秘める)。変化は「音」で伝える。
  - 「逃げた」は罰ではなく自然現象。安全モードは作らない。
"""
from __future__ import annotations
import json
import base64
import concurrent.futures
import streamlit as st
import streamlit.components.v1 as components
import xc_client


_COMPONENT_HEIGHT = 175
_MAX_BIRDS = 4  # 同時再生する最大羽数


@st.cache_data(show_spinner=False)
def _get_audio_b64(scientific_name: str) -> str | None:
    """鳴き声mp3をbase64文字列で返す。ダウンロード済みならキャッシュから即返す。"""
    path = xc_client.download_audio(scientific_name)
    if path and path.exists():
        return base64.b64encode(path.read_bytes()).decode("ascii")
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
    音源が1羽も取れない場合は return し、既存のハーモニーボタンに委ねる。
    """
    if not resident_ids:
        return
    if not xc_client.is_enabled():
        return

    # 音源を並列フェッチ(最大 _MAX_BIRDS 羽分)
    candidates = [
        (bid, birds_data[bid])
        for bid in resident_ids
        if bid in birds_data and birds_data[bid].get("scientific")
    ][:_MAX_BIRDS * 2]  # 余裕を持って候補を多めに取る

    birds = []
    with st.spinner(""):
        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_BIRDS) as ex:
            futures = {ex.submit(_fetch_bird_audio, c): c[0] for c in candidates}
            for future in concurrent.futures.as_completed(futures):
                bid, b64 = future.result()
                if b64 and len(birds) < _MAX_BIRDS:
                    bird = birds_data[bid]
                    birds.append({
                        "id": bid,
                        "name": bird.get("name", bid),
                        "color": bird.get("color", "#888"),
                        "wariness": float(bird.get("wariness", 0.5)),
                        "b64": b64,
                    })

    if not birds:
        return

    # 元の順序(resident_ids の並び)を維持する
    id_order = {bid: i for i, bid in enumerate(resident_ids)}
    birds.sort(key=lambda b: id_order.get(b["id"], 999))

    n = len(birds)
    names_text = "、".join(b["name"] for b in birds)
    birds_meta = [{"name": b["name"], "wariness": b["wariness"]} for b in birds]
    birds_json = json.dumps(birds_meta, ensure_ascii=False)

    audio_tags = "".join(
        f'<audio id="rite_audio_{i}" preload="auto" loop style="display:none">'
        f'<source src="data:audio/mp3;base64,{b["b64"]}" type="audio/mp3"></audio>'
        for i, b in enumerate(birds)
    )

    html = f"""
    {audio_tags}
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
        <div id="rite_met" style="
            margin-top: 10px; min-height: 18px;
            color: #5a7a5a; font-size: 0.82em;
        "></div>
    </div>
    <script>
    (function() {{
        const BIRDS = {birds_json};
        const btn   = document.getElementById('rite_btn');
        const metEl = document.getElementById('rite_met');

        // 距離ごとの音響パラメータ(gain=音量, freq=ローパス遮断, wet=エコー量)
        const D = {{
            far:  {{ gain: 0.05, freq: 450,  wet: 0.45 }},
            mid:  {{ gain: 0.45, freq: 2200, wet: 0.15 }},
            near: {{ gain: 1.00, freq: 12000, wet: 0.02 }},
            gone: {{ gain: 0.0,  freq: 400,  wet: 0.0  }}
        }};
        const RAMP     = 2.5;    // 距離変化にかける秒数(長めにして変化を体感しやすく)
        const STEP_MS  = 4000;   // 状態遷移チェック間隔(ms)
        const WARY_MS  = 5000;   // 警戒モード持続時間(ms)
        const SPOOK_P  = 0.18;   // 各ステップで「突然の驚き」が起きる確率

        let ctx = null, running = false, timer = null, waryUntil = 0;
        const nodes = [];
        const met = new Set();

        function buildNode(i) {{
            const audioEl = document.getElementById('rite_audio_' + i);
            const src    = ctx.createMediaElementSource(audioEl);
            const filter = ctx.createBiquadFilter();  filter.type = 'lowpass';
            const gain   = ctx.createGain();
            const delay  = ctx.createDelay(1.0);      delay.delayTime.value = 0.28;
            const fb     = ctx.createGain();          fb.gain.value = 0.32;
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

        function applyDist(nd, dist) {{
            const p = D[dist];
            ramp(nd.gain.gain, p.gain);
            ramp(nd.filter.frequency, p.freq);
            ramp(nd.wet.gain, p.wet);
            nd.dist = dist;
        }}

        function markMet(i) {{
            if (met.has(i)) return;
            met.add(i);
            metEl.textContent = '🪶 出会えた鳥: ' +
                [...met].map(j => BIRDS[j].name).join('、');
        }}

        function step() {{
            // 突然の驚き: ランダムで一時的に警戒モードへ(ユーザー操作なしでも体験できる)
            if (Math.random() < SPOOK_P) {{
                waryUntil = Math.max(waryUntil, Date.now() + 2500);
            }}
            const wary = Date.now() < waryUntil;
            for (let i = 0; i < nodes.length; i++) {{
                const nd = nodes[i];
                if (nd.dist === 'gone') continue;
                const w = BIRDS[i].wariness, r = Math.random();
                if (wary) {{
                    // 警戒モード: 遠ざかる/消える
                    if      (nd.dist === 'far'  && r < 0.30) applyDist(nd, 'gone');
                    else if (nd.dist === 'mid'  && r < 0.45) applyDist(nd, 'far');
                    else if (nd.dist === 'near' && r < 0.55) applyDist(nd, 'mid');
                }} else {{
                    if (nd.dist === 'far') {{
                        if      (r < 0.22) applyDist(nd, 'mid');
                        else if (r < 0.27) applyDist(nd, 'gone');
                    }} else if (nd.dist === 'mid') {{
                        const pNear = 0.18 * (1 - w * 0.8);
                        if      (r < pNear)          {{ applyDist(nd, 'near'); markMet(i); }}
                        else if (r < pNear + 0.04)   applyDist(nd, 'gone');
                    }} else if (nd.dist === 'near') {{
                        if      (r < 0.10) applyDist(nd, 'mid');
                        else if (r < 0.12) applyDist(nd, 'gone');
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
                applyDist(nd, 'far');
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
        }}

        btn.addEventListener('click', function() {{
            if (running) {{ stop(); }}
            else if (ctx) {{ ctx.resume(); playAll(); startRunning(); }}
            else {{ start(); }}
        }});

        // iframe内のユーザー操作 → 警戒モード(ボタン自体のクリックは除外)
        ['pointerdown', 'touchstart', 'wheel', 'keydown'].forEach(ev =>
            document.addEventListener(ev, function(e) {{
                if (running && e.target !== btn) waryUntil = Date.now() + WARY_MS;
            }}, {{ passive: true }})
        );
    }})();
    </script>
    """

    components.html(html, height=_COMPONENT_HEIGHT)
