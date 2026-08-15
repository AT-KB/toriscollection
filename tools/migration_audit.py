"""移行の取りこぼしを**機械で**数える。

## なぜ要るか(2026-08-15)
移した/移していないを目視で数えていたため、取りこぼしを繰り返した。
実際、CEO の指摘で「土地の選択(Charlotte)・不在中の時間経過・出会いの儀式・
ネットワーク図・木と鳥の絵」が抜けていたことが分かった。**数えたつもりの数字は
当てにならない。**

そこでこの道具が:
  1. Python 側(`toris_collection/*.py`)の**公開関数を全部**拾い、
  2. 台帳(`tools/migration_ledger.json`)と突き合わせ、
  3. 台帳に無い関数があれば **落ちる**(= 新しく増えた機能を見落とせない)、
  4. 「移した」と書いてある項目は、Dart 側に実体があるかを実際に探して確かめる。
  5. **画面を検める**(下の `screen_audit`)。関数を移したかだけでは、
     画面のミスは1件も捕まらない — 実際、Flutter のマスコットが鳥の代わりに
     出ていたのを見逃した(CEO 指摘 2026-08-15)。
  6. **テストを実際に走らせる**(下の `run_tests`)。テストは書いてあっても
     回さなければ無いのと同じ。この1コマンドを唯一の入口にする。

**作業を1つ終えるたびに必ず走らせること。**

    py -3 tools/migration_audit.py            # 一覧・画面の検査・テスト
    py -3 tools/migration_audit.py --update   # 新しい関数を台帳に todo で足す
    py -3 tools/migration_audit.py --no-test  # テストを飛ばす(急ぐときだけ)
"""
import ast
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
PY_DIR = os.path.join(ROOT, "toris_collection")
DART_DIRS = [os.path.join(ROOT, "toris_core", "lib"),
             os.path.join(ROOT, "toris_app", "lib")]
LEDGER = os.path.join(os.path.dirname(__file__), "migration_ledger.json")

# 開発用・調査用で、製品の機能ではないもの
SKIP_MODULES = {
    "diagnose", "diagnose_globi", "test_sheets_connection", "license_audit",
    "check_xeno_canto_coverage", "build_globi_cache", "species_expand",
    "app",  # 画面の組み立て。関数単位ではなく画面単位で数える(下の SCREENS)
}

# app.py の公開関数。**黙って除外しない。**
# SKIP_MODULES に app を入れて画面単位で数えているが、それだと app.py に
# ロジックが増えても気づけない。ここに名前を書いておき、知らない関数が
# 現れたら落とす(2026-08-16 の監査で、9件が黙って除外されていたのを見つけた)。
APP_FUNCTIONS = {
    "render_bird_profile_html": "図鑑のプロフィール → screen.tab_guide",
    "render_bird_sprite_html": "鳥のドット絵 → screen.bird_sprites",
    "render_bird_detail_image_html": "図鑑の大きい絵 → screen.bird_sprites",
    "render_bird_audio": "鳴き声の再生 → screen.tab_guide",
    "render_field_view": "庭の SVG → screen.garden_tree_scene",
    "render_login_screen": "入口画面 → screen.login_screen",
    "load_state_from_sheets": "[legacy・未使用] Sheets からの復元。捨てる",
    "init_state": "初期化 → Garden の既定値",
    "render_tutorial_banner": "3ステップの案内 → tutorial(保留)",
}

# 画面(app.py の中身)は関数では数えられないので、目で見える単位で持つ
SCREENS = [
    "tab_radio", "tab_garden", "tab_plant", "tab_guide", "tab_network",
    "tab_howto", "login_screen", "save_code_ui", "biome_choice",
    "garden_tree_scene", "bird_sprites", "network_graph_view",
    "ritual_meet_birds", "todays_garden", "popup_met_bird",
]


def python_api() -> dict:
    """モジュール → 公開関数の一覧。"""
    out = {}
    for f in sorted(os.listdir(PY_DIR)):
        if not f.endswith(".py"):
            continue
        mod = f[:-3]
        if mod in SKIP_MODULES or mod.startswith("_"):
            continue
        try:
            tree = ast.parse(open(os.path.join(PY_DIR, f), encoding="utf-8").read())
        except Exception:
            continue
        fns = [n.name for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not n.name.startswith("_")]
        if fns:
            out[mod] = fns
    return out


