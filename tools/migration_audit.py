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
  7. **主張台帳と素材台帳を検める**(下の `claim_ledger_audit` /
     `material_ledger_audit`)。公に言ったことの「検査」欄が実在するか、
     外に出した画と動画が台帳に載っているかを見る。2026-10-15 追加。

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
    # 「おかえりなさい」は台帳に無かった(app.py の _welcome_dialog)。
    # 画面の数え漏れ(2026-08-16 にポップアップを移すときに気づいた)。
    "popup_welcome_back",
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

# **無いと画面が黙って嘘をつく**もの。(ファイル, 正規表現, 説明)
#
# ## なぜ足したか(2026-08-18 の監査)
# ここまでのリントは「出ていたら間違い」しか見ていなかった。ところが実際に
# 漏れたのは逆で、**あるべきものが画面から落ちていた**:
#
#   - 図鑑の「こわいもの」。Python は属レベル(同属の近縁種の記録)のとき
#     「(from records of close relatives)」と断っていたのに、Flutter は
#     黙って種の事実として出していた(6種が該当)。原則4「生態に誠実」。
#   - 庭が留守のぶんを進める処理。画面の初回生成でしか呼ばれず、
#     ホームに戻して戻ってきても動かなかった。**鳥が来ない**の正体。
#
# どちらも「関数は移植済み」なので関数の台帳では検出できない。
# **呼ばれているかどうか**を見る必要がある。
# ─────────────────────────────────────────────────────────────
# **両言語に書いたのに、突き合わせていない定数**を捕まえる。
#
# ## なぜ足したか(2026-08-21)
# `ITEM_OFFERED`(Python) と `kOfferedItems`(Dart) を両方に書いたのに
# `logic_fixtures.py` へ足すのを忘れ、**抽選プールが 6種 と 3種 でずれていた**。
# 台帳は「関数が宣言されているか」しか見ず、fixtures は足したものしか比べない。
# つまり **定数は誰も見ていなかった**。
#
# ここでは (Python の定数, Dart の識別子) の組を並べ、
#   1. Dart 側にその名前の宣言があるか
#   2. **その値が logic.json に載っているか**(= 突き合わせの対象になっているか)
# の2つを見る。値が載っていなければ、書いてあってもずれに気づけない。
SHARED_CONSTANTS = [
    ("garden_items.ITEM_OFFERED", "kOfferedItems"),
    ("garden_items.DURATION_HOURS", "kItemDurationHours"),
    ("garden_items.NYJER_TARGET_BIRDS", "kNyjerTargets"),
    ("feeder_chain.FEEDERS", "kFeeders"),
]

# ─────────────────────────────────────────────────────────────
# **起動を止めうる待ちが無いか。**
#
# ## なぜ足したか(2026-08-21)
# `main()` で `await MobileAds.initialize()` していた。このアプリは
# ネットワーク無しで全部動くのに、**電波が悪いと起動が固まる**状態だった。
# 監査はシンボルの有無しか見ておらず、待ち切りかどうかは誰も見ていなかった。
#
# (ファイル, その中に必ず在るべき語, なぜ)
MUST_NOT_BLOCK = [
    # ⚠️ 「ファイルのどこかに timeout がある」では**弱すぎる**
    #    (別の待ちに付いていても通ってしまい、実際に取り逃した)。
    #    **初期化そのもの**に付いていることを見る。
    ("toris_app/lib/ads/ads.dart", r"initialize\(\)\s*\.timeout\(",
     "広告SDKの初期化に待ち切りが無い。電波が悪いと起動が固まる"),
]

