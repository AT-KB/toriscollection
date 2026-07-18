"""
tutorial.py - 新規スタート向けチュートリアルの案内ステップ(スキップ可能・強制ブロックなし)

交渉不能の原則(受動的である・罰しない)を守るため、ここで作るのは
「案内文言」と「どのステップに進むか」の純粋なロジックだけ。実際の表示・
ボタン配線・session_state の読み書きは app.py 側(render_tutorial_banner)で行う。

- ポップアップでプレイをブロックしない(いつでもスキップできる)。
- ステップ2(植物を植える)は、実際に1つ植えた時点で自動的に次へ進む
  (「案内されながら進める」体験)。
- 依存は標準ライブラリのみ(tests/test_*.py と同じ、stdlib のみ・純粋関数対象の流儀)。
"""
from __future__ import annotations

from i18n import t

# ステップ数: 0=土地を選ぶ, 1=植物を植える, 2=最終案内(あとは待つだけ)
TOTAL_STEPS = 3


def resolve_step(step: int, planted) -> int:
    """実際の進行状況(植えた植物があるか)を見て、必要ならステップを繰り上げる。

    ステップ1(植物を植える)は、ユーザーが実際に1つ植えた時点で
    自動的にステップ2(最終案内)へ進む。それ以外のステップはそのまま返す
    (強制はしない、目安の繰り上げのみ)。
    """
    if step == 1 and planted:
        return 2
    return step


def advance_step(step: int) -> int:
    """「次へ」ボタンで1つ進める。TOTAL_STEPS 以上は TOTAL_STEPS に丸める
    (呼び出し側はこれを is_done() で「完了」と判定する)。"""
    return min(step + 1, TOTAL_STEPS)


def is_done(step: int) -> bool:
    """このステップ数で、もうチュートリアルを終えたと見なせるか。"""
    return step >= TOTAL_STEPS


def step_content(step: int, biome_name: str) -> dict:
    """指定ステップの案内文言(表示用)を返す。

    app.py はこれをそのまま st.markdown / st.button に渡すだけで、
    文言そのもののロジックはこの関数に閉じる(テスト容易性のため)。
    """
    step = max(0, min(step, TOTAL_STEPS - 1))
    if step == 0:
        return {
            "title": t("👋 はじめまして!ステップ 1/3: 🏞️ 土地を選びましょう"),
            "body": t(
                "庭にする土地を選びます。今は「{biome_name}」が選ばれています。"
                "このままでもOK。気が変わったら「🏞️ 庭の様子」タブの『土地を選ぶ』からいつでも"
                "変えられます。決まったらボタンを押して次に進みましょう。",
                biome_name=biome_name,
            ),
            "next_label": t("🏞️ この土地でいく →"),
        }
    if step == 1:
        return {
            "title": t("🌱 ステップ 2/3: 植物を植えましょう"),
            "body": t(
                "「🌱 植える」タブから、土地に合う植物を選んで植えてみましょう。"
                "植物が昆虫を呼び、植物と昆虫が鳥を呼び寄せます。"
                "1つ植えると、ここが自動で次のステップに進みます。"
            ),
            "next_label": t("次へ →"),
        }
    return {
        "title": t("⏳ ステップ 3/3: ここからが本番です"),
        "body": t(
            "今はまだ、庭は静かなままです。ここでアプリを閉じて、少し時間をおいて"
            "(数時間後や翌日など)また開いてみてください。あなたが離れている間に"
            "生態系が動き、鳥が来ます。戻ってきたら「🎙 ラジオ」タブで鳴き声を、"
            "「📖 図鑑」タブで出会った鳥を確かめられます。"
        ),
        "next_label": t("はじめる ✓"),
    }
