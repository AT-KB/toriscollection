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

    if broken or unknown:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
