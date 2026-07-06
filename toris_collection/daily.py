"""
daily.py - 今日の庭(Wordle 型・1日1回・全員共通の入口)

■ 方針(交渉不能・軸 §1-1)
  「1日1回しかできない」= 強迫が構造的に不可能。これは反グラインド軸と完全に一致する。
  日付シードで全ユーザー共通の「今日の一羽」を決める。順位もノルマもない。
  ただ「今日はこの声が庭にいる」。まだ会っていなければ、会いに行く誘い(=儀式へ。
  ループを閉じる)。単位は競争ではなく「今日という共有の瞬間」。

  Wordle の発明(1日1個・共有・反 binge)を、アンビエントに薄く重ねる。
  別画面のクイズにはしない(やり過ぎるとラジオが死ぬ)。ラジオの上に一筆だけ。

  ねらい: 不在ループが空振りする再訪(留守が短く何も起きない日)でも、
  「今日」だけは必ず新しい——戻る理由の最後のピースを埋める。

集計/選定ロジックは I/O から切り離した純粋関数。テスト可能。
"""
from __future__ import annotations
from datetime import date


def daily_seed(today: date | None = None) -> int:
    """日付から決定的な整数シードを作る(全ユーザー共通)。"""
    today = today or date.today()
    return today.toordinal()


def todays_bird(biome_id: str, birds_data: dict,
                today: date | None = None) -> str | None:
    """その土地・その日の「今日の一羽」を決定的に選ぶ。

    日付＋土地でシードするので、同じ日・同じ土地なら全ユーザーで同一の鳥になる
    (=共有の瞬間)。その土地に鳥がいなければ None。
    """
    candidates = sorted(
        bid for bid, b in birds_data.items()
        if biome_id in b.get("biome_pref", [])
    )
    if not candidates:
        return None
    seed = daily_seed(today) + sum(ord(c) for c in biome_id)
    return candidates[seed % len(candidates)]


def is_met(bird_id: str, observed: dict) -> bool:
    """その鳥に既に会っているか(observed に count>0 で記録があるか)。"""
    rec = observed.get(bird_id) if observed else None
    return bool(rec and rec.get("count", 0) > 0)


# ── UI(streamlit 依存。ロジックは上の純粋関数に閉じている) ──────────

def render_todays_garden(biome_id: str, birds_data: dict, observed: dict,
                         biome_label: str = "",
                         sprite_html_fn=None, audio_render_fn=None) -> None:
    """ラジオタブ上部に「今日の一羽」を一筆だけ描く。読み取り専用・no-fail。

    Args:
        sprite_html_fn: (bird_id, size_px, fallback_emoji) -> HTML文字列 を
            返す任意のコールバック(通常は app.py の render_bird_sprite_html)。
            渡された場合のみドット絵サムネイルを添える。既存アセットの流用のみで、
            新規アセットは要求しない。
        audio_render_fn: (bird_id, bird_dict) -> None を実行する任意のコールバック
            (通常は app.py の render_bird_audio)。渡された場合のみ、その場で
            鳴き声を試聴するボタンを添える。鳴き声のアクセスは元から無料であり、
            ここで課金をゲートすることはしない(交渉不能の原則3)。
        いずれも渡さなければ従来どおりテキストと帯のみの表示になる
        (後方互換・呼び出し側の変更は任意)。

    ■ 方針(daily.py 冒頭の設計思想を厳守)
        別画面のクイズにはしない・ゲーム化しない。追加するのは「見た目」と
        「試聴」のみで、新しい判定ロジック・連続日数条件は一切足さない。
    """
    import streamlit as st

    bid = todays_bird(biome_id, birds_data)
    if not bid:
        return
    bird = birds_data[bid]
    name = bird.get("name", bid)
    color = bird.get("color", "#7ba87b")
    met = is_met(bid, observed)

    # 生態の一言(ギルド。なぜこの声かを軽く)
    eco = ""
    try:
        import ecology
        g = ecology.guild(bid, birds_data)
        _, glabel = ecology.GUILD_LABELS.get(g, ecology.GUILD_LABELS["other"])
        eco = f"{glabel}仲間。"
    except Exception:
        eco = ""

    where = biome_label or biome_id
    if met:
        invite = "🎙 あなたのラジオでも、今日はきっと鳴いています。"
    else:
        invite = "まだ会っていません。会いに行くと、ラジオに加わります。"

    card_html = (
        f'<div style="background:linear-gradient(180deg,#fcfaf3,#f4f0e2);'
        f'border-left:4px solid {color};border-radius:10px;'
        f'padding:10px 14px;margin:2px 0 12px;">'
        f'<div style="font-size:0.78em;color:#a08a50;letter-spacing:0.05em;">'
        f'🌅 今日の庭 — {where}</div>'
        f'<div style="font-size:1.05em;color:#3a4a2a;font-weight:600;margin:2px 0;">'
        f'{name}</div>'
        f'<div style="font-size:0.84em;color:#6a7a5a;">{eco}{invite}</div>'
        f'</div>'
    )

    if sprite_html_fn:
        try:
            sprite_html = sprite_html_fn(bid, size_px=56, fallback_emoji="🐦")
        except Exception:
            sprite_html = None
        if sprite_html:
            cols = st.columns([1, 5])
            with cols[0]:
                st.markdown(
                    f'<div style="margin-top:6px;">{sprite_html}</div>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.markdown(card_html, unsafe_allow_html=True)

    if audio_render_fn:
        try:
            audio_render_fn(bid, bird)
        except Exception:
            pass
