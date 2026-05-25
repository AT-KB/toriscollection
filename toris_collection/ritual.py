"""
ritual.py - 距離メカニクスの儀式UI(第一段階・骨格版)

役割:
  - ホームタブの最上部に「儀式エリア」を表示する
  - 第一段階の最小版: 「♪ 耳を澄ます」ボタンと、今いる鳥の名前リストのみ
  - 音もタイマーも距離遷移もまだ実装しない(ステップ3以降)

使い方:
  from ritual import render_ritual
  render_ritual(resident_ids, biome_id)

仕様書:
  - DISTANCE_MECHANIC_SPEC.md(音中心版)
  - RITUAL_IMPLEMENTATION_PLAN.md

最終更新: 2026-05-20 (ステップ2: 骨格作成)
"""
from __future__ import annotations
import json
import streamlit as st
import streamlit.components.v1 as components


# 儀式コンポーネントの高さ(px)。骨格段階では小さく、ステップ4以降で広げる
_COMPONENT_HEIGHT = 200


def render_ritual(resident_ids, biome_id: str, birds_data: dict):
    """
    儀式UIをホームタブに描画する。

    Args:
        resident_ids: 今、ここにいる鳥のID集合(set または list)
        biome_id: 現在のバイオームID(例: "kyoto")
        birds_data: BIRDS辞書(各鳥のname, color等の参照用)

    動作:
        - 「♪ 耳を澄ます」ボタンと鳥の名前リストを表示
        - ボタンを押してもまだ何も起きない(ステップ2では骨格のみ)
    """
    if not resident_ids:
        # 滞在鳥がいない場合は儀式エリアを描画しない
        # (ステップ4以降で「今は静かです」のような表示を検討)
        return

    # 鳥データをJSに渡すために整形(ステップ3以降で使う想定だが、今は名前のみ)
    rite_birds = []
    for bid in resident_ids:
        bird = birds_data.get(bid, {})
        rite_birds.append({
            "id": bid,
            "name": bird.get("name", bid),
            "color": bird.get("color", "#888"),
            "wariness": bird.get("wariness", 0.5),
        })

    # JSON文字列にしてHTMLに埋め込む。
    # json.dumps(ensure_ascii=False) で日本語をそのまま埋め込み可能
    rite_birds_json = json.dumps(rite_birds, ensure_ascii=False)

    # 鳥の名前を表示用に結合(骨格段階の確認用)
    names_text = "、".join(b["name"] for b in rite_birds)

    # ============================================================
    # HTMLコンポーネント
    # 骨格段階: ボタン1つ + 名前リスト + ステップ確認用のステータス表示
    # ============================================================
    html = f"""
    <div id="rite_container" style="
        background: linear-gradient(180deg, #f7faf2 0%, #eef4e6 100%);
        padding: 16px 20px;
        border-radius: 12px;
        border-left: 4px solid #7ba87b;
        margin-bottom: 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
        <div style="display: flex; align-items: center; gap: 14px;">
            <button id="rite_start_btn" style="
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
                    今、ここにいる鳥たち({len(rite_birds)}羽)
                </div>
                <div style="color: #888; font-size: 0.82em; margin-top: 3px;">
                    {names_text}
                </div>
            </div>
        </div>
        <div id="rite_status" style="
            margin-top: 10px;
            padding: 8px 12px;
            background: #fff;
            border-radius: 6px;
            font-size: 0.78em;
            color: #888;
            font-family: monospace;
        ">
            ステータス: 待機中(ボタンが押されていません)
        </div>
    </div>
    <script>
    (function() {{
        // ステップ2: 骨格のみ。ボタン押下を検知してステータス表示を変えるだけ
        const RITE_BIRDS = {rite_birds_json};
        const btn = document.getElementById('rite_start_btn');
        const status = document.getElementById('rite_status');
        let started = false;

        btn.addEventListener('click', function() {{
            if (started) return;  // 二重起動防止
            started = true;
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'default';
            status.textContent = 'ステータス: 開始済み(ステップ2では音は鳴りません。' +
                                 RITE_BIRDS.length + '羽のデータを受け取りました)';
            status.style.color = '#3a8a3a';
            // ステップ3以降: ここで AudioContext を作成、音を再生開始
            console.log('Rite started. Birds:', RITE_BIRDS);
        }});
    }})();
    </script>
    """

    components.html(html, height=_COMPONENT_HEIGHT)
