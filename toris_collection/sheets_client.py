"""
Toris Collection - Google Sheets バックエンド
全テスターの状態とログをスプレッドシートに保存する。

- ローカル開発: credentials.json をプロジェクト直下に置く
- Streamlit Cloud: secrets の [gcp_service_account] セクションを参照

すべての関数は、失敗時にも例外を投げない設計(log_access 以外は呼び出し側で
適切にハンドリング)。アプリの基本動作を Sheets 障害で止めないため。
"""
import json
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


# ====== 設定 ======
SPREADSHEET_ID = "18qZcHLNjR_DnXr3vaCaCHD3m2JsQPTaQcW2DALm8WM4"
CREDENTIALS_PATH = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ====== 認証(プロセス内キャッシュ) ======
_client_cache = None
_spreadsheet_cache = None


def _load_credentials():
    """credentials を読み込む。Streamlit Cloud secrets を優先、フォールバックでローカルファイル"""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            return Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass
    return Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)


def get_client():
    global _client_cache
    if _client_cache is None:
        _client_cache = gspread.authorize(_load_credentials())
    return _client_cache


def get_spreadsheet():
    global _spreadsheet_cache
    if _spreadsheet_cache is None:
        _spreadsheet_cache = get_client().open_by_key(SPREADSHEET_ID)
    return _spreadsheet_cache


def _ws(name):
    return get_spreadsheet().worksheet(name)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# ====== testers ======
def list_testers():
    """[(tester_id, display_name), ...] を返す。display_name 未設定時は tester_id 自身"""
    rows = _ws("testers").get_all_values()
    if len(rows) < 2:
        return []
    header = rows[0]
    out = []
    for row in rows[1:]:
        d = dict(zip(header, row))
        tid = (d.get("tester_id") or "").strip()
        if not tid:
            continue
        name = (d.get("display_name") or "").strip() or tid
        out.append((tid, name))
    return out


# ====== field_state ======
def load_field_state(tester_id):
    """該当テスターの行を dict で返す。なければ None。
    current_birds は JSON 文字列を list に変換した値も併せて返す。
    """
    rows = _ws("field_state").get_all_records()
    for row in rows:
        if str(row.get("tester_id", "")) == tester_id:
            # JSON文字列を解析して使いやすい list に変換
            cb_str = row.get("current_birds", "")
            try:
                row["current_birds_list"] = json.loads(cb_str) if cb_str else []
            except (ValueError, TypeError):
                row["current_birds_list"] = []
            return row
    return None


def save_field_state(tester_id, biome, current_temperature, current_season,
                     current_birds_list):
    """upsert: 該当行があれば更新、なければ追加"""
    sheet = _ws("field_state")
    rows = sheet.get_all_values()
    new_row = [
        tester_id,
        now_iso(),
        biome,
        f"{current_temperature:.1f}",
        current_season,
        json.dumps(list(current_birds_list)),
        now_iso(),
    ]
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == tester_id:
            sheet.update(values=[new_row], range_name=f"A{i}:G{i}")
            return
    sheet.append_row(new_row)


# ====== plantings ======
def load_active_plantings(tester_id):
    """[plant_id, ...] のリスト(植えた順)"""
    rows = _ws("plantings").get_all_records()
    return [
        r["plant_id"] for r in rows
        if str(r.get("tester_id", "")) == tester_id and r.get("status") == "active"
    ]


def load_active_plantings_with_time(tester_id):
    """[(plant_id, planted_at_str), ...] のリスト(植えた順)"""
    rows = _ws("plantings").get_all_records()
    out = []
    for r in rows:
        if str(r.get("tester_id", "")) == tester_id and r.get("status") == "active":
            out.append((r["plant_id"], r.get("planted_at", "")))
    return out


def add_planting(tester_id, plant_id):
    sheet = _ws("plantings")
    rows = sheet.get_all_values()
    next_id = len(rows)  # ヘッダ行を含むので len(rows) が次の整数IDになる
    sheet.append_row([str(next_id), tester_id, plant_id, now_iso(), "active", ""])


def remove_planting(tester_id, plant_id):
    """指定したテスターの指定 plant_id の active 行を1件 removed に変更する。
    複数植えていた場合は最後の1本だけ撤去する。
    """
    sheet = _ws("plantings")
    rows = sheet.get_all_values()
    if len(rows) < 2:
        return False
    # 後ろから探す(最後に植えたものを最初に撤去)
    for i in range(len(rows) - 1, 0, -1):
        row = rows[i]
        if (len(row) >= 5 and row[1] == tester_id and
                row[2] == plant_id and row[4] == "active"):
            sheet.update(values=[["removed"]], range_name=f"E{i+1}")
            return True
    return False