# ─────────────────────────────────────────────────────────────
# **「移した」と言っているのに、誰も突き合わせていない関数**を数える。
#
# ## なぜ足したか(2026-08-21)
# CEO「なんでこの前監査したのにこれ気づけないのか」。ラジオが会っていない鳥まで
# 鳴らしていた件を、監査は3回目のすり抜けとして見逃した。
#
# 原因は個別の見落としではなく**構造**だった:
#   ・台帳は「Dart に**宣言があるか**」しか見ない。中身が違っても通る。
#   ・fixtures は「**誰かが足したもの**」しか比べない。足し忘れは検出できない。
# 実際に数えると、「移した」100件のうち **35件が一度も突き合わせられていない**。
# 移植面の3分の1が未検証のまま「済み」と表示されていた。
#
# ## 対策: 個別の grep を増やすのではなく、**未検証の数を測って増やさせない**
# 全部を一度に埋めるのは非現実的なので、**ラチェット**にする。
# いまの数を基準として記録し、**増えたら落とす**。減らすぶんには自由。
# こうすると「新しく移したのに突き合わせを書かない」が必ず引っかかる。
UNVERIFIED_KEY = "unverified_baseline"


def _test_sources() -> str:
    """突き合わせに使っているテストを全部つなげたもの。"""
    out = []
    for base in ("toris_core/test", "toris_app/test"):
        root = os.path.join(ROOT, base.replace("/", os.sep))
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.endswith(".dart"):
                    out.append(open(os.path.join(dp, f), encoding="utf-8").read())
    return chr(10).join(out)


def _mentions(blob: str, sym: str) -> bool:
    """`sym` が**単語として**出てくるか。正規表現は使わない(エスケープ事故を避ける)。"""
    def word_char(c: str) -> bool:
        return c.isalnum() or c == "_"

    i = blob.find(sym)
    while i != -1:
        before = blob[i - 1] if i > 0 else " "
        j = i + len(sym)
        after = blob[j] if j < len(blob) else " "
        if not word_char(before) and not word_char(after):
            return True
        i = blob.find(sym, i + 1)
    return False


def unverified_ports(items: dict) -> list:
    """`done` なのに、どのテストからも名前が出てこない関数。"""
    blob = _test_sources()
    out = []
    for k, v in items.items():
        if v.get("status") != "done":
            continue
        sym = v.get("dart") or snake_to_camel(k.split(".", 1)[1])
        if not _mentions(blob, sym):
            out.append(k)
    return sorted(out)


def _normalize(value):
    """比較しやすい形に。set/tuple は並べ替えた list、dict はキーの集合として見る。"""
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, dict):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _contains_value(blob, wanted) -> bool:
    """logic.json のどこかにこの値が入っているか。**構造で**探す。

    ⚠️ 文字列一致で見てはいけない。`json.dumps` の空白の入り方が
    fixtures の書き方(indent=1)と違うだけで、載っているのに「無い」と
    判定してしまう(2026-08-21 に実際にやった)。
    """
    if _normalize(blob) == wanted:
        return True
    if isinstance(blob, dict):
        return any(_contains_value(v, wanted) for v in blob.values())
    if isinstance(blob, list):
        return any(_contains_value(v, wanted) for v in blob)
    return False


REQUIRED_IN_UI = [
    ("toris_app/lib/garden/guide_page.dart", r"predatorIsGenusLevel",
     "図鑑が属レベルの但し書きを出していない。近縁種の記録を種の事実にしない"),
    ("toris_app/lib/garden/garden_page.dart", r"didChangeAppLifecycleState",
     "前面に戻った時に庭を進めていない。初回生成でしか進まず鳥が来なくなる"),
    # 広告(2026-08-21)。**移してあるのに誰も呼んでいない**を防ぐ。
    ("toris_app/lib/garden/garden_state.dart", r"makeArrivalBonusFn",
     "今日の道具の加点をエンジンに渡していない。置いても効かない"),
    ("toris_app/lib/garden/garden_state.dart", r"isBaffleActive",
     "リス返しが餌台の連鎖に渡っていない。置いてもリスが来続ける"),
    ("toris_app/lib/garden/garden_page.dart", r"showRewardedAd",
     "リワード広告を画面から呼んでいない。道具を受け取る導線が無い"),
    ("toris_app/lib/garden/garden_page.dart", r"QuietBanner",
     "バナーを画面に置いていない"),
    ("toris_app/lib/ads/ads.dart", r"radioPlaying",
     "ラジオ再生中にバナーを黙らせていない(原則3)"),
    # ラジオ(2026-08-21)。**会った鳥だけが鳴く**をエンジンが実際に使っているか。
    # 移植でこの絞り込みが落ち、初回から未観察の鳥が鳴いていた。
    ("toris_app/lib/radio/radio_engine.dart", r"observedInBiome",
     "ラジオが観察済みの鳥に絞っていない。会っていない鳥が最初から鳴く"),
]

