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

**作業を1つ終えるたびに必ず走らせること。**

    py -3 tools/migration_audit.py            # 一覧と残りを出す
    py -3 tools/migration_audit.py --update   # 新しい関数を台帳に todo で足す
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
    buf = []
    for d in DART_DIRS:
        for root, _, files in os.walk(d):
            for f in files:
                if f.endswith(".dart"):
                    buf.append(open(os.path.join(root, f), encoding="utf-8").read())
    return "\n".join(buf)


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
    return problems


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
            # 「移した」なら実体があるはず。無ければ嘘なので落とす。
            sym = it.get("dart") or snake_to_camel(k.split(".", 1)[1])
            (done if sym in src else broken).append(k)
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

    if broken or unknown or screen_problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
