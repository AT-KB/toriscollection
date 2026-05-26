"""
ritual.py - 鳥たちのコーラス UI (ステップ5a: スプライト表示 + 距離による視覚変化)

これまでの積み上げ:
  - ステップ3: 「♪ 耳を澄ます」で音を鳴らす(自動再生制限の突破)
  - ステップ4: 最大4羽を同時再生し、距離で音量・ローパス・エコーを変化
  - ステップ4b: 並列ロード・より鮮明なフェード・ランダム警戒

ステップ5aの中身:
  - 各鳥のドット絵スプライト(designbird/<id>.png)を「情景」に表示
  - 距離状態に応じてスプライトの大きさ・透明度・前後位置を滑らかに変える
      遠 = 小さく薄く奥 / 中 = 中くらい / 近 = 大きくはっきり手前 / 不在 = 消える
  - 音(主)と視覚(副)を同じ距離状態で同期させる(仕様§3-4)
  - 近距離まで来た鳥は「出会えた鳥」として控えめに表示

ステップ5bの中身(今回):
  - 儀式終了時(「終わる」/他タブへ移動)に、近距離まで来た鳥を観察記録として保存
  - JS→Python は top window のクエリパラメータ ?ritual_obs=id1,id2 で渡す
    (components.html は値を返せないため。srcdoc iframe は親と同一オリジン)
  - app.py がパラメータを読んで observations シートに保存し、図鑑に蓄積する

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
import xc_client


_COMPONENT_HEIGHT = 330
_MAX_BIRDS = 4  # 同時再生する最大羽数
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
                        "sprite": _get_sprite_b64(bid),
                    })

    if not birds:
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

    # 情景に並べる鳥スプライト(横方向に等間隔で配置)。
    # 各鳥は wrapper(距離=大きさ・透明度・前後)+ 内側img(ふわふわ上下のbob)の二層構造。
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
        // 距離ごとの見た目(scale=大きさ, opacity=濃さ, top=縦位置%。下ほど手前)
        const V = {{
            far:  {{ scale: 0.5,  opacity: 0.35, top: 8  }},
            mid:  {{ scale: 0.8,  opacity: 0.7,  top: 32 }},
            near: {{ scale: 1.15, opacity: 1.0,  top: 54 }},
            gone: {{ scale: 0.4,  opacity: 0.0,  top: 4  }}
        }};
        const RAMP     = 2.5;    // 距離変化にかける秒数
        const STEP_MS  = 4000;   // 状態遷移チェック間隔(ms)
        const WARY_MS  = 5000;   // 警戒モード持続時間(ms)
        const SPOOK_P  = 0.18;   // 各ステップで「突然の驚き」が起きる確率

        let ctx = null, running = false, timer = null, waryUntil = 0;
        let saved = false;       // 観察記録を二重送信しないためのフラグ
        const nodes = [];
        const sprites = [];
        const met = new Set();   // 近距離まで来た(=観察できた)鳥のindex

        // 儀式終了時に、出会えた鳥を top window のクエリパラメータで Python に渡す。
        // top.location を書き換えるとアプリ全体がリロードされ、app.py が保存する。
        function saveObservations() {{
            if (saved || met.size === 0) return;
            saved = true;
            const ids = [...met].map(j => BIRDS[j].id).join(',');
            try {{
                const url = new URL(window.top.location.href);
                url.searchParams.set('ritual_obs', ids);
                window.top.location.href = url.toString();
            }} catch (e) {{ /* クロスオリジン等で失敗したら静かに諦める */ }}
        }}

        for (let i = 0; i < BIRDS.length; i++) {{
            sprites.push(document.getElementById('rite_bird_' + i));
        }}

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

        function applyVisual(i, dist) {{
            const sp = sprites[i];
            if (!sp) return;
            const v = V[dist];
            sp.style.top = v.top + '%';
            sp.style.opacity = v.opacity;
            sp.style.transform = 'translate(-50%,0) scale(' + v.scale + ')';
            sp.style.zIndex = Math.round(v.top);  // 手前の鳥を前面に
        }}

        function applyDist(nd, i, dist) {{
            const p = D[dist];
            ramp(nd.gain.gain, p.gain);
            ramp(nd.filter.frequency, p.freq);
            ramp(nd.wet.gain, p.wet);
            nd.dist = dist;
            applyVisual(i, dist);
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

        // 他タブ/他アプリへ移った時も儀式終了とみなして記録する(仕様§4-5)
        document.addEventListener('visibilitychange', function() {{
            if (document.hidden && running) saveObservations();
        }});

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