# ─────────────────────────────────────────────────────────────
# app.py が開いている**外部リンク**が、アプリにもあるか。
#
# ## なぜ足したか(2026-08-19 CEO)
# 「画像やウィキに飛ぶ奴、移行漏れてるよね図鑑の・なんで気づかないの?」
#
# 気づけなかった理由ははっきりしていて、**台帳は公開関数しか数えていない**。
# あの2つのリンクは `app.py` の関数の**中に直接書かれた HTML** で、関数では
# ないので台帳に載りようがなかった。画面リントも「出てはいけないもの」と
# 「あるべき呼び出し」しか見ておらず、**Python 側にあってこちらに無いもの**を
# 探す目が無かった。
#
# ここでは URL のホスト＋パスだけを見る。クエリは言語や学名で変わるため。
URL_MUST_EXIST = {
    "https://www.google.com/search": "図鑑の「実物の画像を見る」",
    "https://en.wikipedia.org/wiki/": "図鑑の「Wikipedia(英)」",
}

# 意図して持ってこなかった外部リンク(理由つき)。
URL_DROPPED = {
    "https://toris-collection.onrender.com/": (
        "Streamlit 版の配布先。Flutter は端末で動くので不要"),
}


# 画面の日本語。
#
# ⚠️ **2026-10-19 に意味が変わった。** それまでは「アプリの表示は全部英語」で、
# 画面の文字列に日本語があること自体が問題だった(一度これで作り直しになった)。
# CEO の判断で**日本語への切り替えを入れた**ので、いまの約束はこう変わる:
#
#   **英語を選んでいる人に、日本語が漏れないこと。**
#
# 日本語があってよいのは2つだけ:
#   1. 辞書そのもの(`lib/i18n.dart`)
#   2. **言語で分岐している行** — 日本語で語順が変わる文は辞書に載せられないので、
#      `L10n.lang.value == Lang.ja ? ... : ...` の形で持っている
#
# それ以外の場所の日本語は、**英語の人の画面に出る**ので問題。
JP_ALLOWED_FILES = ("i18n.dart",)
JP_GUARDED = ("L10n.lang.value == Lang.ja", "L10n.lang.value==Lang.ja")

# 分岐は**数行上**にあることがある(三項演算子が複数行に折れるため)。
# この行数だけさかのぼって目印を探す。
JP_GUARD_LOOKBACK = 4

# 英語の画面でも日本語のままでよい文字列。
# 言語の名前は、その言語で書くのが世界共通のやり方(英語の人が探せなくなる)。
JP_ALLOWED_TEXT = ("日本語",)

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


