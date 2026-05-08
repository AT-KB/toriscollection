"""
Toris Collection - Google Sheets 接続テスト
これを最初に実行して、スプレッドシートに読み書きできることを確認する。
本体アプリには触れないので、安全にテストできる。

使い方:
    python test_sheets_connection.py
"""
import json
import sys
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("❌ パッケージが未インストール。以下を実行:")
    print("   pip install gspread google-auth")
    sys.exit(1)


# ===== 設定 =====
SPREADSHEET_ID = "18qZcHLNjR_DnXr3vaCaCHD3m2JsQPTaQcW2DALm8WM4"
CREDENTIALS_PATH = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    print("=" * 60)
    print("Toris Collection - Sheets 接続テスト")
    print("=" * 60)

    # ステップ1: 認証ファイルの存在確認
    print("\n[1/5] 認証ファイル確認...")
    try:
        with open(CREDENTIALS_PATH, "r") as f:
            cred_data = json.load(f)
        client_email = cred_data.get("client_email", "(取得失敗)")
        print(f"  ✓ {CREDENTIALS_PATH} を読み込み")
        print(f"  ✓ サービスアカウント: {client_email}")
    except FileNotFoundError:
        print(f"  ❌ {CREDENTIALS_PATH} が見つかりません")
        print(f"     プロジェクトフォルダ直下に配置してください")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"  ❌ {CREDENTIALS_PATH} が壊れています")
        sys.exit(1)

    # ステップ2: 認証
    print("\n[2/5] Google認証...")
    try:
        creds = Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        client = gspread.authorize(creds)
        print("  ✓ 認証成功")
    except Exception as e:
        print(f"  ❌ 認証失敗: {e}")
        sys.exit(1)

    # ステップ3: スプレッドシートを開く
    print("\n[3/5] スプレッドシートを開く...")
    try:
        sh = client.open_by_key(SPREADSHEET_ID)
        print(f"  ✓ タイトル: {sh.title}")
    except gspread.exceptions.APIError as e:
        print(f"  ❌ スプレッドシートが開けません: {e}")
        print(f"     対処: スプレッドシートの「共有」で")
        print(f"     {client_email} を編集者として追加してください")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ エラー: {e}")
        sys.exit(1)

    # ステップ4: シート一覧を読む
    print("\n[4/5] シート構造の確認...")
    expected = ["_README", "testers", "field_state", "plantings",
                "bird_visits", "collection", "access_logs", "harmony_records"]
    actual = [ws.title for ws in sh.worksheets()]
    print(f"  検出シート: {actual}")
    missing = [s for s in expected if s not in actual]
    if missing:
        print(f"  ⚠️  不足シート: {missing}")
    else:
        print("  ✓ 全シート存在")

    # ステップ5: 読み書きテスト
    print("\n[5/5] 読み書きテスト (access_logs にテスト行を追記)...")
    try:
        ws = sh.worksheet("access_logs")
        rows = ws.get_all_values()
        print(f"  ✓ 読み込み成功 (現在 {len(rows)} 行)")

        next_id = len(rows)  # ヘッダ行を含むので次の log_id はそのまま
        test_row = [
            str(next_id),
            "tester_00",
            datetime.now().isoformat(timespec="seconds"),
            "test",
            "connection_test",
            "接続テストからの書き込み",
        ]
        ws.append_row(test_row)
        print(f"  ✓ 書き込み成功 (テスト行を追加)")
        print(f"     スプレッドシートを開いて access_logs を確認してください")
    except Exception as e:
        print(f"  ❌ 読み書き失敗: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ すべて成功。連携の準備が整いました。")
    print("=" * 60)
    print("\n次のステップ: 本体アプリへの統合に進めます。")


if __name__ == "__main__":
    main()
