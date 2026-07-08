"""
community.py - 集合アトラス(みんなの庭) UI

ユーザー間機能の最小版。HANDOFF §1-1-a / 軸に従う:

  - 匿名・集合・非競争。個人名も順位も出さない。
    「人 × 数」を同じ画面に出さない——これが比較=グラインドの種を作らない不可侵ルール。
  - 単位は「人」ではなく「場所と種」。みんなの観察が集まって、
    どの土地にどの種が訪れているかの"生きた地図"になる(co-creation)。
    iNaturalist/eBird のネットワーク効果の"感触"を、識別ツールにならずに借りる。
  - 既存 Sheets(collection)を読み取り専用で集計するだけ。基盤移行なしの実験。
    火がつくか温度を測るためのもので、点かなければ1タブ消すだけで撤去できる。

集計ロジック(aggregate_atlas)は I/O から切り離した純粋関数。テスト可能。
"""
from __future__ import annotations
from datetime import date, datetime

import streamlit as st


# ── 純粋ロジック(I/O なし・テスト可能) ──────────────────────────────

def _parse_day(iso_str: str):
    """ISO 文字列 → date。失敗時 None。"""
    s = str(iso_str or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None


def _row_count_and_last(row: dict):
    """collection の1行から (visit_count, last_seen_iso) を列名に依存せず推定する。

    collection シートの列順は環境で揺れうるので、tester_id/bird_id 以外の
    セルを走査し「整数に見える最大値=訪問回数」「ISO日時の最大値=最終観測」とみなす。
    """
    cnt = 1
    last = ""
    for k, v in row.items():
        if k in ("tester_id", "bird_id"):
            continue
        sv = str(v).strip()
        if sv.isdigit():
            cnt = max(cnt, int(sv))
        elif len(sv) >= 10 and sv[:4].isdigit() and "-" in sv:
            if sv > last:
                last = sv
    return cnt, last


def aggregate_atlas(rows: list, birds_data: dict,
                    recent_days: int = 21, today: date | None = None) -> dict:
    """collection の生行 → 匿名・集合の集計。

    Returns:
      {
        "gardens": int,                      # 参加している庭(テスター)の総数
        "biomes": {
            biome_id: [
                {"bird_id", "name", "gardens", "sightings", "recent"(bool)},
                ...  # 庭の数が多い順
            ]
        },
      }
    tester_id は gardens 件数に畳み込むだけで、個人としては一切持ち出さない。
    """
    today = today or date.today()
    gardens: set[str] = set()
    # bird_id -> {gardens:set, sightings:int, last:str}
    by_bird: dict[str, dict] = {}

    for r in rows:
        tid = str(r.get("tester_id", "")).strip()
        bid = str(r.get("bird_id", "")).strip()
        if not tid or not bid or bid not in birds_data:
            continue
        gardens.add(tid)
        cnt, last = _row_count_and_last(r)
        slot = by_bird.setdefault(bid, {"gardens": set(), "sightings": 0, "last": ""})
        slot["gardens"].add(tid)
        slot["sightings"] += cnt
        if last > slot["last"]:
            slot["last"] = last

    biomes: dict[str, list] = {}
    for bid, slot in by_bird.items():
        bird = birds_data.get(bid, {})
        d = _parse_day(slot["last"])
        recent = bool(d and 0 <= (today - d).days <= recent_days)
        entry = {
            "bird_id": bid,
            "name": bird.get("name", bid),
            "gardens": len(slot["gardens"]),
            "sightings": slot["sightings"],
            "recent": recent,
        }
        for biome_id in bird.get("biome_pref", []):
            biomes.setdefault(biome_id, []).append(entry)

    for biome_id in biomes:
        biomes[biome_id].sort(key=lambda e: (-e["gardens"], -e["sightings"], e["name"]))

    return {"gardens": len(gardens), "biomes": biomes}


# ── データ取得(キャッシュ付き。Sheets を毎 rerun 叩かない) ──────────

@st.cache_data(ttl=300, show_spinner=False)
def _load_atlas_cached(_birds_sig: tuple) -> dict:
    """collection 全行を読み、集計して返す。5分キャッシュ。

    _birds_sig は birds_data の同一性をキャッシュキーに混ぜるためのダミー。
    """
    try:
        import sheets_client as sc
        rows = sc.load_all_collection()
    except Exception:
        rows = []
    # birds_data はキャッシュをまたいで安定なので import 側で取得
    from species_loader import BIRDS
    return aggregate_atlas(rows, BIRDS)


# ── UI ────────────────────────────────────────────────────────────

_BIOME_LABELS = {"kyoto": "🏯 京都", "charlotte": "🌳 シャーロット"}


def render_community_atlas(default_biome: str = "kyoto") -> None:
    """集合アトラス(みんなの庭)を描画する。読み取り専用・匿名・非競争。"""
    st.markdown("### 🗺 みんなの庭")
    st.caption(
        "みんなの観察が集まって、どの土地にどの声が訪れているかの地図になります。"
        "名前も順位もありません。ただ、世界が誰かに育てられているという記録です。"
    )

    atlas = _load_atlas_cached(("v1",))
    gardens = atlas.get("gardens", 0)
    biomes = atlas.get("biomes", {})

    if not gardens:
        st.info(
            "まだみんなの庭の記録がありません。"
            "鳥に会うと、その声がこの地図に静かに加わります。"
        )
        return

    st.markdown(
        f'<div style="color:#5a7a5a;font-size:0.9em;margin:2px 0 10px;">'
        f'🌿 いま <b>{gardens}</b> の庭が、この世界を育てています。</div>',
        unsafe_allow_html=True,
    )

    biome_ids = list(_BIOME_LABELS.keys())
    cur = default_biome if default_biome in biome_ids else biome_ids[0]
    chosen = st.radio(
        "土地を選ぶ",
        options=biome_ids,
        format_func=lambda x: _BIOME_LABELS[x],
        index=biome_ids.index(cur),
        horizontal=True,
        key="community_biome_select",
        label_visibility="collapsed",
    )

    species = biomes.get(chosen, [])
    if not species:
        st.info(f"{_BIOME_LABELS[chosen]}には、まだみんなの庭から訪れた声がありません。")
        return

    max_g = max(e["gardens"] for e in species)
    rows_html = ""
    for e in species[:20]:
        width = int(round(100 * e["gardens"] / max_g)) if max_g else 0
        recent = (
            '<span style="color:#c8a830;font-size:0.8em;margin-left:6px;">🌟 最近</span>'
            if e["recent"] else ""
        )
        rows_html += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;">'
            f'<span style="min-width:9em;font-size:0.9em;color:#3a5a3a;">{e["name"]}{recent}</span>'
            f'<span style="flex:1;background:#eef2e6;border-radius:6px;height:10px;overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{width}%;background:#9ec27a;"></span></span>'
            f'<span style="min-width:4.5em;text-align:right;color:#6a8a5a;font-size:0.8em;">'
            f'{e["gardens"]} の庭</span>'
            f'</div>'
        )
    st.markdown(
        f'<div style="background:#f3f7ed;border-left:3px solid #b0c890;'
        f'border-radius:8px;padding:10px 14px;margin:6px 0;">'
        f'<div style="font-size:0.8em;color:#7a9a6a;margin-bottom:6px;">'
        f'{_BIOME_LABELS[chosen]} に、みんなの庭から訪れている声</div>'
        f'{rows_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "「N の庭」はその声を迎えた庭の数です。多い少ないは賑わいであって、"
        "競争ではありません。あなたの庭も、この地図の一部です。"
    )