def dart_sources() -> str:
    """Dart の**実装だけ**(コメントと文字列リテラルを落とす)。

    ⚠️ 以前は全文をそのまま連結していた。すると「移した」の確認が
    **コメントや画面の文字列への部分一致**で通ってしまう。実際
    `bird_profile.likes / home / fears` は図鑑のラベル
    "Likes" / "Home" / "Fears" に当たって「移した」ことになっていたが、
    実体は無く、中身(天敵の分類表)は間違っていた(2026-08-16 の監査で発覚)。
    """
    import re
    buf = []
    for d in DART_DIRS:
        for root, _, files in os.walk(d):
            for f in files:
                if not f.endswith(".dart"):
                    continue
                t = open(os.path.join(root, f), encoding="utf-8").read()
                t = re.sub(r"/\*.*?\*/", " ", t, flags=re.S)             # ブロック注釈
                t = "\n".join(l.split("//")[0] for l in t.splitlines())  # 行注釈
                t = re.sub(r"'(?:[^'\\\n]|\\.)*'", " ", t)               # 文字列
                t = re.sub(r'"(?:[^"\\\n]|\\.)*"', " ", t)
                buf.append(t)
    return "\n".join(buf)


def is_declared(sym: str, code: str) -> bool:
    """その名前が Dart 側で**宣言されている**か(呼ばれているだけでは駄目)。

    関数・クラス・定数・getter を拾う。戻り値の型に括弧が入る形
    (`double Function(String) makeArrivalBonusFn(`)も通す。
    """
    import re
    e = re.escape(sym)
    pats = [
        r"\b(?:class|enum|mixin|extension|typedef)\s+" + e + r"\b",
        r"(?:^|\n)\s*(?:const|final|var|late)\s[^;\n]*\b" + e + r"\s*=",
        r"(?:^|\n)[^;\n]*\b" + e + r"\s*\([^;]*\)\s*(?:async\s*)?[{=]",
        r"(?:^|\n)[^;\n]*\bget\s+" + e + r"\b",
    ]
    return any(re.search(p, code) for p in pats)


def snake_to_camel(s: str) -> str:
    a, *rest = s.split("_")
    return a + "".join(x.title() for x in rest)


def load_ledger() -> dict:
    if os.path.exists(LEDGER):
        return json.load(open(LEDGER, encoding="utf-8"))
    return {"items": {}}


# ─────────────────────────────────────────────────────────────
# 画面の検査
#
# ## なぜ足したか(2026-08-15 CEO)
# 「なんで監査機能働いてないの? ゴミみたいな初期スクリーンで分かるミスやん」
#
# そのとおりで、ここまでの監査は「Python の関数を移したか」しか見ておらず、
# **画面を一度も見ていなかった**。実際に漏れた:
#   - 絵の無い種のフォールバックが `Icons.flutter_dash`(Flutter のマスコット)
#   - 画面に日本語が出ていた(アプリは全部英語)
#
# 完成度は機械で測れないが、**「これが出ていたら確実に間違い」は機械で測れる。**
# 以下はその一覧。目で見つける前に落とすのが目的。
# ─────────────────────────────────────────────────────────────

# 出ていたら確実に間違い、という印(正規表現, 説明)
FORBIDDEN_IN_UI = [
    (r"Icons\.flutter_dash",
     "Flutter のマスコット。素材の代役に枠組みの既定を使わない"),
    (r"Icons\.image_not_supported|Icons\.broken_image",
     "「絵がありません」を見せない。代役を用意する"),
    (r"FlutterLogo",
     "Flutter のロゴが画面に出る"),
    (r"\bTODO\b|\bFIXME\b|Lorem ipsum|placeholder text",
     "書きかけが画面に残っている"),
    (r"Text\(\s*['\"]\s*['\"]\s*\)",
     "空の文字。出さないなら widget ごと出さない"),
]

# 画面に日本語が出ていないこと。**アプリの表示は全部英語**
# (一度これで作り直しになった)。コメントと doc は日本語なので、
# 文字列リテラルの中だけを見る。
JP = r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]"


def _ui_files() -> list:
    out = []
    app_lib = os.path.join(ROOT, "toris_app", "lib")
    for root, _dirs, files in os.walk(app_lib):
        for f in files:
            if f.endswith(".dart"):
                out.append(os.path.join(root, f))
    return sorted(out)