def _strip_comments_all(src: str) -> str:
    """行コメントを落とす。**説明文に書いただけ**を「有る」と数えないため。"""
    import re as _re
    return _re.sub(r"//.*", "", src)


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
            # 表示文字列の中の日本語だけを見る。
            # 辞書そのものと、言語で分岐している行は除く(上の説明を読むこと)。
            if any(a in rel for a in JP_ALLOWED_FILES):
                continue
            # 言語で分岐しているか。三項演算子が折れている場合に備えて、
            # 数行さかのぼって目印を探す。
            window = "".join(lines[max(0, n - 1 - JP_GUARD_LOOKBACK):n])
            if any(g in window for g in JP_GUARDED):
                continue
            for lit in re.findall(r"'([^'\\]*)'|\"([^\"\\]*)\"", line):
                text = lit[0] or lit[1]
                if text in JP_ALLOWED_TEXT:
                    continue
                if re.search(JP, text):
                    problems.append(
                        f"{rel}:{n} 英語を選んでいる人に日本語が漏れる\n"
                        f"        {text[:60]}")

    # あるべきものが落ちていないか。
    # 共有定数: Dart に宣言があり、かつ fixtures で突き合わせているか。
    dart_src = dart_sources()
    fx_path = os.path.join(ROOT, "toris_core", "test", "fixtures", "logic.json")
    fx_obj = None
    if os.path.exists(fx_path):
        fx_obj = json.load(open(fx_path, encoding="utf-8"))
    for py_ref, dart_name in SHARED_CONSTANTS:
        mod_name, const_name = py_ref.split(".", 1)
        try:
            # 台帳は AST で読むが、定数は**実際の値**が要るので import する。
            if PY_DIR not in sys.path:
                sys.path.insert(0, PY_DIR)
            value = getattr(__import__(mod_name), const_name)
        except Exception as e:                       # noqa: BLE001
            problems.append(f"{py_ref} を読めない({e})")
            continue
        if not is_declared(dart_name, dart_src):
            problems.append(f"{py_ref} に当たる {dart_name} が Dart に無い")
        if not _contains_value(fx_obj, _normalize(value)):
            problems.append(
                f"{py_ref} が fixtures で突き合わされていない" + chr(10)
                + "        両方に書いてもずれに気づけない。"
                  "logic_fixtures.py に足すこと")

    # 「移したのに突き合わせていない」数のラチェット。
    ledger_path = os.path.join(ROOT, "tools", "migration_ledger.json")
    ledger = json.load(open(ledger_path, encoding="utf-8"))
    unver = unverified_ports(ledger.get("items", {}))
    base = ledger.get(UNVERIFIED_KEY)
    if base is None:
        problems.append(
            f"台帳に {UNVERIFIED_KEY} が無い(いまの数は {len(unver)})")
    elif len(unver) > base:
        added = (chr(10) + "        ").join(unver[:10])
        problems.append(
            f"突き合わせていない移植が {base} 件 -> {len(unver)} 件に増えた"
            + chr(10) + "        新しく移したなら、fixtures かテストに足すこと"
            + chr(10) + f"        {added}")

    # 起動を止めうる待ち。
    for rel, pat, why in MUST_NOT_BLOCK:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path):
            problems.append(f"{rel} が無い({why})")
        elif not re.search(pat, open(path, encoding="utf-8").read()):
            problems.append(f"{rel} に {pat} が無い" + chr(10) + f"        {why}")

    for rel, pat, why in REQUIRED_IN_UI:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path):
            problems.append(f"{rel} が無い({why})")
            continue
        body = _strip_comments_all(open(path, encoding="utf-8").read())
        if not re.search(pat, body):
            problems.append(f"{rel} に {pat} が無い" + chr(10) + f"        {why}")

    # app.py の外部リンクが、アプリにも来ているか。
    app_py_path = os.path.join(PY_DIR, "app.py")
    if os.path.exists(app_py_path):
        src = open(app_py_path, encoding="utf-8").read()
        found = set(re.findall(r"https://[a-zA-Z0-9./?=&{}_+-]*", src))
        app_all = "".join(
            open(f, encoding="utf-8").read() for f in _ui_files())
        for u in sorted(found):
            base = u.split("?")[0]
            if base in URL_DROPPED:
                continue
            why = None
            for known, label in URL_MUST_EXIST.items():
                if base.startswith(known):
                    why = label
                    break
            if why is None:
                problems.append(
                    f"app.py に台帳に無い外部リンク: {base}" + chr(10) + f""
                    f"        URL_MUST_EXIST か URL_DROPPED に足すこと")
            elif base.split("?")[0] not in app_all:
                problems.append(
                    f"app.py の外部リンクがアプリに無い: {base}" + chr(10) + f""
                    f"        {why}")

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
# 規則A: **主張台帳の「検査」欄を、機械で突き合わせる。**
#
# ## なぜ足したか(2026-10-15。5回目のすり抜け)
# 2026-09-22 に「なぜ来たか」を製品から削除したとき(`885a6ee`)、
# `logic_test.dart` の3件を消した。ところが `06_監査.md` §3 の主張台帳は
# **消えたテストを指す行をそのまま残していた**:
#   ・:66「なぜ来たかは実データ(GloBI)に従う」 → 検査欄は『生態ログの突き合わせ』
#   ・:78「植えたものが虫を養い、虫が鳥を呼ぶ」 → 検査欄は『同じ検査』
# 主張そのものは嘘になっていなかった(到来は食物網で決まっており、別のテストが
# 生きていた)。**嘘だったのは検査欄のほう。** しかもその言い切りは
# 公開中の LP に載っている。台帳は人が書いた文で、**実体があるかを誰も見ていなかった。**
#
# ## 捕まえたい種類
# 「検査が消えたのに、台帳の行だけ残る」。個別の grep ではなく、
# **検査欄が名指ししたものの実在**を全行について見る。
#
# 書き方の決まりは `06_監査.md` §3-A。要点だけここにも:
#   A1. 検査欄は、バッククォートのファイル名か、かぎ括弧のテスト名を**必ず1つは**持つ
#   A2. 名指ししたファイルは**実在する**(`CLAIM_REF_GONE` に登録したものを除く)
#   A3. かぎ括弧の中身は、**実在する Dart のテスト名に含まれる**
# 検査がまだ無い行は `未整備` と書けば A1/A3 は免除。**A2 は免除しない。**
# ─────────────────────────────────────────────────────────────
CLAIM_DOC = "toris_collection/docs/team/06_監査.md"

