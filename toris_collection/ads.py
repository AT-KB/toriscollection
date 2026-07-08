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
"""
from __future__ import annotations


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
