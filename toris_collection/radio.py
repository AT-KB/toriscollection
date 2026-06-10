"""
庭のラジオ - 観察済みの鳥たちが奏でるアンビエントプレイヤー

観察した鳥だけが鳴く。鳴く鳥が多いほど豊かなコーラスになる。
捕まえる仕組みはない。ただ聴く。

季節:  アプリ内時間で2週ごとに季節が変わる(8週サイクル)。
      渡り鳥はいない季節はラジオから消える。
距離感: 観察回数が多い鳥ほど手前(クリア)に聞こえる。
"""
from __future__ import annotations
import json
import base64
import concurrent.futures
from datetime import date
from pathlib import Path

import streamlit as st

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
                          max_n: int = 3) -> list[tuple[str, str]]:
    """(base64, 鳴き方) のリスト。最大合計 1.5MB base64。"""
    if xc_client is None:
        return []
    paths = xc_client.download_audio_variants(scientific_name, max_n=max_n)
    out: list[tuple[str, str]] = []
    total = 0
    _BUDGET = 2_000_000
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
    p = _SPRITE_DIR / f"{bird_id}.png"
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
) -> None:
    """
    庭のラジオを描画する。

    biome_id:      プレイヤーの現在のバイオーム(デフォルト選択に使う)
    observed:      観察記録 {bird_id: {count, first, last}}
    birds_data:    BIRDS 辞書
    selected_biome: ユーザーが選んだバイオーム(None = biome_id を使う)
    """
    if xc_client is None or not xc_client.is_enabled():
        st.info("xeno-canto APIキーが設定されていません。鳴き声機能を有効にするには xc_api_key.txt を追加してください。")
        return

    season = current_app_season()
    season_meta = _SEASON_META[season]
    weeks_left = weeks_until_next_season()

    # ── バイオーム選択 ──────────────────────────────────────────
    biome_labels = {"kyoto": "🏯 京都", "sydney": "🦘 シドニー", "charlotte": "🌳 シャーロット"}
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
            key="radio_biome_select",
            label_visibility="collapsed",
        )
    with col_time:
        time_options = ["朝 (4-8時)", "昼 (10-15時)", "夕 (16-19時)", "夜 (20-3時)"]
        time_hours  = [6, 12, 17, 22]
        t_idx = st.selectbox(
            "時間帯",
            options=range(len(time_options)),
            format_func=lambda i: time_options[i],
            key="radio_time_select",
            label_visibility="collapsed",
        )
    sim_hour = time_hours[t_idx]
    # 季節表示はタブ見出し(app.py)が出すのでここでは出さない
    _ = weeks_left

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

    # ── 音源取得(上位 _MAX_RADIO_BIRDS 羽まで) ────────────────
    candidates = [
        (bid, birds_data[bid]) for bid in in_season
        if birds_data[bid].get("scientific")
    ][:_MAX_RADIO_BIRDS * 2]

    if "radio_ready" not in st.session_state:
        st.session_state.radio_ready = False

    if not st.session_state.radio_ready:
        # 開始前: 鳥チップ一覧(在籍+季節外)で「誰が鳴けるか」を見せる
        _render_bird_chips(in_season, out_season, observed, birds_data, season)
        total_observed = len(observed_in_biome)
        st.markdown(
            f'<div style="color:#5a7a5a;font-size:0.85em;">'
            f'観察済み {total_observed} 羽 · 今の季節に {len(in_season)} 羽が鳴ける</div>',
            unsafe_allow_html=True,
        )
        if st.button("🎙 ラジオを始める", key="radio_start_btn"):
            st.session_state.radio_ready = True
            st.rerun()
        return

    # 開始後: 在籍チップは iframe 内(♪付き)に出るので、季節外だけ表示
    if out_season:
        _render_bird_chips([], out_season, observed, birds_data, season)

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
                        "nv":     len(b64s),
                        "vt":     [t for _, t in b64s],
                    })

    if not birds:
        st.info("音源を取得できませんでした。")
        return

    # 観察回数 多い順にソート
    birds.sort(key=lambda b: -b["count"])

    # ── HTML/JS レンダリング ───────────────────────────────────
    _render_radio_iframe(birds, sim_hour, chosen, season, season_meta)


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