def remove_all_plantings(tester_id):
    """active 行を全て removed に更新(物理削除はしない)"""
    sheet = _ws("plantings")
    rows = sheet.get_all_values()
    if len(rows) < 2:
        return
    updates = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 5 and row[1] == tester_id and row[4] == "active":
            updates.append({"range": f"E{i}", "values": [["removed"]]})
    if updates:
        sheet.batch_update(updates)


# ====== bird_visits ======
def add_visit(tester_id, bird_id, visit_type, reason_text="",
              related_plant_id="", related_insect_id="",
              arrived_at=None):
    """訪問記録を追加。
    arrived_at が None の場合は現在時刻、datetime を渡せばその時刻、
    str を渡せばそのまま記録する(不在中ループからの過去時刻記録に対応)。
    """
    if arrived_at is None:
        arrived_at_str = now_iso()
    elif hasattr(arrived_at, "isoformat"):
        arrived_at_str = arrived_at.isoformat(timespec="seconds")
    else:
        arrived_at_str = str(arrived_at)

    sheet = _ws("bird_visits")
    rows = sheet.get_all_values()
    next_id = len(rows)
    sheet.append_row([
        str(next_id), tester_id, bird_id, arrived_at_str, "",
        visit_type, reason_text, related_plant_id, related_insect_id,
    ])


# ====== collection ======
def load_collection_set(tester_id):
    """{bird_id, ...} の set"""
    rows = _ws("collection").get_all_records()
    return {
        r["bird_id"] for r in rows
        if str(r.get("tester_id", "")) == tester_id
    }


def upsert_collection(tester_id, bird_id):
    """初回観測なら追加、既存なら last_seen_at と visit_count を更新"""
    sheet = _ws("collection")
    rows = sheet.get_all_values()
    seen_at = now_iso()
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 5 and row[0] == tester_id and row[1] == bird_id:
            try:
                count = int(row[4]) + 1
            except (ValueError, IndexError):
                count = 1
            sheet.batch_update([
                {"range": f"D{i}", "values": [[seen_at]]},
                {"range": f"E{i}", "values": [[str(count)]]},
            ])
            return
    sheet.append_row([tester_id, bird_id, seen_at, seen_at, "1"])


# ====== mementos (落とし物) ======
def _ensure_mementos_sheet():
    """mementos シートが存在しなければ作成する。
    スプレッドシートの既存構造を変更せずに必要な時だけ追加する。
    """
    ss = get_spreadsheet()
    try:
        return ss.worksheet("mementos")
    except Exception:
        # 新規作成
        ws = ss.add_worksheet(title="mementos", rows=1000, cols=8)
        ws.append_row([
            "memento_id", "tester_id", "kind", "target_id", "biome",
            "found_at", "via_bird_id", "notes",
        ])
        return ws


def add_memento(tester_id, memento_id, kind, target_id, biome, via_bird_id):
    """落とし物を記録する。memento_id は 'feather:shijukara' 等の形式。"""
    sheet = _ensure_mementos_sheet()
    rows = sheet.get_all_values()
    next_id = len(rows)
    sheet.append_row([
        str(next_id), tester_id, kind, target_id, biome,
        now_iso(), via_bird_id, "",
    ])


