"""
i18n.py - 表示文言の多言語化(EN/JA 切替)

方針(CEO承認済み・HANDOFF_I18N_2026-07-17.md 参照):
  - プレイヤーが見る文言だけを対象にする。コメント・docstring・docs は対象外。
  - 日本語原文を辞書のキーにする。これにより日本語原文がコード内に残り、
    「いつでも日本語に復元できる」バックアップを兼ねる(別ファイルのバックアップは不要)。
  - 既定言語は "en"(CEO確定)。
  - 辞書に無いキーは日本語原文をそのまま返す(未訳が残っても落ちない)。

使い方:
    from i18n import t
    st.button(t("はじめる"))
    st.caption(t("{bird}の羽根", bird=bird_name))

Streamlit ランタイム外(テスト等)でも動く。言語は st.session_state["lang"] に
保持し、session_state が使えない環境では set_lang() で設定したモジュール既定値を使う。
"""
from __future__ import annotations

_LANGS = ("en", "ja")
_DEFAULT_LANG = "en"

# Streamlit の session_state が使えない環境(テスト等)用のフォールバック。
_fallback_lang = _DEFAULT_LANG


def get_lang() -> str:
    """現在の表示言語を返す。Streamlit の session_state を優先し、
    使えなければ set_lang() で設定したモジュール既定値(初期値 "en")。"""
    try:
        import streamlit as st
        lang = st.session_state.get("lang")
        if lang in _LANGS:
            return lang
    except Exception:
        pass
    return _fallback_lang


def set_lang(lang: str) -> None:
    """表示言語を設定する。"en" / "ja" 以外は無視する。"""
    global _fallback_lang
    if lang not in _LANGS:
        return
    _fallback_lang = lang
    try:
        import streamlit as st
        st.session_state["lang"] = lang
    except Exception:
        pass


def t(ja: str, **kwargs) -> str:
    """日本語原文 ja を現在の言語に変換して返す。

    - lang == "ja": ja をそのまま使う。
    - lang == "en": 辞書に訳があればそれを、無ければ ja をそのまま使う(落とさない)。
    - kwargs があれば .format(**kwargs) でプレースホルダを埋める。
      (str.format は未使用の名前付き引数を無視するので、余分な kwargs は安全)
    """
    if get_lang() == "ja":
        text = ja
    else:
        text = TRANSLATIONS.get(ja, ja)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def describe(entity: dict) -> str:
    """種(鳥・バイオーム等)の説明文を現在の言語で返す。

    lang == "en" で description_en があればそれを、無ければ日本語 description に
    フォールバックする。種データは Sheets 由来で description_en 列が無いことがあるため、
    フォールバックは必須(HANDOFF_I18N_2026-07-17.md §1.5)。
    """
    if get_lang() == "en":
        en = entity.get("description_en")
        if en:
            return en
    return entity.get("description", "")