# 検査欄がわざと名指しする「もう無い実体」。**黙って素通りさせない。**
# 理由つきでここに登録する(`URL_DROPPED` と同じ流儀)。
CLAIM_REF_GONE = {
    "toris_core/lib/src/eco_log.dart":
        "2026-09-22 に CEO 判断で製品から削除(885a6ee)。"
        "§3 の『取り下げ要』の行が、消えた実体を名指しで説明している",
    "eco_log.dart": "同上(ファイル名だけで書いてある箇所)",
}

# 「検査がまだ無い」と正直に書いている印。この行は A1/A3 を免除する。
NO_TEST_MARKS = ("未整備", "検査できない")

# 台帳が読む拡張子。コードだけでなく**画と動画**も見る(規則B で使う)。
LEDGER_EXTS = ("dart", "py", "json", "md", "html", "yaml", "png", "jpg", "mp4")

_RE_BACKTICK = __import__("re").compile(r"`([^`]+)`")
_RE_FILEREF = __import__("re").compile(
    r"^[\w./\-]+\.(?:" + "|".join(LEDGER_EXTS) + r")$")
# かぎ括弧。テスト名の中にもう一段「」が入る形
# (「食物網の統計と「足りないもの」の提案が…」)まで通す。
_RE_TESTNAME = __import__("re").compile(r"「((?:[^「」]|「[^「」]*」)*)」")
_RE_MATERIAL = __import__("re").compile(r"^[fgqrs]\d{2}_[a-z0-9_]+$")
_RE_STRIKE = __import__("re").compile(r"~~.*?~~")
_RE_LINENO = __import__("re").compile(r":\d+(?:-\d+)?$")

_FILE_INDEX = None
_TEST_NAMES = None


def _file_index() -> dict:
    """ファイル名 → リポジトリ内の相対パスの集合。生成物は見ない。"""
    global _FILE_INDEX
    if _FILE_INDEX is not None:
        return _FILE_INDEX
    skip = {".git", "build", "__pycache__", ".dart_tool", "node_modules",
            ".pytest_cache", ".gradle", ".idea", "release"}
    idx = {}
    for dp, dirs, fs in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in fs:
            if f.rsplit(".", 1)[-1].lower() in LEDGER_EXTS:
                rel = os.path.relpath(os.path.join(dp, f), ROOT)
                idx.setdefault(f, set()).add(rel.replace("\\", "/"))
    _FILE_INDEX = idx
    return idx


def _ref_exists(ref: str) -> bool:
    if "/" in ref:
        return os.path.exists(os.path.join(ROOT, ref.replace("/", os.sep)))
    return ref in _file_index()