def _strip_comments(line: str) -> str:
    i = line.find("//")
    return line[:i] if i >= 0 else line


def screen_audit() -> list:
    """画面の作りを機械で検める。問題の一覧を返す(空なら合格)。"""
    import re
    problems = []

    for path in _ui_files():
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        for n, raw in enumerate(lines, 1):
            line = _strip_comments(raw)
            if not line.strip():
                continue
            for pat, why in FORBIDDEN_IN_UI:
                if re.search(pat, line):
                    problems.append(f"{rel}:{n} {why}\n        {line.strip()[:90]}")
            # 表示文字列の中の日本語だけを見る
            for lit in re.findall(r"'([^'\\]*)'|\"([^\"\\]*)\"", line):
                text = lit[0] or lit[1]
                if re.search(JP, text):
                    problems.append(
                        f"{rel}:{n} 画面に日本語(アプリは全部英語)\n"
                        f"        {text[:60]}")

    # 全37種に、絵か**代役の方針**があること。
    # 絵が無いこと自体は問題ではない(描き下ろしは順次)。
    # 問題なのは、代役が用意されていないこと。
    sprites = os.path.join(ROOT, "toris_app", "assets", "sprites")
    birds_json = os.path.join(ROOT, "toris_app", "assets", "data", "birds.json")
    if os.path.isdir(sprites) and os.path.exists(birds_json):
        have = {f[:-4] for f in os.listdir(sprites)
                if f.endswith(".png") and not f.endswith("_detail.png")}
        with open(birds_json, encoding="utf-8") as f:
            all_birds = set(json.load(f))
        missing = sorted(all_birds - have)
        mark = os.path.join(ROOT, "toris_app", "lib", "ui", "bird_mark.dart")
        if missing and not os.path.exists(mark):
            problems.append(
                f"絵が無い種が {len(missing)} 件あるのに、代役(ui/bird_mark.dart)"
                f"が無い: {', '.join(missing[:6])}…")
        elif missing:
            print(f"  絵が無い種 {len(missing)}/{len(all_birds)} 件は代役で出る"
                  f"(BirdMark): {', '.join(missing)}")

    # app.py に、台帳に無い公開関数が増えていないか。
    import ast as _ast
    app_py = os.path.join(PY_DIR, "app.py")
    if os.path.exists(app_py):
        try:
            tree = _ast.parse(open(app_py, encoding="utf-8").read())
            names = {n.name for n in tree.body
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                     and not n.name.startswith("_")}
            for n in sorted(names - set(APP_FUNCTIONS)):
                problems.append(
                    f"app.py に台帳の無い公開関数 {n}(APP_FUNCTIONS に足すこと)")
            gone = sorted(set(APP_FUNCTIONS) - names)
            if gone:
                print(f"  app.py から消えた関数(台帳の掃除どき): {', '.join(gone)}")
        except Exception as e:
            problems.append(f"app.py を読めなかった: {e}")

    # アセットと差分テストのデータが**同じもの**か。
    # 別管理にしていたら predators.json だけ入っておらず、図鑑のテストが
    # 書けなかった(2026-08-16)。片方だけ更新されると、テストが古いデータを
    # 見たまま「一致している」と嘘をつく。
    assets = os.path.join(ROOT, "toris_app", "assets", "data")
    fixtures = os.path.join(ROOT, "toris_core", "test", "fixtures")
    if os.path.isdir(assets) and os.path.isdir(fixtures):
        for f in sorted(os.listdir(assets)):
            if not f.endswith(".json"):
                continue
            a = os.path.join(assets, f)
            b = os.path.join(fixtures, f)
            if not os.path.exists(b):
                problems.append(f"データ {f} が差分テスト側に無い"
                                f"(tools/export_data.py が両方に書くはず)")
            elif (open(a, encoding="utf-8").read()
                  != open(b, encoding="utf-8").read()):
                problems.append(f"データ {f} がアセットと差分テストでずれている"
                                f"(py -3 tools/export_data.py を実行すること)")

    return problems


# ─────────────────────────────────────────────────────────────
# テストを実際に走らせる
#
# テストは**書いてあっても回さなければ無い**のと同じ。監査を1つの入口にする。
#   - toris_core : Python 版と突き合わせた差分テスト(到来4440通り 等)
#   - toris_app  : 庭の状態の往復(閉じて開き直しても欠けないこと)
# 遅いのが嫌なときだけ --no-test。ふだんは付けないこと。
# ─────────────────────────────────────────────────────────────

