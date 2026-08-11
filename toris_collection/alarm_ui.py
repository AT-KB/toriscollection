"""alarm_ui.py - 「鳥のさえずりで起きる」目覚ましの設定UI。

設計の根拠は `docs/team/proposals/2026-08-11_目覚まし設計_研究に基づく仕様.md`。
要点だけ再掲する:
  - 鳴らすのは**さえずり(song)のみ**。地鳴き・警戒声(call)は使わない
    (McFarlane ら 2020: 耳障りな音は睡眠慣性を悪化させ、メロディだけが
     注意の脱落を有意に減らした)。
  - 5分かけて 8% から最大音量へ、1羽 → 2羽 → 3羽と加わる(夜明けのコーラス)。

**実際に鳴らすのはネイティブ側**(`BirdAlarmService`)で、ここは時刻と鳥を渡すだけ。
アプリを閉じていても鳴る必要があり、WebView の中では実現できないため。
また Render のコールドスタート(実測22.7秒)に朝いちばんを預けられないので、
音源は APK 同梱のものを使い、サーバーには一切依存しない。

Web版(通常のブラウザ)には `window.AndroidAlarm` が存在しないため、
その場合は設定UIを出さずに案内だけ出す(既存の AndroidWatchdog と同じ設計)。
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from i18n import t

# ネイティブ側 BirdAlarmSounds.KEYS と**同じ順序**にしておくこと。
# 順序がそのまま「夜明けのコーラスで加わる順」になる。
ALARM_BIRDS: list[tuple[str, str]] = [
    ("northern_cardinal", "Northern Cardinal"),
    ("american_robin", "American Robin"),
    ("song_sparrow", "Song Sparrow"),
    ("carolina_wren", "Carolina Wren"),
]


def render_alarm(key_prefix: str = "alarm") -> None:
    """目覚ましの設定UIを描画する。"""
    with st.expander(t("⏰ 鳥の声と起きたい"), expanded=False):
        st.caption(t(
            "選んだ鳥のさえずりが、5分かけて少しずつ大きくなり、"
            "途中でほかの鳥も加わります。いきなり大きな音では起こしません。"
        ))

        col_h, col_m = st.columns(2)
        with col_h:
            hour = st.number_input(t("時"), min_value=0, max_value=23, value=7,
                                   step=1, key=f"{key_prefix}_hour")
        with col_m:
            minute = st.number_input(t("分"), min_value=0, max_value=59, value=0,
                                     step=5, key=f"{key_prefix}_min")

        bird = st.selectbox(
            t("最初に鳴く鳥"),
            options=[b[0] for b in ALARM_BIRDS],
            format_func=lambda k: dict(ALARM_BIRDS)[k],
            key=f"{key_prefix}_bird",
            help=t("さえずり(song)の録音だけを選べるようにしています。"
                   "耳障りな地鳴きで起こさないためです。"),
        )

        c1, c2 = st.columns(2)
        with c1:
            set_it = st.button(t("⏰ この時刻にセット"), use_container_width=True,
                               type="primary", key=f"{key_prefix}_set")
        with c2:
            clear_it = st.button(t("解除する"), use_container_width=True,
                                 key=f"{key_prefix}_clear")

        st.caption(t("※ Android アプリ版でのみ動きます。"
                     "ブラウザ版では設定しても鳴りません。"))

        if set_it:
            _call_native("set", int(hour), int(minute), bird)
        if clear_it:
            _call_native("cancel", 0, 0, "")

        # 現在の設定をネイティブから読み、画面に反映する
        _render_status(key_prefix)


def _call_native(action: str, hour: int, minute: int, bird: str) -> None:
    """ネイティブ側の AndroidAlarm を叩く。

    Web版では `window.AndroidAlarm` が無いので、try/catch で静かに素通りする
    (既存の `_inject_splash_hide()` 等と同じ、片道の注入パターン)。
    """
    payload = json.dumps({"action": action, "hour": hour,
                          "minute": minute, "bird": bird})
    components.html(
        f"""
<script>
(function() {{
  var p = {payload};
  try {{
    var A = window.AndroidAlarm || (window.parent && window.parent.AndroidAlarm);
    if (!A) return;                      // ブラウザ版: 何もしない
    if (p.action === 'set') {{
      var ok = A.setAlarm(p.hour, p.minute, p.bird);
      if (ok === false && A.openExactAlarmSettings) {{
        // Android 12 で「正確なアラーム」が未許可。設定画面へ案内する。
        A.openExactAlarmSettings();
      }}
    }} else {{
      A.cancelAlarm();
    }}
  }} catch (e) {{}}
}})();
</script>
""",
        height=0,
    )


def _render_status(key_prefix: str) -> None:
    """ネイティブが持っている現在の設定を、そのまま画面に出す。"""
    components.html(
        """
<div id="toris_alarm_status"
     style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
            font-size:0.92em; color:#3f5c37; padding:2px 0;"></div>
<script>
(function() {
  var el = document.getElementById('toris_alarm_status');
  try {
    var A = window.AndroidAlarm || (window.parent && window.parent.AndroidAlarm);
    if (!A || !A.getAlarm) {
      el.textContent = '';               // ブラウザ版では何も出さない
      return;
    }
    var s = JSON.parse(A.getAlarm());
    if (s.enabled) {
      var hh = ('0' + s.hour).slice(-2), mm = ('0' + s.minute).slice(-2);
      el.textContent = '⏰ ' + hh + ':' + mm + ' にセットされています';
    } else {
      el.textContent = 'いまは設定されていません';
    }
  } catch (e) { el.textContent = ''; }
})();
</script>
""",
        height=32,
    )