def dart_test_names() -> set:
    """Dart のテスト名(`test('…')` / `testWidgets('…')` の第1引数)。"""
    global _TEST_NAMES
    if _TEST_NAMES is not None:
        return _TEST_NAMES
    import re
    pat = re.compile(r"\btest(?:Widgets)?\(\s*(['\"])((?:[^'\"\\]|\\.)*?)\1",
                     re.S)
    names = set()
    for base in ("toris_core/test", "toris_app/test"):
        root = os.path.join(ROOT, base.replace("/", os.sep))
        for dp, _d, fs in os.walk(root):
            for f in fs:
                if not f.endswith(".dart"):
                    continue
                src = open(os.path.join(dp, f), encoding="utf-8").read()
                for m in pat.finditer(src):
                    names.add(m.group(2))
    _TEST_NAMES = names
    return names


def _claim_doc_tables():
    """`06_監査.md` の §3(主張台帳)と §3.5(素材台帳)の行を返す。

    どちらかの表が読めなくなったら **None を返して落とす** —
    「表が消えたので検査が0件になり、黙って通る」が一番まずい。
    """
    import re
    p = os.path.join(ROOT, CLAIM_DOC.replace("/", os.sep))
    if not os.path.exists(p):
        return None, None
    lines = open(p, encoding="utf-8").read().splitlines()
    i3 = i35 = i4 = None
    for n, ln in enumerate(lines):
        if i3 is None and ln.startswith("## 3. "):
            i3 = n
        elif i3 is not None and i35 is None and ln.startswith("### 3.5"):
            i35 = n
        elif i3 is not None and i4 is None and ln.startswith("## 4."):
            i4 = n
    if i3 is None or i35 is None or i4 is None or not (i3 < i35 < i4):
        return None, None

    def rows(block):
        out = []
        for ln in block:
            s = ln.strip()
            if not (s.startswith("|") and s.endswith("|")):
                continue
            cells = [c.strip() for c in s[1:-1].split("|")]
            if all(re.fullmatch(r"[-: ]*", c) for c in cells):
                continue
            out.append(cells)
        return out

    return rows(lines[i3:i35]), rows(lines[i35:i4])


def claim_ledger_audit() -> list:
    """規則A。主張台帳の「検査」欄が、実在するものを指しているか。"""
    problems = []
    claim, _material = _claim_doc_tables()
    if claim is None:
        return [f"主張台帳 {CLAIM_DOC} の §3 / §3.5 / §4 の見出しが読めない"
                + chr(10) + "        表の形を変えたら migration_audit.py も直すこと"]
    if len(claim) < 10:
        return [f"主張台帳の行が {len(claim)} 行しか読めない(表の形が変わった?)"]

    names = dart_test_names()
    seen = 0
    for cells in claim:
        if len(cells) != 3:
            problems.append(
                "主張台帳の行の列数が3でない(セルの中に | を書いていないか): "
                + " | ".join(c[:24] for c in cells))
            continue
        what, where, check = cells
        if what.startswith("主張"):
            continue
        seen += 1
        exempt = any(m in check for m in NO_TEST_MARKS)

        # A2: 名指ししたファイルは実在する(免除しない)
        refs_check, refs_all = [], []
        for cell, bucket in ((check, refs_check), (where, None)):
            for tok in _RE_BACKTICK.findall(cell):
                t = _RE_LINENO.sub("", tok.strip())
                if _RE_FILEREF.match(t):
                    refs_all.append(t)
                    if bucket is not None:
                        bucket.append(t)
        for t in refs_all:
            if t in CLAIM_REF_GONE:
                continue
            if not _ref_exists(t):
                problems.append(
                    f"主張台帳『{what[:26]}』が指す {t} が無い" + chr(10)
                    + "        検査が消えたのに行だけ残っていないか。"
                      "わざと消えた実体を指しているなら CLAIM_REF_GONE に理由つきで足す")

        # A3: かぎ括弧の中身は、実在するテスト名に含まれる
        quoted = [] if exempt else _RE_TESTNAME.findall(check)
        for q in quoted:
            if len(q) < 6:
                continue
            if not any(q in n for n in names):
                problems.append(
                    f"主張台帳『{what[:26]}』の検査「{q[:40]}」というテストが無い" + chr(10)
                    + "        テスト名が変わった / 消えた。"
                      "かぎ括弧はテスト名にだけ使う(ほかの引用は『』)")

        # A1: 何かを名指ししているか
        if not exempt and not refs_check and not quoted:
            problems.append(
                f"主張台帳『{what[:26]}』の検査欄が、実在するものを名指ししていない"
                + chr(10)
                + "        ファイル名(バッククォート)かテスト名(かぎ括弧)を書く。"
                  "検査がまだ無いなら 未整備 と書く")
    if seen < 10:
        problems.append(f"主張台帳の主張が {seen} 件しか読めない(表の形が変わった?)")
    return problems