def load_mementos(tester_id):
    """テスターの落とし物履歴を全件返す: list of dict
    各dictは {memento_id, kind, target_id, biome, found_at, via_bird_id, notes} を含む。
    memento_id は 'feather:shijukara' のような合成IDを返す(mementos モジュール側のIDと整合)。

    案A の新形式(全カテゴリ kind:bird_id 形式)を主に処理し、
    旧形式や過去のバグで残っているレコードも吸収する:
      - kind="twig", target="kyoto"             → twig_kyoto (旧バイオーム別)
      - kind="twig", target="twig_kyoto"        → twig_kyoto (target_id 二重バグ)
      - kind="seed", target="dogwood" (植物名)   → seed_charlotte (biome に紐づけ)
        ※ 案A化で seed は鳥固有になったが、過去レコードは植物固有だった
    """
    sheet = _ensure_mementos_sheet()
    rows = sheet.get_all_records()
    out = []
    KNOWN_BIOMES = {"kyoto", "sydney", "charlotte"}
    for r in rows:
        if str(r.get("tester_id", "")) != tester_id:
            continue
        kind = (r.get("kind") or "").strip()
        target = (r.get("target_id") or "").strip()
        biome = (r.get("biome") or "").strip()
        if not kind or not target:
            continue

        if kind in ("twig", "nut"):
            # twig/nut は新形式では bird_id, 旧形式ではバイオーム名 or twig_xxx 文字列
            if target.startswith(("twig_", "nut_")):
                # target_id 二重バグ: そのまま使う
                mid = target
            elif target in KNOWN_BIOMES:
                # 旧形式: バイオーム名 → twig_kyoto 等
                mid = f"{kind}_{target}"
            else:
                # 新形式: bird_id
                mid = f"{kind}:{target}"
        elif kind == "seed":
            # seed は新形式では bird_id, 旧形式では植物名
            from data import PLANTS, BIRDS
            if target in BIRDS:
                mid = f"seed:{target}"
            elif target in PLANTS:
                # 旧形式の植物紐づけ seed: 表示は via_bird_id ベースの新形式に変換
                via = (r.get("via_bird_id") or "").strip()
                if via and via in BIRDS:
                    mid = f"seed:{via}"
                else:
                    # fallback: 植物名のままIDとして残す
                    mid = f"seed_plant:{target}"
            else:
                mid = f"seed:{target}"
        else:
            # feather, plume など: kind:target_id
            mid = f"{kind}:{target}"

        out.append({
            "memento_id": mid,
            "kind": kind,
            "target_id": target,
            "biome": biome,
            "found_at": r.get("found_at", ""),
            "via_bird_id": r.get("via_bird_id", ""),
            "notes": r.get("notes", ""),
        })
    return out


# ====== bird_notes (鳥への個人メモ・発見地) ======
def _ensure_bird_notes_sheet():
    """bird_notes シートが存在しなければ作成する。"""
    ss = get_spreadsheet()
    try:
        return ss.worksheet("bird_notes")
    except Exception:
        ws = ss.add_worksheet(title="bird_notes", rows=1000, cols=6)
        ws.append_row([
            "tester_id", "bird_id", "location", "note_text", "first_saved_at", "updated_at"
        ])
        return ws


def load_bird_notes(tester_id):
    """ {bird_id: {"location": ..., "note_text": ..., ...}} の dict を返す """
    sheet = _ensure_bird_notes_sheet()
    rows = sheet.get_all_records()
    out = {}
    for r in rows:
        if str(r.get("tester_id", "")) != tester_id:
            continue
        bird_id = r.get("bird_id", "")
        if bird_id:
            out[bird_id] = {
                "location": r.get("location", ""),
                "note_text": r.get("note_text", ""),
                "first_saved_at": r.get("first_saved_at", ""),
                "updated_at": r.get("updated_at", ""),
            }
    return out


def save_bird_note(tester_id, bird_id, location, note_text):
    """upsert: 既存行があれば更新、なければ追加"""
    sheet = _ensure_bird_notes_sheet()
    rows = sheet.get_all_values()
    now = now_iso()
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 2 and row[0] == tester_id and row[1] == bird_id:
            sheet.batch_update([
                {"range": f"C{i}", "values": [[location]]},
                {"range": f"D{i}", "values": [[note_text]]},
                {"range": f"F{i}", "values": [[now]]},
            ])
            return
    sheet.append_row([tester_id, bird_id, location, note_text, now, now])


# ====== memento_notes (個別の落とし物へのメモ) ======
def update_memento_note(tester_id, memento_row_id, note_text):
    """mementos シートの notes 列を更新する。
    memento_row_id はシート上の memento_id (連番)。
    """
    sheet = _ensure_mementos_sheet()
    rows = sheet.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 2 and row[0] == str(memento_row_id) and row[1] == tester_id:
            sheet.update(values=[[note_text]], range_name=f"H{i}")
            return True
    return False


# ====== access_logs ======
def log_access(tester_id, screen, action, details=""):
    """fire-and-forget: 失敗してもアプリは続行する"""
    try:
        sheet = _ws("access_logs")
        rows = sheet.get_all_values()
        next_id = len(rows)
        sheet.append_row([
            str(next_id), tester_id, now_iso(), screen, action, details
        ])
    except Exception:
        pass