def _render_radio_iframe(
    birds: list[dict], sim_hour: int,
    biome_id: str, season: str, season_meta: dict,
) -> None:
    """Web Audio ベースのラジオ iframe を描画する。"""

    n = len(birds)
    birds_meta = [
        {"id": b["id"], "name": b["name"], "nv": b["nv"],
         "vt": b["vt"], "depth": b["depth"]}
        for b in birds
    ]
    birds_json = json.dumps(birds_meta, ensure_ascii=False)

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
        f'<span class="ra_note_{i}" style="font-size:0.9em;color:#7ab040;display:none;">♪</span>'
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
          <span style="font-weight:400;">{n}羽</span>
        </div>
      </div>
      <div id="ra_chips">{sprite_divs}</div>
    </div>

    <script>
    (function() {{
        const BIRDS = {birds_json};
        const HAS_AMBIENT = {has_ambient};
        const SIM_HOUR = {sim_hour};
        const n = BIRDS.length;
        const btn = document.getElementById('ra_btn');

        // 音響パラメータ(ritual.py と同じ)
        const D = {{
            b3: {{ gain: 0.58, freq: 4200, wet: 0.20 }},
            b2: {{ gain: 0.90, freq: 8000, wet: 0.09 }},
            b1: {{ gain: 1.25, freq: 12000, wet: 0.01 }},
        }};

        let ctx = null, master = null, reverb = null;
        let running = false, rafId = null;
        const nodes = [];

        // AGC / 呼応の状態
        const peakRMS   = [];
        const phraseOn  = [];
        const silentF   = [];
        let activeIdx   = 0;
        let activeSince = 0;
        const AGC_TARGET = 0.065, AGC_MIN = 0.5, AGC_MAX = 3.5;
        const CALL_FLOOR = 0.12;
        const SILENT_NEED = 12;
        const MIN_SOLO_MS = 5000;
        const GATE_THRESH = 0.020, GATE_FLOOR = 0.12;

        // HRTF / StereoPanner
        const DEPTH_Z = {{ b3: -7, b2: -3.5, b1: -1.2 }};
        function makePanner() {{
            try {{
                const p = new PannerNode(ctx, {{
                    panningModel:'HRTF', distanceModel:'linear',
                    refDistance:1, maxDistance:30, rolloffFactor:0
                }});
                return {{ node: p, hrtf: true }};
            }} catch(e) {{
                return {{ node: ctx.createStereoPanner(), hrtf: false }};
            }}
        }}
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
            const h = SIM_HOUR;
            if (h >= 4 && h < 10)  return 'song';
            if (h >= 16 || h < 4)  return 'call';
            return null;
        }}
        function pickVariant(i, exclude) {{
            const vt = BIRDS[i].vt || [];
            const pref = preferredType();
            const pool = [];
            for (let v = 0; v < vt.length; v++) {{
                if (v === exclude) continue;
                const w = (pref && vt[v] === pref) ? 3 : 1;
                for (let k = 0; k < w; k++) pool.push(v);
            }}
            if (!pool.length) return exclude >= 0 ? exclude : 0;
            return pool[Math.floor(Math.random() * pool.length)];
        }}

        function makeReverbIR() {{
            const dur = 1.6, len = Math.floor(ctx.sampleRate * dur);
            const ir = ctx.createBuffer(2, len, ctx.sampleRate);
            for (let ch = 0; ch < 2; ch++) {{
                const d = ir.getChannelData(ch);
                for (let k = 0; k < len; k++) {{
                    d[k] = (Math.random()*2-1) * Math.pow(1 - k/len, 2.6);
                }}
                [0.013, 0.029, 0.051, 0.078].forEach((tt, idx) => {{
                    const p = Math.floor(tt * ctx.sampleRate);
                    if (p < len) d[p] += (0.5 - idx*0.1) * (ch===0 ? 1 : 0.8);
                }});
            }}
            return ir;
        }}

        function makeNoiseBuffer(brown) {{
            const len = ctx.sampleRate * 4;
            const buf = ctx.createBuffer(1, len, ctx.sampleRate);
            const data = buf.getChannelData(0);
            let last = 0;
            for (let i = 0; i < len; i++) {{
                const w = Math.random()*2-1;
                if (brown) {{ last = (last + 0.02*w)/1.02; data[i] = last*3.2; }}
                else data[i] = w;
            }}
            return buf;
        }}

        function buildAmbient() {{
            const ambEl = document.getElementById('ra_ambient');
            if (HAS_AMBIENT && ambEl) {{
                const src = ctx.createMediaElementSource(ambEl);
                const lp  = ctx.createBiquadFilter(); lp.type='lowpass'; lp.frequency.value=6000;
                const ag  = ctx.createGain(); ag.gain.value=0;
                src.connect(lp); lp.connect(ag); ag.connect(master);
                ambEl.play().catch(()=>{{}});
                ag.gain.setTargetAtTime(0.22, ctx.currentTime, 3.5);
                return ag;
            }}
            const wind = ctx.createBufferSource(); wind.buffer = makeNoiseBuffer(true); wind.loop=true;
            const wlp  = ctx.createBiquadFilter(); wlp.type='lowpass'; wlp.frequency.value=420;
            const wg   = ctx.createGain(); wg.gain.value=0;
            wind.connect(wlp); wlp.connect(wg); wg.connect(master);
            const lfo  = ctx.createOscillator(); lfo.frequency.value=0.06;
            const lfoG = ctx.createGain(); lfoG.gain.value=200;
            lfo.connect(lfoG); lfoG.connect(wlp.frequency);
            const air  = ctx.createBufferSource(); air.buffer = makeNoiseBuffer(false); air.loop=true;
            const abp  = ctx.createBiquadFilter(); abp.type='bandpass'; abp.frequency.value=2600;
            const ag2  = ctx.createGain(); ag2.gain.value=0;
            air.connect(abp); abp.connect(ag2); ag2.connect(master);
            wind.start(); air.start(); lfo.start();
            const t = ctx.currentTime;
            wg.gain.setTargetAtTime(0.075, t, 2.5);
            ag2.gain.setTargetAtTime(0.012, t, 2.5);
            return wg;
        }}

        function buildNode(i) {{
            const depth = BIRDS[i].depth || 'b3';
            const nv    = BIRDS[i].nv   || 1;
            const els   = [];
            const hp = ctx.createBiquadFilter(); hp.type='highpass'; hp.frequency.value=520;
            for (let v = 0; v < nv; v++) {{
                const el = document.getElementById('ra_' + i + '_' + v);
                if (el) {{ els.push(el); ctx.createMediaElementSource(el).connect(hp); }}
            }}
            const filter  = ctx.createBiquadFilter(); filter.type='lowpass';
            const gate    = ctx.createGain(); gate.gain.value=1;
            const agcGain = ctx.createGain(); agcGain.gain.value=1;
            const gain    = ctx.createGain();
            const chGain  = ctx.createGain(); chGain.gain.value=1;
            const pan     = makePanner();
            const wet     = ctx.createGain();
            const ana     = ctx.createAnalyser(); ana.fftSize=512;

            hp.connect(filter); filter.connect(ana); filter.connect(gate);
            gate.connect(agcGain); agcGain.connect(gain);
            gain.connect(chGain);
            chGain.connect(pan.node); pan.node.connect(master);
            chGain.connect(wet); wet.connect(reverb);

            gain.gain.value        = D[depth].gain;
            filter.frequency.value = D[depth].freq;
            wet.gain.value         = D[depth].wet;

            // 初期水平位置: 均等間隔
            const left = 20 + (i / Math.max(n-1, 1)) * 60;
            setPan({{ pan, depth }}, left);

            const cur = els.length > 1 ? pickVariant(i, -1) : 0;
            return {{ els, cur, filter, gain, agcGain, chGain, wet, gate, ana,
                      pan, depth, buf: new Float32Array(ana.fftSize) }};
        }}

        function updateChip(i, active) {{
            const chip = document.getElementById('ra_chip_' + i);
            const note = chip ? chip.querySelector('.ra_note_' + i) : null;
            if (chip) chip.classList.toggle('ra_active', active);
            if (note) note.style.display = active ? 'inline' : 'none';
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

                // ① ノイズゲート
                nd.gate.gain.setTargetAtTime(rms < GATE_THRESH ? GATE_FLOOR : 1.0, t, 0.06);

                // ② AGC
                if (rms > GATE_THRESH) peakRMS[i] = peakRMS[i]*0.92 + rms*0.08;
                else                   peakRMS[i] *= 0.9998;
                const agcT = Math.min(Math.max(AGC_TARGET / Math.max(peakRMS[i], 0.003),
                                               AGC_MIN), AGC_MAX);
                nd.agcGain.gain.setTargetAtTime(agcT, t, 3.0);

                // UI: 鳴いている鳥のチップを光らせる
                const isSolo = (i === activeIdx);
                const audible = rms > GATE_THRESH * 0.5;
                updateChip(i, isSolo && audible);

                // ③ 呼応
                if (i === activeIdx) {{
                    if (rms > GATE_THRESH * 0.6) {{
                        phraseOn[i] = true; silentF[i] = 0;
                    }} else if (phraseOn[i]) {{
                        silentF[i]++;
                        if (silentF[i] === SILENT_NEED
                                && Date.now() - activeSince > MIN_SOLO_MS
                                && Math.random() < 0.40) {{
                            const cands = Array.from({{length: nodes.length}}, (_, j) => j).filter(j => j !== i);
                            if (cands.length > 0) {{
                                const next = cands[Math.floor(Math.random() * cands.length)];
                                nd.chGain.gain.setTargetAtTime(CALL_FLOOR, t, 1.5);
                                nodes[next].chGain.gain.setTargetAtTime(1.0, t+0.35, 0.8);
                                activeIdx = next; activeSince = Date.now();
                                phraseOn[next] = false; silentF[next] = 0;
                            }}
                        }}
                    }}
                }}
            }}
            rafId = requestAnimationFrame(gateTick);
        }}

        function start() {{
            ctx    = new (window.AudioContext || window.webkitAudioContext)();
            master = ctx.createDynamicsCompressor();
            master.threshold.value=-10; master.knee.value=10;
            master.ratio.value=4; master.attack.value=0.003; master.release.value=0.25;
            master.connect(ctx.destination);
            reverb = ctx.createConvolver(); reverb.buffer = makeReverbIR();
            const rvRet = ctx.createGain(); rvRet.gain.value=0.9;
            reverb.connect(rvRet); rvRet.connect(master);
            buildAmbient();

            for (let i = 0; i < n; i++) {{
                peakRMS.push(0.01); phraseOn.push(false); silentF.push(0);
                const nd = buildNode(i);
                nodes.push(nd);
                // 1羽目をフォアグラウンド、他はバックグラウンド
                if (i > 0) nd.chGain.gain.setValueAtTime(CALL_FLOOR, ctx.currentTime);
            }}
            activeIdx = 0; activeSince = Date.now();

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

    st.iframe(html, height=_COMPONENT_HEIGHT)
