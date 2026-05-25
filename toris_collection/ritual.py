"""
ritual.py - 鳥たちのコーラス UI (ステップ3: 音を鳴らす)

ステップ3の変更点:
  - ボタンを押すと1羽分の鳴き声が実際に鳴る
  - base64埋め込みなのでブラウザのautoplay制限をボタンクリックで突破
  - 表示名を「♪ 鳥たちのコーラス」に統一(ステップ2の「今、ここにいる鳥たち」を廃止)
  - デバッグ用ステータスボックスを削除
  - 距離遷移・複数同時再生はステップ4以降
"""
from __future__ import annotations
import base64
import streamlit as st
import streamlit.components.v1 as components
import xc_client


_COMPONENT_HEIGHT = 130


@st.cache_data(show_spinner=False)
def _get_audio_b64(scientific_name: str) -> str | None:
    """鳴き声mp3をbase64文字列で返す。ダウンロード済みならキャッシュから即返す。"""
    path = xc_client.download_audio(scientific_name)
    if path and path.exists():
        return base64.b64encode(path.read_bytes()).decode("ascii")
    return None


def render_ritual(resident_ids, biome_id: str, birds_data: dict):
    """
    鳥たちのコーラスUIをホームタブに描画する。

    ステップ3: ボタンを押すと滞在鳥の中で最初に音源が取れた1羽の鳴き声を再生する。
    音源がない場合(xeno-canto無効 or ダウンロード失敗)はそのまま return し、
    既存のハーモニーボタンに委ねる。
    """
    if not resident_ids:
        return

    if not xc_client.is_enabled():
        return

    rite_birds = []
    for bid in resident_ids:
        bird = birds_data.get(bid, {})
        rite_birds.append({
            "id": bid,
            "name": bird.get("name", bid),
            "color": bird.get("color", "#888"),
            "wariness": bird.get("wariness", 0.5),
            "scientific": bird.get("scientific", ""),
        })

    n = len(rite_birds)
    names_text = "、".join(b["name"] for b in rite_birds)

    # 1羽分の音源を取得(キャッシュ済みなら即座に返る)
    audio_b64 = None
    with st.spinner(""):
        for b in rite_birds:
            sci = b.get("scientific", "")
            if sci:
                audio_b64 = _get_audio_b64(sci)
                if audio_b64:
                    break

    # 音源がなければ旧ハーモニーに委ねる
    if audio_b64 is None:
        return

    html = f"""
    <audio id="rite_audio" preload="auto" style="display:none">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
    </audio>
    <div style="
        background: linear-gradient(180deg, #f7faf2 0%, #eef4e6 100%);
        padding: 16px 20px;
        border-radius: 12px;
        border-left: 4px solid #7ba87b;
        margin-bottom: 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
        <div style="display: flex; align-items: center; gap: 14px;">
            <button id="rite_btn" style="
                background: #cfd9b8;
                color: #3a5a3a;
                border: none;
                padding: 12px 22px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 1em;
                font-weight: 600;
                min-width: 140px;
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
    </div>
    <script>
    (function() {{
        const btn   = document.getElementById('rite_btn');
        const audio = document.getElementById('rite_audio');
        let playing = false;

        btn.addEventListener('click', function() {{
            if (playing) {{
                audio.pause();
                audio.currentTime = 0;
                btn.textContent    = '♪ 耳を澄ます';
                btn.style.background = '#cfd9b8';
                playing = false;
            }} else {{
                // ユーザー操作直後なのでブラウザのautoplay制限を突破できる
                audio.play()
                    .then(function() {{
                        btn.textContent      = '■ 停止';
                        btn.style.background = '#b8c8a0';
                        playing = true;
                    }})
                    .catch(function(e) {{
                        console.error('play() failed:', e);
                    }});
            }}
        }});

        audio.addEventListener('ended', function() {{
            btn.textContent      = '♪ 耳を澄ます';
            btn.style.background = '#cfd9b8';
            playing = false;
        }});
    }})();
    </script>
    """

    components.html(html, height=_COMPONENT_HEIGHT)
