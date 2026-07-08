"""
ads.py - 広告UIの土台(プレースホルダー)

■ 位置づけ(交渉不能の原則・00_共通サマリ.md)
  - 全画面割り込み広告は絶対に実装しない。
  - 鳥の声・癒し体験(ラジオ)を広告でゲートしない(常に無料)。
  - リワード広告は完全に任意のおまけ。見なくても庭の進み方は一切変わらない。
  - 受動的であること(広告を見ないと不利になる設計にしない)。

■ 実装範囲(2026-07-08時点)
  ここにあるのは配置・表示/非表示ロジックだけの UI プレースホルダー。
  実際の広告配信ネットワーク(AdMob 等)へはまだ接続していない。
  理由: 広告=商用利用となり、xeno-canto の非商用(CC BY-NC 等)録音を
  含んだまま商用化するとライセンス違反になる。ライセンス監査
  (license_audit.py)が完了し、`xc_client.COMMERCIAL_ONLY` を商用可の
  音源だけに絞った状態で運用開始してから、実配信の着手を判断する
  (ROADMAP_GOOGLE_PLAY.md Phase 2 参照)。

  将来ここに実SDKを差し込む際は:
    - render_banner_placeholder() の中身を実SDKのタグ/コンポーネントに置き換える
    - render_reward_ad_button() の disabled/no-op 部分を実際のリワード広告呼び出しに置き換える
  だけで済むよう、呼び出し側(app.py)とはこの2関数のインターフェースだけで疎結合にしてある。

集計/判定ロジックは Streamlit から切り離した純粋関数。テスト可能。

■ 2026-07-08 追記: 広告リワードアイテム拡充
  docs/team/proposals/2026-07-08_広告リワードアイテム拡充案.md に基づき、
  以下2種類の「見ると1日1回だけ受け取れる」リワードを追加した(いずれも完全に任意):
    - 落とし物(mementos)連動リワード: 今日庭に来た鳥から小枝を1個確定付与。
    - 庭アイテム(garden_items.py・6種)配置リワード: 6時間だけ効くおまけを1つ置ける。
  どちらも1日1回のゲートは `has_claimed_today`/`mark_claimed_today`(ISO日付文字列の
  比較、`app._mark_met_today` と同じ「今日=1カウント」パターン)で管理する。
  実際の状態変更(memento付与・アイテム配置)は呼び出し側(app.py)の関数に委譲し、
  ここでは UI と日付ゲートの判定だけを持つ(疎結合を保つ既存方針を踏襲)。
"""
from __future__ import annotations

from datetime import date


def _today_str(today=None) -> str:
    """日付から 'YYYY-MM-DD' 文字列を作る(全ユーザー・全端末で同じ形式)。"""
    return (today or date.today()).isoformat()


def has_claimed_today(session_state, flag_key: str, today=None) -> bool:
    """指定のフラグキーが「今日」既に消費済みかどうか。

    `app._mark_met_today` と同じ「ISO日付文字列を保存し、今日の文字列と比較する」
    パターン(daily.py の「1日1回・全員共通」という設計思想を踏襲)。
    """
    try:
        return session_state.get(flag_key) == _today_str(today)
    except AttributeError:
        return False


def mark_claimed_today(session_state, flag_key: str, today=None) -> None:
    """指定のフラグキーに「今日」の日付文字列を記録する(1日1回ゲートの消費)。"""
    session_state[flag_key] = _today_str(today)


def is_radio_active(session_state) -> bool:
    """ラジオが再生開始状態かどうかを、Python 側から分かる範囲で近似する。

    radio.render_radio() は既定で key_prefix="radio" を使い、ユーザーが
    「🎙 ラジオを始める」ボタンを押すと session_state["radio_ready"] が
    True になる(radio.py 参照)。ラジオは iframe 内 Web Audio で鳴っており、
    庭タブに戻ってもオーディオはバックグラウンドで鳴り続けている可能性が
    あるため、その間は静かなバナーを隠す。

    session_state: st.session_state、またはテスト用の dict 等
                    (`.get(key, default)` を持つもの)。
    """
    try:
        return bool(session_state.get("radio_ready"))
    except AttributeError:
        return False


def render_banner_placeholder(session_state, key_prefix: str = "ads") -> None:
    """ホーム下部の静かなバナー広告のプレースホルダーを描画する。

    ラジオ再生中(is_radio_active）は非表示にする。
    実際の広告SDKは未接続。枠と表示/非表示ロジックのみを検証する目的。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    if is_radio_active(session_state):
        return

    st.markdown(
        "<div style='margin-top:22px;padding:10px 16px;border-radius:8px;"
        "background:#f4f2ec;border:1px dashed #cfc7b0;text-align:center;'>"
        "<span style='color:#9a9078;font-size:0.82em;'>🌾 広告スペース(準備中)</span>"
        "<div style='font-size:0.76em;color:#b0a890;margin-top:2px;'>"
        "実際の広告はまだ配信していません・ラジオ再生中は表示しません"
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_reward_ad_button(key_prefix: str = "ads") -> None:
    """任意のリワード広告ボタンのプレースホルダーを描画する。

    将来「見ると今日だけ珍しい種が来やすくなる」等の一時的なブーストを
    想定しているが、現時点では広告配信を開始していないため、押しても
    ゲーム進行には何の影響も与えないダミー。あくまで完全に任意のおまけで
    あり、見なくても庭の進み方・鳥の声は変わらないことを明示する。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    with st.expander("🎁 応援広告(準備中)", expanded=False):
        st.caption(
            "見ると今日だけ珍しい鳥が来やすくなる……予定の任意広告です。"
            "今はまだ広告配信を始めていません。見ても見なくても、"
            "庭の進み方や鳥の声はいつもどおりです。"
        )
        if st.button(
            "▶ 広告を見る(準備中)",
            key=f"{key_prefix}_reward_btn",
            use_container_width=True,
        ):
            st.info("広告はまだ準備中です。もうしばらくお待ちください。")