# ─────────────────────────────────────────────────────────────
# 規則B: **掲載素材(スクショ・動画)を台帳に載せる。**
#
# ## なぜ足したか(2026-10-15。5回目のすり抜けの、重いほう)
# 「なぜ来たか」を製品から消したあと、**文**は手当てされたのに、
# **Play に掲載中のスクリーンショット
# `marketing/phase-1/SNS部/素材/store/02_guide.png` には WHY IT CAME が映ったまま**
# 配信され続けていた。台帳が**文しか持っていなかった**ので、機能を消すときに
# 「その機能が映っている画」を探す先がどこにも無かった。
#
# ## 捕まえたい種類
# 「外に出した画が、製品より古いまま残る」。そのために:
#   B1. 台帳(`06_監査.md` §3.5)に書いた素材が**実在する**
#   B2. 外に出している素材で、**台帳に無いものが無い**
#   B3. 主張台帳が名指しした素材(`g03_song` 等)が、**素材台帳にある**
#       (出すのをやめた素材は ~~ ~~ で囲む)
#
# ⚠️ B2 の「外に出している素材」は**人の申告では取らない**。
#    `素材/` 直下と `素材/store/` の実ファイル、そして
#    **`landing/page.html` が実際に使っているトークン × `landing/build.py` の
#    差し替え表**から取る。LP に画を足せば、台帳に1行足すまで落ちる。
# ─────────────────────────────────────────────────────────────
MATERIAL_DIRS = [
    ("marketing/phase-1/SNS部/素材", (".mp4", ".png", ".jpg"),
     "SNS部が外に出す素材(直下)"),
    ("marketing/phase-1/SNS部/素材/store", (".png",),
     "Google Play の掲載素材"),
]


def _lp_materials():
    """LP が実際に埋め込んでいる画。(パス→なぜ, 問題の一覧)"""
    import re
    out, problems = {}, []
    page = os.path.join(ROOT, "landing", "page.html")
    build = os.path.join(ROOT, "landing", "build.py")
    if not (os.path.exists(page) and os.path.exists(build)):
        return out, ["landing/page.html か landing/build.py が無い"]
    psrc = open(page, encoding="utf-8").read()
    bsrc = open(build, encoding="utf-8").read()
    table = {}
    for m in re.finditer(
            r'\.replace\(\s*"(__[A-Z_]+__)"\s*,\s*data_uri\(\s*'
            r'os\.path\.join\(\s*MEDIA\s*,\s*"([^"]+)"', bsrc):
        table[m.group(1)] = "landing/media/" + m.group(2)
    for m in re.finditer(r'\(\s*"(__[A-Z_]+__)"\s*,\s*"([^"]+)"\s*\)', bsrc):
        table[m.group(1)] = "landing/media/" + m.group(2)
    for m in re.finditer(r'^(ICON|PLATE)\s*=\s*os\.path\.join\(([^)]*)\)',
                         bsrc, re.M):
        parts = re.findall(r'"([^"]+)"', m.group(2))
        if parts:
            table["__%s__" % m.group(1)] = "/".join(parts)
    for tok in sorted(set(re.findall(r"__[A-Z_]+__", psrc))):
        if tok not in table:
            problems.append(
                f"LP に {tok} があるが landing/build.py が差し替えていない"
                + chr(10) + "        公開すると穴が開く")
            continue
        out[table[tok]] = f"LP が {tok} として埋め込んでいる"
    return out, problems