def run_tests() -> list:
    """テストを走らせる。落ちたものの一覧を返す(空なら合格)。"""
    import shutil
    import subprocess

    failures = []
    flutter = shutil.which("flutter") or shutil.which("flutter.bat")
    dart = shutil.which("dart") or shutil.which("dart.bat")
    if not dart and not flutter:
        return ["dart / flutter が PATH に無いのでテストを走らせられない"]

    jobs = []
    if dart:
        jobs.append(("toris_core (Python 版との突き合わせ)",
                     [dart, "test"], os.path.join(ROOT, "toris_core")))
    if flutter:
        jobs.append(("toris_app (庭の状態の往復・画面)",
                     [flutter, "test"], os.path.join(ROOT, "toris_app")))

    for label, cmd, cwd in jobs:
        if not os.path.isdir(cwd):
            continue
        try:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                               timeout=600, encoding="utf-8", errors="replace")
        except Exception as e:
            failures.append(f"{label}: 走らせられなかった({e})")
            continue
        if r.returncode == 0:
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
            print(f"  OK  {label}  {tail[-1][:70] if tail else ''}")
        else:
            failures.append(f"{label}: 落ちた")
            for ln in (r.stdout or "").splitlines()[-12:]:
                if ln.strip():
                    failures.append(f"      {ln[:110]}")
    return failures


def main() -> None:
    api = python_api()
    ledger = load_ledger()
    items = ledger.setdefault("items", {})
    update = "--update" in sys.argv

    keys = []
    for mod, fns in api.items():
        for fn in fns:
            keys.append(f"{mod}.{fn}")
    for s in SCREENS:
        keys.append(f"screen.{s}")

    unknown = [k for k in keys if k not in items]
    if unknown and update:
        for k in unknown:
            items[k] = {"status": "todo", "dart": ""}
        json.dump(ledger, open(LEDGER, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print(f"台帳に {len(unknown)} 件を todo で追加した")
        unknown = []

    src = dart_sources()
    done, todo, dropped, broken = [], [], [], []
    for k in keys:
        it = items.get(k)
        if it is None:
            continue
        st = it.get("status")
        if st == "dropped":
            dropped.append(k)
        elif st == "done":
            # 「移した」なら**宣言**があるはず。呼ばれているだけ・コメントに
            # 出てくるだけ・画面の文字列に当たっただけでは通さない。
            sym = it.get("dart") or snake_to_camel(k.split(".", 1)[1])
            (done if is_declared(sym, src) else broken).append(k)
        else:
            todo.append(k)

    print(f"Python の公開関数 {sum(len(v) for v in api.values())} 件"
          f" + 画面 {len(SCREENS)} 件 = {len(keys)} 件")
    print(f"  移した      : {len(done)}")
    print(f"  未着手      : {len(todo)}")
    print(f"  やらない    : {len(dropped)}")
    if broken:
        print(f"  !! 台帳では『移した』だが Dart に実体が無い: {len(broken)}")
        for k in broken:
            print(f"       {k}")
    if unknown:
        print(f"  !! 台帳に無い(見落とし): {len(unknown)}")
        for k in unknown[:40]:
            print(f"       {k}")

    if todo:
        print("\n── 残り ──")
        by_mod = {}
        for k in todo:
            by_mod.setdefault(k.split(".", 1)[0], []).append(k.split(".", 1)[1])
        for mod in sorted(by_mod):
            print(f"  {mod:<16} {', '.join(sorted(by_mod[mod]))}")

    # ── 画面の検査 ──
    # 関数を移したかだけでは、画面のミスは1件も捕まらない。
    print("\n── 画面 ──")
    screen_problems = screen_audit()
    if screen_problems:
        print(f"  !! {len(screen_problems)} 件")
        for p in screen_problems:
            print(f"     {p}")
    else:
        print("  問題なし")

    # ── テスト ──
    test_failures = []
    if "--no-test" not in sys.argv:
        print("\n── テスト ──")
        test_failures = run_tests()
        for f in test_failures:
            print(f"  !! {f}" if not f.startswith("  ") else f)

    if broken or unknown or screen_problems or test_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