def render_twig_reward_button(session_state, residents, birds_data, grant_fn,
                              key_prefix: str = "ads") -> None:
    """落とし物(mementos)連動リワード(1日1回)。

    今日庭に来ている鳥(residents)から1羽選び、小枝(twig)を1個確定付与する。
    実際の付与処理は `grant_fn(bird_id)` に委譲する(app.py 側が mementos の
    session反映・Sheetsへのベストエフォート書き戻しを持つ。ここではUIと
    「1日1回」の日付ゲートだけを扱う)。

    庭に誰も来ていない日はボタンを無効化(選べる鳥がないため)する。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ

    flag_key = "twig_reward_claimed_date"
    with st.expander("🎁 応援広告(今日来た鳥から、小枝をもう一つ)", expanded=False):
        st.caption(
            "見ると、今日庭に来てくれた鳥から、記念の小枝をもう一つもらえます。"
            "見なくても、鳥の声や落とし物のチャンスはいつもどおりです。"
        )
        if has_claimed_today(session_state, flag_key):
            st.caption("✓ 今日はもう受け取りました。また明日。")
            return
        if not residents:
            st.caption("今日はまだ庭に鳥が来ていません。鳥が来てから受け取れます。")
            return

        ids_sorted = sorted(
            residents, key=lambda b: birds_data.get(b, {}).get("name", b)
        )
        choice = st.selectbox(
            "小枝をもらう鳥を選ぶ",
            options=ids_sorted,
            format_func=lambda b: birds_data.get(b, {}).get("name", b),
            key=f"{key_prefix}_twig_bird_choice",
        )
        if st.button(
            "▶ 広告を見て、小枝をもらう",
            key=f"{key_prefix}_twig_reward_btn",
            use_container_width=True,
        ):
            grant_fn(choice)
            mark_claimed_today(session_state, flag_key)
            st.rerun()


def render_garden_item_button(session_state, biome_id, birds_data, place_fn,
                              key_prefix: str = "ads") -> None:
    """庭アイテム(garden_items.py・6種)配置リワード(1日1回・6時間持続)。

    実際の配置処理は `place_fn(item_id)` に委譲する(app.py 側が
    session_state["garden_item_placement"] を更新する)。
    pp数値はユーザーには見せず、`garden_items.ITEMS` の hint/culture_note の
    言葉に翻訳して見せる(提案書§4 UI仕様)。
    """
    import streamlit as st  # 遅延importでロジック部分をstreamlit非依存に保つ
    import garden_items as gi

    flag_key = "garden_item_claimed_date"
    with st.expander("🎁 応援広告(今日の庭アイテムを選ぶ)", expanded=False):
        active = session_state.get("garden_item_placement")
        if gi.is_active(active):
            item = gi.ITEMS.get(active.get("item_id"), {})
            hrs = gi.hours_remaining(active)
            st.caption(
                f"{item.get('emoji', '')} 今は「{item.get('name', '')}」を"
                f"置いています(あと{hrs:.1f}時間)。"
            )
            return
        if has_claimed_today(session_state, flag_key):
            st.caption("✓ 今日はもう1つ選びました。また明日、別のアイテムを選べます。")
            return

        st.caption(
            "見ると、庭に6時間だけ道具を1つ置けます。アメリカの裏庭バードウォッチング"
            "文化の道具を紹介する、今日だけの特別な小窓です。見なくても庭の進み方は"
            "いつもどおりです。"
        )
        for item_id in gi.ITEM_ORDER:
            item = gi.ITEMS[item_id]
            label = f"{item['emoji']} {item['name']}"
            available = gi.is_available(item_id, biome_id, birds_data)
            if available:
                st.markdown(f"**{label}**")
                st.caption(f"{item['hint']} {item['culture_note']}")
                if st.button(
                    f"▶ {label} を置く",
                    key=f"{key_prefix}_item_{item_id}_btn",
                    use_container_width=True,
                ):
                    place_fn(item_id)
                    mark_claimed_today(session_state, flag_key)
                    st.rerun()
            else:
                st.markdown(f"~~{label}~~ (今のこの庭では選べません)")
                st.caption(gi.unavailable_reason(item_id, biome_id, birds_data))
            st.markdown("---")