def published_materials():
    """外に出している素材 → なぜ外に出ているか。"""
    out, problems = {}, []
    for rel, exts, why in MATERIAL_DIRS:
        d = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isdir(d):
            problems.append(f"素材の置き場 {rel} が無い")
            continue
        for f in sorted(os.listdir(d)):
            if os.path.isfile(os.path.join(d, f)) and f.lower().endswith(exts):
                out[f"{rel}/{f}"] = why
    lp, lp_problems = _lp_materials()
    out.update(lp)
    problems += lp_problems
    return out, problems


def material_ledger_audit() -> list:
    """規則B。素材台帳(§3.5)と、外に出している実体が合っているか。"""
    problems = []
    claim, material = _claim_doc_tables()
    if material is None:
        return [f"素材台帳 {CLAIM_DOC} §3.5 が読めない"]
    if len(material) < 10:
        return [f"素材台帳の行が {len(material)} 行しか読めない(表の形が変わった?)"]

    listed = {}
    for cells in material:
        if len(cells) != 3:
            problems.append("素材台帳の行の列数が3でない: "
                            + " | ".join(c[:24] for c in cells))
            continue
        path_cell, _where, what = cells
        if path_cell.startswith("素材"):
            continue
        m = _RE_BACKTICK.search(path_cell)
        if not m:
            problems.append(
                f"素材台帳の1列目がバッククォートのパスでない: {path_cell[:50]}")
            continue
        p = m.group(1).strip()
        listed[p] = what
        # B1: 書いてあるものが実在するか
        if not os.path.exists(os.path.join(ROOT, p.replace("/", os.sep))):
            problems.append(
                f"素材台帳に書いてある {p} が無い" + chr(10)
                + "        素材を消したなら台帳の行も消す(素材だけ消すと台帳が嘘になる)")
        if len(what) < 12:
            problems.append(
                f"素材台帳の {p} に『何が映っているか』が書かれていない" + chr(10)
                + "        機能を消すときに grep する先なので、映っているものを書く")

    # B2: 外に出しているのに台帳に無いもの
    pub, pub_problems = published_materials()
    problems += pub_problems
    for p, why in sorted(pub.items()):
        if p not in listed:
            problems.append(
                f"外に出している素材 {p} が素材台帳({CLAIM_DOC} §3.5)に無い"
                + chr(10) + f"        {why}。1行足して『何が映っているか』を書くこと")

    # B3: 主張台帳が名指しした素材が、素材台帳にあるか
    for cells in claim or []:
        if len(cells) != 3 or cells[0].startswith("主張"):
            continue
        where = _RE_STRIKE.sub(" ", cells[1])   # 取り下げた素材は見ない
        for tok in _RE_BACKTICK.findall(where):
            t = tok.strip()
            if _RE_MATERIAL.match(t) and not any(t in p for p in listed):
                problems.append(
                    f"主張台帳『{cells[0][:26]}』が名指しする素材 {t} が素材台帳に無い"
                    + chr(10)
                    + "        出すのをやめた素材なら ~~ ~~ で囲む。"
                      "まだ出しているなら §3.5 に1行足す")
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
    _unver = unverified_ports(items)
    print(f"  移した      : {len(done)}"
          f"(うち突き合わせ無し {len(_unver)})")
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

    # ── 主張と素材 ──
    # 公に言ったことの「検査」欄が実在するか / 外に出した画が台帳にあるか。
    print("\n── 主張と素材 ──")
    claim_problems = claim_ledger_audit() + material_ledger_audit()
    if claim_problems:
        print(f"  !! {len(claim_problems)} 件")
        for p in claim_problems:
            print(f"     {p}")
    else:
        _c, _m = _claim_doc_tables()
        print(f"  問題なし(主張 {len(_c or []) - 1} 件 / 素材 {len(_m or []) - 1} 件)")

    # ── テスト ──
    test_failures = []
    if "--no-test" not in sys.argv:
        print("\n── テスト ──")
        test_failures = run_tests()
        for f in test_failures:
            print(f"  !! {f}" if not f.startswith("  ") else f)

    if broken or unknown or screen_problems or claim_problems or test_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