# ============================================================
# 翻訳辞書(日本語原文 → 英訳)
#
# トーン方針(交渉不能の原則5「かわいさ最優先」):
#   直訳しない。原文の です・ます調 と「〜ていた」の柔らかさを、
#   静かで あたたかい 短い英語で再現する。事務的な英語は避ける。
# ============================================================
TRANSLATIONS: dict[str, str] = {
    # ── badges.py(会った日数の節目) ──
    # label: 図鑑カードの短い呼び名 / message: 添える一言(数字・煽りは持たない)
    "皆勤の友": "Dear Friend",
    "常連": "Regular",
    "おなじみ": "Familiar Face",
    "{bird}とはすっかり顔なじみです。": "You and {bird} are old friends now.",
    "{bird}とはよく会う仲になりました。": "You and {bird} meet often these days.",
    "{bird}とはおなじみになってきました。": "You and {bird} are getting to know each other.",

    # ── mementos.py(落とし物) ──
    # カテゴリ名
    "小枝": "Twig",
    "羽根": "Feather",
    "羽冠": "Plume",
    # 表示名・説明(かわいさ優先。事実は曲げない)
    "{bird}の止まり木の枝": "{bird}'s little perch twig",
    "{bird} が一休みしていた小枝。": "A little twig where {bird} paused to rest.",
    "{bird}の羽根": "{bird}'s feather",
    "{bird} ({sci}) の美しい羽根。": "A lovely feather from {bird} ({sci}).",
    "{bird}の冠羽": "{bird}'s crest feather",
    "{bird} の特に鮮やかな羽。とても珍しい。": "An especially bright feather from {bird}. Wonderfully rare.",
    "未知の{label}": "Unknown {label}",
    # 旧形式(過去ログ閲覧用・まれにしか出ない)
    "{biome}の小枝(旧)": "{biome} twig (old)",
    "{biome}の木の実(旧)": "{biome} nut (old)",
    "{bird}の種(旧)": "{bird}'s seed (old)",
    "{bird}の木の実(旧)": "{bird}'s nut (old)",
    "種(旧)": "Seed (old)",
    "木の実(旧)": "Nut (old)",
    "古い形式の記録": "A keepsake in an older form.",
    "現在は廃止された形式": "A form no longer in use.",

    # ── app.py(メイン画面・図鑑・使い方) ──
    '🔒 進行データ(図鑑・会った日数・落とし物など)は、この端末のこのブラウザにのみ保存されます。次にこの端末・このブラウザで開いたときは自動的に続きから始まります。ブラウザのデータを消す・別の端末や別のブラウザで開くと引き継がれません。ときどき「セーブコードを書き出す」(サイドバーの中)でバックアップしておくと安心です。': '🔒 Your progress (field guide, days met, keepsakes, and so on) is saved only in this browser on this device. Next time you open it here, you\'ll pick up right where you left off. Clearing your browser data, or opening from another device or browser, won\'t carry it over. Now and then it\'s reassuring to back up with "Export save code" (in the sidebar).',
    'はじめかた': 'Getting started',
    '### 🌍 あなたの土地': '### 🌍 Your land',
    '### 📊 コレクション状況': '### 📊 Your collection',
    '図鑑登録種数': 'Species in guide',
    '現在滞在中': 'Visiting now',
    '{n} 羽': '{n} birds',
    '植えた植物': 'Plants grown',
    '{n} 種': '{n} species',
    '落とし物': 'Keepsakes',
    '🌬️ ここを離れる': '🌬️ Step away',
    '🔄 セッションをリセット': '🔄 Reset session',
    '🪶 鳥に出会えました': '🪶 You met a bird',
    '🌿 おかえりなさい': '🌿 Welcome back',
    '🎙 ラジオ': '🎙 Radio',
    '🏞️ 庭の様子': '🏞️ Garden',
    '🌱 植える': '🌱 Plant',
    '🧪 シミュ': '🧪 Sim',
    '📖 図鑑': '📖 Guide',
    '🎁 落とし物': '🎁 Keepsakes',
    '🕸️ ネットワーク': '🕸️ Network',
    '❓ 使い方': '❓ How to',
    '### 🌳 フィールドの様子': '### 🌳 In the field',
    'ここはあなたのコレクション。一度会った鳥は、庭を離れても、ここではいつでも会える。会った鳥が増えるほどキャストは豊かになり、よく会った鳥は群れで鳴く。': "This is your collection. Once you've met a bird, you can always find it here, even after it leaves the garden. The more birds you meet, the richer the cast becomes, and the birds you meet often sing together as a flock.",
    '### 🌱 植物を植える': '### 🌱 Plant something',
    '植物が他の生き物(昆虫・鳥)と**どう相互作用するか**が、やってくる鳥を決めます。': "It's **how a plant interacts** with other creatures (insects and birds) that decides which birds come by.",
    '🧪 確率変化(鳥×植物)は「シミュ」タブで確認できます。': '🧪 You can preview how a plant shifts each bird\'s chances in the "Sim" tab.',
    '### 🌿 植えた植物': "### 🌿 Plants you've grown",
    '### 🧪 シミュレーター': '### 🧪 Simulator',
    '「この土地に、この植物を植えたら、この鳥の出現確率がどう変わるか」を試せます。実際に植えたり植え替えたりする前に、効果を確認するためのツールです。': 'Try out "if I plant this here, how would this bird\'s chances change?" A tool for checking the effect before you actually plant or replant anything.',
    '🌍 土地': '🌍 Land',
    '📅 {month}月 · 🌡️ {temp}℃': '📅 Month {month} · 🌡️ {temp}℃',
    '### 📖 鳥類図鑑': '### 📖 Bird guide',
    '### 🎁 鳥たちの落とし物': '### 🎁 What the birds left behind',
    '鳥が立ち寄ったとき、ときどき小さな宝物を残していくことがあります。': 'When a bird stops by, it will now and then leave a little treasure behind.',
    '表示': 'View',
    '### 🕸️ 生態系ネットワーク': '### 🕸️ Ecosystem network',
    'あなたの土地で今、活きている**種のつながり**を可視化します。**中心にあるほどハブ種**(多くの種とつながる重要な種)です。植物・昆虫・食物経路がある鳥のみ表示しています。': 'A picture of the **living connections** among species in your land right now. **The closer to the center, the more of a hub** a species is (an important one, tied to many others). Only birds with a plant, insect, or food path are shown.',
    '## ❓ Toris Collection の使い方': '## ❓ How to play Toris Collection',
    'クローズドテスト中のためフィードバックを歓迎しています。': "We're in closed testing and would love your feedback.",
    '🔊 {name}の鳴き声 (xeno-canto未読込)': "🔊 {name}'s call (xeno-canto not loaded)",
    '🔊 聴く': '🔊 Listen',
    '植物を植えて時間を進めると、ここに鳥たちが現れます。': 'Plant something and let time pass — the birds will appear here.',
    '朝': 'Morning',
    '夕': 'Evening',
    '夜': 'Night',
    'この端末に保存されていた進行データを自動で読み込めませんでした(壊れているか、対応していない形式のようです)。セーブコードをお持ちの場合は、下から読み込んで再開してください。': "We couldn't automatically load the progress saved on this device (it seems corrupted or in an unsupported format). If you have a save code, load it below to pick up where you left off.",
    '▶ はじめる': '▶ Begin',
    'セーブコードを貼り付け': 'Paste your save code',
    'またはセーブファイルを選ぶ': 'Or choose a save file',
    '📥 読み込んで再開': '📥 Load and resume',
    'チュートリアルをスキップ': 'Skip the tutorial',
    '💾 セーブコード(バックアップ)': '💾 Save code (backup)',
    '進行データはこの端末に自動保存されています(次回もこのまま続きから始まります)。別の端末へ引き継ぐ・念のため保管しておきたい時だけ、下のボタンでコピーしてください。': "Your progress is saved automatically on this device (you'll pick up from here next time too). Only when you want to move to another device, or keep a copy just in case, use the button below to copy it.",
    'うまくいかない場合はこちら': 'Having trouble? Try here',
    '滞在中の鳥をクリア。植えた植物と図鑑は保持。': 'Clears the birds currently visiting. Your plants and field guide are kept.',
    'この端末の今のセッションを終了し、開始画面に戻ります(ログイン概念はないため「ログアウト」ではありません)。セーブコードを書き出していないデータは失われます。': 'Ends the current session on this device and returns to the start screen (there\'s no login, so this isn\'t a "log out"). Any progress you haven\'t exported as a save code will be lost.',
    'とじる': 'Close',
    '庭を見る': 'View the garden',
    '### 🏞️ 土地を選ぶ': '### 🏞️ Choose your land',
    'バイオーム': 'Biome',
    '### 🐦 今、ここにいる鳥たち': '### 🐦 Birds here right now',
    '嵐や伐採で庭の植物が倒れても、ここで鳴く鳥は減りません。渡り鳥は季節が外れると一時的に引っ込みます。よく観察した鳥ほど近くで・群れで聞こえます。': "Even if a storm or felling knocks the plants down, the birds that sing here don't dwindle. Migratory birds slip away for a while when their season passes. The more you've watched a bird, the nearer — and more in chorus — you'll hear it.",
    '庭をはじめると、あなたが出会った鳥たちの声が聴けます。': "Once you start a garden, you can hear the voices of the birds you've met.",
    '土地が一杯です。新しく植えるには、下の「植えた植物」から1つ抜いてください。': 'Your land is full. To plant something new, remove one from "Plants you\'ve grown" below.',
    '🗑️ 全部抜く': '🗑️ Clear all',
    'まだ何も植えていません。': 'Nothing planted yet.',
    '**🐦 鳥を選ぶ**': '**🐦 Choose a bird**',
    '鳥': 'Bird',
    '**🌱 追加候補の植物を選ぶ**': '**🌱 Choose a plant to try adding**',
    '植物': 'Plant',
    '(既に植え済み・効果は反映済み)': '(already planted — effect included)',
    '並び': 'Sort',
    'まだネットワークがありません。植物を植えてみましょう。': 'No network yet. Try planting something.',
    '濃い緑=植えた植物 / 色付き大=来た鳥 / 淡色=未訪問の鳥や昆虫': 'Deep green = plants you grew / large & colored = birds that came / pale = birds and insects not yet visited',
    '🔄 基本のサイクル': '🔄 The basic cycle',
    '\n        1. **土地(都市)を選ぶ**: 京都・シャーロットの2つから選びます。それぞれ気候と生息する鳥が違います。\n        2. **植物を植える**: その土地に合う植物を選んで植えます。植物が昆虫を呼び、植物と昆虫が鳥を呼び寄せます。\n        3. **しばらく待つ**: アプリを閉じている間にも、生態系は時間とともに動きます。次に開いたとき、新しい鳥が来ているかもしれません。\n        4. **鳥を眺める・聴く**: フィールドに来た鳥たちのキャストを聴いたり、図鑑で詳細を確認したりできます。\n           はじめて出会った鳥・久しぶりに来た鳥は、ポップアップでお知らせします。\n        5. **落とし物を集める**: 鳥はときどき羽根や小枝などの宝物を残します。集めるごとに図鑑が充実します。\n        6. **庭のラジオを聴く**: 図鑑に載った鳥たちが掛け合いで鳴くアンビエントラジオ。出会った鳥が多いほどキャストが豊かになります。季節は1週間ごとに巡り、渡り鳥はいない季節はラジオから消えます。\n        ': "\n        1. **Choose a land (city)**: Pick one of two — Kyoto or Charlotte. Each has its own climate and its own birds.\n        2. **Plant something**: Choose plants that suit the land. Plants call insects, and plants and insects together draw in the birds.\n        3. **Wait a while**: Even while the app is closed, the ecosystem keeps moving with time. Next time you open it, a new bird may have come.\n        4. **Watch and listen**: Listen to the cast of birds that came to the field, or check their details in the guide.\n           A bird you meet for the first time, or one that returns after a long while, is announced with a popup.\n        5. **Collect keepsakes**: Birds sometimes leave treasures like feathers and twigs. Each one you gather fills out your guide.\n        6. **Listen to the garden radio**: An ambient radio where the birds in your guide sing back and forth. The more birds you've met, the richer the cast. The seasons turn each week, and migratory birds leave the radio in seasons they're away.\n        ",
    '🐦 鳥に出会えた時': '🐦 When you meet a bird',
    '\n        庭で鳥に出会う(留守のあいだに来ていた・「♪ 耳を澄ます」で近くまで来てくれた)と、\n        ポップアップでお知らせします。\n\n        - **はじめての種**: 「はじめまして! 新しく図鑑に登録されました」と表示され、図鑑にすぐ反映されます。\n        - **すでに図鑑にいる種**: 「また会えました」と、再会をやわらかく伝えます。\n\n        「♪ 耳を澄ます」で鳥に近づいているときは、しばらく待つと自動的に記録されます\n        (止めるボタンを押さなくても大丈夫です)。\n        ': '\n        When you meet a bird in the garden (it came while you were away, or drew near through "♪ Listen closely"),\n        a popup lets you know.\n\n        - **A new species**: it shows "Nice to meet you! Newly added to your guide," and appears in your guide right away.\n        - **A species already in your guide**: it gently notes "Met again," a soft welcome-back.\n\n        While you\'re drawing near a bird with "♪ Listen closely," it\'s recorded automatically if you wait a moment\n        (no need to press the stop button).\n        ',
    '📐 出現確率の仕組み(図鑑の「なぜこの確率?」)': '📐 How appearance chance works (the guide\'s "Why this chance?")',
    '\n        各鳥の出現確率は、4つの係数の積で計算されます。\n\n        ```\n        確率 = 気温適合度 × バイオーム補正 × 食物係数 × レア度係数 × 0.5\n        ```\n\n        - **気温適合度 (temp_fit)**: 0〜1の値。その鳥の好む気温域の中心に近いほど1に近い、外れるほど0に近い。\n        - **バイオーム補正 (biome_bonus)**: 1.0(好む土地) または 0.15(それ以外)。\n        - **食物係数 (food_factor)**: 食物スコア(植物・昆虫からのエサ経路の合計重み)から計算。経路が太いほど高い。\n        - **レア度係数 (rarity_factor)**: 1 - rarity*0.85 で、レアな種ほど1未満に下がる。生態ネットワーク上の重要度(補正済PageRank)を反映。\n        - 末尾の **× 0.5** は、滞在2-4種に落ち着かせるための全体倍率。\n\n        **食物経路** の表示は、その鳥が来る原因となった「植物 → 昆虫 → 鳥」または「植物 → 鳥」の経路と、各経路の重み(寄与度)です。\n        ': '\n        Each bird\'s appearance chance is the product of four factors.\n\n        ```\n        chance = temp fit × biome bonus × food factor × rarity factor × 0.5\n        ```\n\n        - **temp fit (temp_fit)**: a value from 0 to 1. Nearer the center of the bird\'s preferred temperature range, the closer to 1; further out, the closer to 0.\n        - **biome bonus (biome_bonus)**: 1.0 (a land it favors) or 0.15 (otherwise).\n        - **food factor (food_factor)**: computed from the food score (the total weight of feeding paths from plants and insects). The thicker the paths, the higher.\n        - **rarity factor (rarity_factor)**: 1 - rarity*0.85, so rarer species dip below 1. It reflects importance in the ecological network (adjusted PageRank).\n        - The trailing **× 0.5** is an overall multiplier that settles visits to around 2-4 species.\n\n        The **food paths** shown are the "plant → insect → bird" or "plant → bird" routes that brought the bird, along with each route\'s weight (its contribution).\n        ',
    '⏳ 不在中ループ': '⏳ The away-time loop',
    '\n        アプリを閉じていた時間に応じて、自動で生態系が複数サイクル進化します。\n\n        | 経過時間   | 進化サイクル数 |\n        |-----------|--------------|\n        | 5分未満    | 0            |\n        | 5-30分     | 1            |\n        | 30分-2時間 | 2            |\n        | 2-6時間    | 3            |\n        | 6-12時間   | 4            |\n        | 12-24時間  | 5            |\n        | 24時間以上 | 6 (上限)     |\n\n        各サイクルでは滞在中の鳥について退去判定、その後新規到着判定(1サイクル最大1羽、滞在最大4羽)が走ります。\n        ': '\n        Depending on how long the app was closed, the ecosystem evolves through several cycles automatically.\n\n        | Time away    | Evolution cycles |\n        |-------------|------------------|\n        | Under 5 min  | 0                |\n        | 5-30 min     | 1                |\n        | 30 min-2 hr  | 2                |\n        | 2-6 hr       | 3                |\n        | 6-12 hr      | 4                |\n        | 12-24 hr     | 5                |\n        | 24 hr+       | 6 (max)          |\n\n        In each cycle, the birds currently visiting are checked for departure, then new arrivals are checked (up to 1 per cycle, up to 4 visiting at once).\n        ',
    '🎁 落とし物のしくみ': '🎁 How keepsakes work',
    '\n        鳥が立ち寄ったとき、低確率で3カテゴリのいずれか1つを落とします。\n        すべての鳥が同じ「小枝」「羽根」の2種類を持ち、一部の鳥だけが特別な「羽冠」も持ちます。\n\n        | カテゴリ | 確率 | 内容 |\n        |---------|-----|------|\n        | 🌿 小枝   | 10% | その鳥が止まっていた小枝(一番出やすい) |\n        | 🪶 羽根   | 5% | その鳥の羽根 |\n        | ✨ 羽冠   | 4% | 一部の鳥だけが持つ冠羽(隠しレア・出会いのご褒美) |\n\n        判定はレア順(羽冠→羽根→小枝)に行われ、最初に当選したカテゴリを返します(複数同時には出ない)。\n        合わせて約16.5%、つまり訪問6回に1回くらい何か出ます。\n\n        全コンプリートで **小枝26種 + 羽根26種 + 羽冠(一部の鳥のみ)** のコレクションになります。\n        ': '\n        When a bird stops by, there\'s a small chance it drops one of three categories.\n        Every bird carries the same two — "twig" and "feather" — and only some birds also carry a special "plume."\n\n        | Category | Chance | What it is |\n        |---------|-----|------|\n        | 🌿 Twig   | 10% | A twig the bird perched on (the most common) |\n        | 🪶 Feather | 5% | The bird\'s feather |\n        | ✨ Plume   | 4% | A crest feather only some birds have (a hidden rarity, a reward for meeting) |\n\n        Checks run in order of rarity (plume → feather → twig) and return the first category that wins (never more than one at once).\n        Together that\'s about 16.5%, so roughly one keepsake every six visits.\n\n        A full set is **26 twigs + 26 feathers + plumes (from some birds only)**.\n        ',
    '🌡️ 土地と気温(月による変化)': '🌡️ Land and temperature (month by month)',
    '\n        気温は次の式で決まります。\n\n        ```\n        気温 = バイオームの平均気温 + 月ごとのオフセット\n        ```\n\n        月オフセット(北半球): 1月=-6、2月=-5、3月=-2、4月=+1、5月=+4、6月=+6、7月=+8、8月=+8、9月=+5、10月=+1、11月=-2、12月=-5\n\n        現在の土地(京都・シャーロット)はどちらも北半球のため、このオフセットがそのまま使われます。\n\n        月は現実時間と同期します(プレイヤーは時間を進める操作はできません)。\n        ': "\n        Temperature is set by this formula.\n\n        ```\n        temperature = biome's average temperature + monthly offset\n        ```\n\n        Monthly offset (Northern Hemisphere): Jan=-6, Feb=-5, Mar=-2, Apr=+1, May=+4, Jun=+6, Jul=+8, Aug=+8, Sep=+5, Oct=+1, Nov=-2, Dec=-5\n\n        The current lands (Kyoto and Charlotte) are both in the Northern Hemisphere, so this offset is used as-is.\n\n        The month follows real-world time (players can't fast-forward it).\n        ",
    '💾 データの所在(この端末にのみ保存)': '💾 Where your data lives (only on this device)',
    '\n        進行データ(バイオーム・植えた植物・図鑑・会った日数・落とし物・メモなど)は、\n        この端末のこのブラウザにのみ保存されます。サーバーには送られません。\n\n        - **同じ端末・同じブラウザなら、開くだけで自動的に続きから始まります**\n          (裏でセーブコードを自動保存しているため、毎回読み込み直す必要はありません)。\n        - ブラウザのデータを消す・別の端末や別のブラウザで開く時は、記録は自動では\n          引き継がれません。サイドバーの「💾 セーブコード(バックアップ)」から、\n          いつでも進行データを1本のコードとして書き出せます。書き出したコードは、\n          開始画面の「セーブコードを読み込んで再開」から読み込むと復元できます。\n        - 「📋 セーブコードをコピー」ボタンを押すだけで、クリップボードに\n          コピーされます(メモアプリなどに貼り付けて保管してください)。\n          うまくいかない場合は、同じ場所にある「⬇️ セーブコードを書き出す」、\n          「💾 セーブコードを共有」ボタン(共有シート経由)、\n          コードを直接選択してコピーする欄もお使いいただけます。\n        - セーブコードは手元で保管するものです(サーバーには送信されません)。\n          失くすと復元できないので、大事な節目でときどき書き出しておくのがおすすめです。\n        ': '\n        Your progress (biome, plants grown, field guide, days met, keepsakes, notes, and so on) is\n        saved only in this browser on this device. It\'s never sent to a server.\n\n        - **On the same device and browser, just opening it picks up where you left off**\n          (a save code is auto-saved in the background, so there\'s no need to reload each time).\n        - When you clear your browser data, or open from another device or browser, your record isn\'t\n          carried over automatically. From "💾 Save code (backup)" in the sidebar, you can\n          export your progress as a single code anytime. That exported code can be restored\n          from "Load a save code and resume" on the start screen.\n        - Just press the "📋 Copy save code" button to copy it to your clipboard\n          (paste it into a notes app to keep it safe).\n          If that doesn\'t work, in the same place you\'ll also find "⬇️ Export save code,"\n          the "💾 Share save code" button (via the share sheet),\n          and a field to select and copy the code directly.\n        - The save code is yours to keep (it\'s never sent to a server).\n          If you lose it there\'s no recovery, so it\'s good to export one now and then at meaningful moments.\n        ',
    '📺 広告について(すべて任意)': '📺 About ads (all optional)',
    '\n        広告は庭の下部にある、完全に任意の応援広告だけです。\n\n        - 「🎁 応援広告(庭に道具をひとつ)」を見ると、アメリカの裏庭バードウォッチング\n          文化の道具(バードフィーダー・バードバス等、全6種)から**ランダムで1つ**、\n          庭に6時間だけ置けます。1日1回だけの、完全に任意のおまけです。\n        - 置いたアイテムは、対象の鳥(アイテムごとに異なる)の到来確率を6時間だけ\n          わずかに(+1〜6ポイント程度)後押しするか、鳥の滞在時間を少し延ばします。\n          効果は常にプラス方向だけで、見なかった場合に何かが減ったり不利になったり\n          することは一切ありません。\n        - 鳥の声・ラジオ・図鑑そのもの、そして通常(アイテムなし)の到来確率・\n          コレクションの進み方は、広告を見ても見なくても変わりません。\n        ': '\n        The only ad is the entirely optional support ad at the bottom of the garden.\n\n        - Watching "🎁 Support ad (one tool for your garden)" lets you place **one random tool**\n          from American backyard birdwatching culture (bird feeder, bird bath, and so on — 6 in all)\n          in your garden for just 6 hours. A completely optional extra, once a day.\n        - A placed item gives the target bird (which differs per item) a small nudge to its\n          arrival chance for 6 hours (about +1 to 6 points), or slightly extends how long birds stay.\n          The effect is always positive — nothing is ever reduced or made worse if you don\'t watch.\n        - The bird calls, the radio, the guide itself, and the normal (item-free) arrival chances\n          and collection pace don\'t change whether you watch an ad or not.\n        ',
    '相互作用データはGloBI(Global Biotic Interactions)の実データを参照して構築したシード': 'The interaction data is a seed built from real records in GloBI (Global Biotic Interactions).',
    '{name}の鳴き声を取得中...': "Fetching {name}'s call...",
    '{month}月 {temp}℃': 'Month {month}, {temp}℃',
    '土地を選び、植物を植え、時間が経つのを待つ。やってきた鳥たちの声に耳を澄まそう。': 'Choose a land, plant something, and wait for time to pass. Listen closely to the birds that come.',
    '書き出しておいたセーブコードをここに貼り付けてください': 'Paste the save code you exported here',
    '📅 {month}月': '📅 Month {month}',
    '🌡️ 気温 <b>{temp}℃</b>': '🌡️ Temp <b>{temp}℃</b>',
    '💧 降水量 <b>{precip}mm/年</b>': '💧 Rainfall <b>{precip} mm/yr</b>',
    '⬇️ セーブコードを書き出す': '⬇️ Export save code',
    '⬆️のボタンで反応がない場合は、ここから選択してコピーできます': "If the button above doesn't respond, you can select and copy from here",
    '🔬 生態的な重要度スコア: {n}種で有効': '🔬 Ecological importance score: active with {n} species',
    '🔬 生態的な重要度スコア: シードrarityのみ使用': '🔬 Ecological importance score: using seed rarity only',
    '{n}日ぶりです。留守のあいだに——': "It's been {n} days. While you were away —",
    '🕊 {names} は旅立っていきました': '🕊 {names} set off on their way',
    '🎁 新しい落とし物が {n} 個あります': '🎁 {n} new keepsakes are waiting',
    '🎙 新しい声がラジオの顔ぶれに加わりました。聴きに行けます。': "🎙 A new voice has joined the radio's cast. Come have a listen.",
    '🪶 {names} に会えました!図鑑に詳細なアイコンが登録され、ラジオにも加わります。': '🪶 You met {names}! A detailed icon joins your guide, and its voice joins the radio.',
    '🪶 {names} にまた会えました。図鑑の観察記録が増えます。': "🪶 You met {names} again. Another mark in your guide's log.",
    '🎁 広告を見てくれてありがとう。今日は「{label}」を庭に置きました(6時間)。': '🎁 Thanks for watching. Today we\'ve set "{label}" out in your garden (6 hours).',
    '出来事を見る': 'See what happened',
    '⚠️ {biome} に移ると、現在の植物と滞在中の鳥はリセットされます。': '⚠️ Moving to {biome} will reset your current plants and the birds visiting now.',
    '✓ {biome} に移る': '✓ Move to {biome}',
    'まだ鳥は来ていません。植物を植えて、しばらくしてからまた覗いてみましょう。': 'No birds yet. Plant something and peek back in a little while.',
    '🎙 庭のラジオ': '🎙 Garden radio',
    '今は{season}': "It's {season} now",
    'あと{n}週で次の季節へ': '{n} weeks until the next season',
    '土地の収容力: {now} / {max} 種': 'Land capacity: {now} / {max} species',
    '{biome}は最大 {max} 種まで植えられます': 'You can plant up to {max} species in {biome}',
    '🔍 計算の内訳': '🔍 Behind the numbers',
    '**{bird} の出現確率の構成**': "**How {bird}'s appearance chance breaks down**",
    '会った日数 {d}日・皆勤の友': 'Met on {d} days · Dear Friend',
    'まだ鳥が来ていません。先にホーム画面で鳥との出会いを待ちましょう。': 'No birds yet. Wait for your first meeting on the home screen first.',
    '🌱 植物': '🌱 Plants',
    '{n}種': '{n} species',
    '🐛 昆虫': '🐛 Insects',
    '🐦 来うる鳥': '🐦 Birds that may come',
    '🔗 相互作用': '🔗 Interactions',
    '{n}本': '{n} links',
    '💡 今のハブ種: **{label}** ({kind}, {n}本のつながり)': '💡 Current hub species: **{label}** ({kind}, {n} connections)',
    '🔒 この鳥の声はNC(非商用)音源のため、録音準備中です。図鑑や庭での観察は、これまでどおり楽しめます。': "🔒 This bird's call comes from a non-commercial (NC) source, so the recording is still being prepared. You can enjoy the guide and watching in the garden just as before.",
    '録音が見つかりませんでした(xeno-cantoに登録なしまたは接続失敗)': 'No recording found (not listed on xeno-canto, or the connection failed)',
    'セーブコードを貼り付けるか、ファイルを選んでください。': 'Please paste a save code or choose a file.',
    'アプリ版(サイドロード)では反応しないことがあります。その場合は上の「📋 セーブコードをコピー」ボタン、右下に出る「💾 セーブコードを共有」ボタン、または下のコピー欄をお使いください。': 'On the sideloaded app version this may not respond. If so, use the "📋 Copy save code" button above, the "💾 Share save code" button at the lower right, or the copy field below.',
    'しばらくぶりです。留守のあいだに——': "It's been a little while. While you were away —",
    'この広告リワードは、アプリ版(Android)でのみご利用いただけます。': 'This ad reward is available only in the app version (Android).',
    '🌿 庭の移ろい': '🌿 How the garden shifted',
    '🌙 不在中の出来事: {summary}': '🌙 While you were away: {summary}',
    '{emoji} 今日は「{name}」を置いています(あと{hrs}時間)。': '{emoji} Today "{name}" is set out (for {hrs} more hours).',
    '🌿 アプリを閉じている間にも、フィールドの生態系は動き続けます。次にここを訪れたとき、新しい鳥が来ているかもしれません。': "🌿 Even while the app is closed, the field's ecosystem keeps moving. Next time you visit, a new bird may have come.",
    '適温: {lo}-{hi}℃': 'Comfort range: {lo}-{hi}℃',
    '変化なし': 'No change',
    '**現状(before)**': '**Now (before)**',
    '気温適合度: {v}': 'Temp fit: {v}',
    'バイオーム補正: ×{v}': 'Biome bonus: ×{v}',
    '食物スコア: {v}': 'Food score: {v}',
    'レア度係数: {v}': 'Rarity factor: {v}',
    '**追加後(+{plant})**': '**After adding (+{plant})**',
    '**追加後の食物経路**': '**Food paths after adding**',
    '会った日数 {d}日・常連': 'Met on {d} days · Regular',
    '**適温域:** {lo}〜{hi}℃': '**Comfort range:** {lo}–{hi}℃',
    '**好む環境:** {biomes}': '**Prefers:** {biomes}',
    '食物経路がつながっている鳥の数': 'Number of birds linked by a food path',
    '植えた植物(入力)': 'Plants grown (input)',
    '来た鳥(出力)': 'Birds that came (output)',
    '未訪問の鳥': 'Birds not yet visited',
    '昆虫': 'Insects',
    '再生エラー: {e}': 'Playback error: {e}',
    '🌱 新規スタート': '🌱 Start fresh',
    '📥 セーブコードを読み込んで再開': '📥 Load a save code and resume',
    'セーブコードを読み込めませんでした。コードが壊れているか、対応していない形式です。': "Couldn't load the save code. It's corrupted or in an unsupported format.",
    '✨ *はじめまして! 新しく図鑑に登録されました*': '✨ *Nice to meet you! Newly added to your guide*',
    'また会えました。図鑑の観察記録が増えます。': "Met again. Another mark in your guide's log.",
    '✨ はじめまして、**{name}**! 新しく図鑑に登録されました': '✨ Nice to meet you, **{name}**! Newly added to your guide',
    '**{name}** が来ていました': '**{name}** had come by',
    '広告を最後まで見られなかったため、今回は受け取れませんでした。またいつでもどうぞ。': "The ad wasn't finished, so there's nothing to receive this time. Come back anytime.",
    '✨ 新しい落とし物が {n} 個': '✨ {n} new keepsakes',
    '{plant}を抜く': 'Remove {plant}',
    '- {name} (寄与 {w})': '- {name} (contribution {w})',
    '会った日数 {d}日・おなじみ': 'Met on {d} days · Familiar Face',
    '(レア度 {stars})': '(rarity {stars})',
    '🪶 近くで観察できた回数: {n}回': '🪶 Times watched up close: {n}',
    '🖼️ 実物の画像を見る': '🖼️ See a real photo',
    '📖 Wikipedia(英)': '📖 Wikipedia (EN)',
    '**食べるもの:**': '**Eats:**',
    '現状の出現確率: {p}': 'Current appearance chance: {p}',
    'なぜこの確率?': 'Why this chance?',
    '- 気温適合度: {v}': '- Temp fit: {v}',
    '- バイオーム補正: ×{v}': '- Biome bonus: ×{v}',
    '- 食物スコア: {s} → 係数 {f}': '- Food score: {s} → factor {f}',
    '- レア度係数: {v}': '- Rarity factor: {v}',
    '**🎯 この鳥を呼ぶには**': '**🎯 How to invite this bird**',
    '**🎁 この鳥にまつわる落とし物**': '**🎁 Keepsakes from this bird**',
    '**🌤 これまでの来訪理由**': '**🌤 Why it has come before**',
    '🔭 まだ遠くから気配を感じただけ。近くまで来てくれたら、詳しい生態が記録されます。': '🔭 So far just a distant hint of its presence. When it comes closer, its details will be recorded.',
    '環境を整えて、出会えるのを待ちましょう。': 'Set the scene, and wait to meet it.',
    '落とし物別': 'By keepsake',
    '鳥別': 'By bird',
    'NEW': 'NEW',
    ' (植え済み)': ' (planted)',
    '全種': 'All species',
    '発見済みのみ': 'Discovered only',
    '未発見のみ': 'Undiscovered only',
    '地域別': 'By region',
    'レア度順': 'By rarity',
    '会った日数 {d}日': 'Met on {d} days',
    '- GloBI補正済PageRank: **{v}** (生態的な重要度スコアを使用)': '- GloBI-adjusted PageRank: **{v}** (using the ecological importance score)',
    '- 食物経路: {paths}': '- Food paths: {paths}',
    '✓ 食物条件は満たされています。あとは時間とレア度次第。': '✓ The food conditions are met. The rest is up to time and rarity.',
    '🪶 まだ {bird} の羽根は手に入っていません。': "🪶 You don't have {bird}'s feather yet.",
    '{owned} / {total} 種 ({pct}%)': '{owned} / {total} species ({pct}%)',
    'あなたの土地に来たことがあります': 'Has visited your land before',
    '🖼️ 画像を見る': '🖼️ See a photo',
    '今の <b>{biome}</b> の生態系に <b>{icon} {plant}</b> を導入すると、<b2>{bird}</b2> が来る確率は…': "If you add <b>{icon} {plant}</b> to <b>{biome}</b>'s current ecosystem, <b2>{bird}</b2>'s chance of visiting becomes…",
    '{plant}を植える': 'Plant {plant}',
    'これまで出会った土地:': "Lands you've visited so far:",
    # ── radio.py(庭のラジオ) ──
    '🎙 ラジオを始める': '🎙 Start the radio',
    '■ 止める': '■ Stop',
    '{season}の庭のラジオ': '{season} garden radio',
    '🏯 京都': '🏯 Kyoto',
    '🌳 シャーロット': '🌳 Charlotte',
    '🎧 ヒーリングBGMスイッチ': '🎧 Healing BGM switch',
    '同じ環境を好み、採餌のしかたが近い鳥ほど一緒に現れます': 'Birds that favor the same surroundings and forage in similar ways appear together',
    '{total}羽 ({n}種)': '{total} birds ({n} species)',
    '{n}羽': '{n} birds',
    'xeno-canto APIキーが設定されていません。鳴き声機能を有効にするには、Streamlit Cloud では secrets に `xc_api_key`、環境変数なら `XC_API_KEY`、ローカルなら `xc_api_key.txt` のいずれかでキーを設定してください。': 'No xeno-canto API key is set. To enable calls, set a key one of these ways: `xc_api_key` in secrets on Streamlit Cloud, the `XC_API_KEY` environment variable, or an `xc_api_key.txt` file locally.',
    '庭を選ぶ': 'Choose a garden',
    '🕒 今の時間のまま': '🕒 Keep the current time',
    '🌅 朝の庭': '🌅 Morning garden',
    '🌞 昼の庭': '🌞 Midday garden',
    '🌆 夕方の庭': '🌆 Evening garden',
    '🌙 夜の庭': '🌙 Night garden',
    '鳴く時間帯': 'Time of day for song',
    '鳥の声は控えめになり、環境音がやわらかく主役になります。作業や就寝のお供に。': 'The bird calls soften and the ambient sounds gently take the lead. A companion for work or drifting off to sleep.',
    '{biome}で鳥に出会うと、ここで声が聴けるようになります。': 'Once you meet birds in {biome}, you can hear their voices here.',
    '今の季節({season})に鳴ける鳥がいません。他の季節にまた来てください。': 'No birds can sing in the current season ({season}). Come back in another season.',
    '声を集めています…': 'Gathering voices…',
    '今、庭で選んでいる土地に自動的に合わせます。過去にコレクションした別の土地の顔ぶれを聴きたい時だけ、ここで一時的に切り替えられます。': "This follows the land you've chosen in the garden automatically. Only when you want to hear the cast of another land you've collected before can you switch here temporarily.",
    '既定はこの端末の今の時間に合わせて鳴きます(朝はさえずり、夜は静かに)。試しに別の時間帯の雰囲気を聴くこともできます。': "By default the birds sing to this device's current time (chirping in the morning, quiet at night). You can also sample the mood of another time of day.",
    '🔒 今日の顔ぶれの声はNC(非商用)音源のため、録音準備中です。図鑑や庭での観察はこれまでどおり楽しめます。': "🔒 Today's cast comes from non-commercial (NC) sources, so the recordings are still being prepared. You can enjoy the guide and watching in the garden just as before.",
    '音源を取得できませんでした。': "Couldn't fetch the audio.",
    '{season}に来る': 'Comes in {season}',
    '🌟 <b>{label}</b> が新しく加わりました': '🌟 <b>{label}</b> has newly joined',
    ' — 会いに行った鳥が、ラジオの顔ぶれに増えています。': " — the bird you went to meet has joined the radio's cast.",
    '🔗 今日の顔ぶれ': "🔗 Today's cast",
    '🗂 コレクション {total} 羽 · 今の季節に {n} 羽が鳴ける': '🗂 Collection: {total} birds · {n} can sing this season',
    # ── ritual.py(耳を澄ます) ──
    '{col}鳥': '{col} bird',
    '♪ 耳を澄ます': '♪ Listen closely',
    '■ 終わる': '■ End',
    '♪ 鳥に会いに行く ({n}羽)': '♪ Go meet the birds ({n})',
    '🪶 %HINT%、%NAME% に出会えた！': '🪶 %HINT% — you met %NAME%!',
    '🕊 %HINT% は庭の向こうへ去った': '🕊 %HINT% slipped away beyond the garden',
    '{plant}にとまっていた{col}鳥': 'A {col} bird that perched on {plant}',
    '鳥の声を呼び込んでいます…': "Calling in the birds' voices…",
    '🔒 ここにいる鳥の声はNC(非商用)音源のため、録音準備中です。図鑑や庭での観察はこれまでどおり楽しめます。': "🔒 This bird's call comes from a non-commercial (NC) source, so the recording is still being prepared. You can enjoy the guide and watching in the garden just as before.",
    '🌙 今日はもう十分に耳を澄ませました。新しい鳥が来たら、また会いに行けます。': "🌙 You've listened closely enough for today. When a new bird comes, you can go and meet it again.",
    # ── absence_loop.py(不在中ループ) ──
    '{n}日前': '{n} days ago',
    '{n}件の立ち寄り({s}種)': '{n} visits ({s} species)',
    '{bird_name}が立ち寄りました。': '{bird_name} stopped by.',
    'まもなく': 'Moments ago',
    '今しがた': 'Just now',
    '{n}分前': '{n} min ago',
    '{n}時間前': '{n} hr ago',
    '{name}が{n}回立ち寄りました': '{name} stopped by {n} times',
    '{bird_name}が来ました。{plant}に惹かれて立ち寄ったようです。': '{bird_name} came. It seems to have stopped by, drawn to {plant}.',
    '{bird_name}が来ました。{insect}を狙って立ち寄ったようです。': '{bird_name} came. It seems to have stopped by, after {insect}.',
    '{bird_name}が、{item_hint}に誘われて立ち寄りました。': '{bird_name} stopped by, tempted by {item_hint}.',
    # ── ads.py(応援広告) ──
    '🎬 広告を読み込んでいます……見終わると自動で戻ります(10秒ほど始まらない場合は自動的に終了します)。': "🎬 Loading the ad… you'll return automatically when it ends (if it doesn't start within about 10 seconds, it will close on its own).",
    'キャンセルする': 'Cancel',
    '🎁 応援広告(庭に道具をひとつ)': '🎁 Support ad (one tool for your garden)',
    '見ると、アメリカの裏庭インテリアショップから、ランダムで道具を1つもらえます。庭に6時間だけ置けるおまけです。見なくても庭の進み方はいつもどおりです。': 'Watch to receive one random tool from an American backyard décor shop. A little extra you can set out in your garden for just 6 hours. Skip it and your garden goes on just the same.',
    '▶ 広告を見て、道具をもらう': '▶ Watch the ad and get a tool',
    '🌾 広告スペース(準備中)': '🌾 Ad space (coming soon)',
    '実際の広告はまだ配信していません・ラジオ再生中は表示しません': "Real ads aren't running yet · not shown while the radio is playing",
    '{emoji} 今は「{name}」を置いています(あと{hrs}時間)。': '{emoji} "{name}" is set out right now ({hrs} hours left).',
    '✓ 今日はもう受け取りました。また明日。': "✓ You've already received today's. See you tomorrow.",
    '今のこの庭では、まだ選べる道具がありません。': 'There are no tools to choose for this garden yet.',
    # ── community.py(みんなの庭) ──
    '### 🗺 みんなの庭': "### 🗺 Everyone's gardens",
    'みんなの観察が集まって、どの土地にどの声が訪れているかの地図になります。名前も順位もありません。ただ、世界が誰かに育てられているという記録です。': "Everyone's observations gather into a map of which voices visit which lands. No names, no rankings. Just a record that the world is being tended by someone.",
    '土地を選ぶ': 'Choose a land',
    '「N の庭」はその声を迎えた庭の数です。多い少ないは賑わいであって、競争ではありません。あなたの庭も、この地図の一部です。': '"N gardens" is how many gardens have welcomed that voice. More or fewer is liveliness, not competition. Your garden, too, is part of this map.',
    'まだみんなの庭の記録がありません。鳥に会うと、その声がこの地図に静かに加わります。': 'There are no shared garden records yet. When you meet a bird, its voice quietly joins this map.',
    '{biome}には、まだみんなの庭から訪れた声がありません。': "No voices have visited {biome} from everyone's gardens yet.",
    '🌿 いま <b>{gardens}</b> の庭が、この世界を育てています。': '🌿 Right now <b>{gardens}</b> gardens are tending this world.',
    '{n} の庭': '{n} gardens',
    '{biome} に、みんなの庭から訪れている声': "Voices visiting {biome} from everyone's gardens",
    '🌟 最近': '🌟 Lately',
    # ── tutorial.py(チュートリアル) ──
    '⏳ ステップ 3/3: ここからが本番です': '⏳ Step 3/3: this is where it really begins',
    '今はまだ、庭は静かなままです。ここでアプリを閉じて、少し時間をおいて(数時間後や翌日など)また開いてみてください。あなたが離れている間に生態系が動き、鳥が来ます。戻ってきたら「🎙 ラジオ」タブで鳴き声を、「📖 図鑑」タブで出会った鳥を確かめられます。': 'For now the garden is still quiet. Close the app here, let a little time pass (a few hours later, or the next day), and open it again. While you\'re away the ecosystem moves and birds arrive. When you come back, check their calls in the "🎙 Radio" tab and the birds you\'ve met in the "📖 Guide" tab.',
    'はじめる ✓': 'Begin ✓',
    '👋 はじめまして!ステップ 1/3: 🏞️ 土地を選びましょう': '👋 Welcome! Step 1/3: 🏞️ Choose your land',
    '庭にする土地を選びます。今は「{biome_name}」が選ばれています。このままでもOK。気が変わったら「🏞️ 庭の様子」タブの『土地を選ぶ』からいつでも変えられます。決まったらボタンを押して次に進みましょう。': 'Choose the land for your garden. "{biome_name}" is selected right now. Keeping it is perfectly fine. If you change your mind, you can switch anytime from "Choose your land" in the "🏞️ Garden" tab. When you\'ve decided, press the button to move on.',
    '🏞️ この土地でいく →': '🏞️ Go with this land →',
    '🌱 ステップ 2/3: 植物を植えましょう': '🌱 Step 2/3: plant something',
    '「🌱 植える」タブから、土地に合う植物を選んで植えてみましょう。植物が昆虫を呼び、植物と昆虫が鳥を呼び寄せます。1つ植えると、ここが自動で次のステップに進みます。': 'From the "🌱 Plant" tab, choose a plant that suits your land and try planting it. Plants call insects, and plants and insects together draw in the birds. Once you plant one, this moves on to the next step automatically.',
    '次へ →': 'Next →',
    # ── daily.py(今日の庭) ──
    '{glabel}仲間。': '{glabel} companion.',
    '🎙 あなたのラジオでも、今日はきっと鳴いています。': "🎙 It's surely singing on your radio today, too.",
    'まだ会っていません。会いに行くと、ラジオに加わります。': "You haven't met it yet. Go meet it, and it joins your radio.",
    '🌅 今日の庭 — {where}': "🌅 Today's garden — {where}",
    # ── garden_items.py(庭の道具) ──
    '{emoji} {name} — 今のこの庭では対象になる鳥がいません。': "{emoji} {name} — there's no target bird for this garden right now.",
    '{emoji} {name} — この庭にはハチドリが生息していないため使えません(シャーロットの庭で使えます)。': "{emoji} {name} — can't be used here, since hummingbirds don't live in this garden (it works in the Charlotte garden).",
    # ── disturbance.py(撹乱) ──
    '{icon} {label}が庭を通り過ぎたが、植物は持ちこたえた。': '{icon} {label} passed through the garden, but the plants held on.',
    '{icon} {label}が庭を通り過ぎ、{lost}が倒れた。': '{icon} {label} passed through the garden, and {lost} was knocked down.',
}
