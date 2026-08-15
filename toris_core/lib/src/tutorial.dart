/// はじめての案内。`tutorial.py` の仕組みを引き継ぎ、**中身は作り直した**。
///
/// ## 現行との違い(意図して変えた)
/// 現行は「ポップアップでプレイをブロックしない・いつでもスキップできる」作りで、
/// その根拠として原則1(受動的である)がコードに書いてある。
/// **今回はそこを変える** — CEO 2026-08-16「ポップアップの通り踏まないと
/// ほか押せない、次進めないみたいな。チュートリアルモードが必要」。
///
/// 原則1との折り合い:
///  - **急かさない**は守る。タイマーも催促も無く、各段は1操作。
///    そもそも最後の段が「アプリを閉じて、あとで戻ってきて」なので、
///    向きは原則1と同じ。
///  - **罰しない**も守る。途中でやめても失うものは無い。
///
/// 引き継いだ仕組み:
///  - `resolve_step` — **実際にやったら繰り上がる**(「次へ」で進めない)
///  - `advance_step` / `is_done`
///
/// 作り直したもの: 段の数(3 → 4)と文言。「虫が湧いた」を足した
/// — 自分が作ったものを一度見せないと、植物→虫→鳥 の輪が伝わらない。
library;

/// 段の数。0=土地 / 1=植える / 2=虫が湧いた / 3=閉じて待つ。
const int kTutorialSteps = 4;

/// 実際の進み具合を見て、必要なら段を繰り上げる。
///
/// **「次へ」ボタンでは進まない段がある** — 植える段は、実際に1つ植えた
/// 時点で自動的に次へ行く(`tutorial.resolve_step` と同じ考え方)。
int resolveTutorialStep(int step, {required bool hasPlanted}) {
  if (step == 1 && hasPlanted) return 2;
  return step;
}

/// 1つ進める。`kTutorialSteps` を超えたら丸める(= 終わり)。
int advanceTutorialStep(int step) =>
    step + 1 > kTutorialSteps ? kTutorialSteps : step + 1;

/// もう案内を終えたか。
bool tutorialIsDone(int step) => step >= kTutorialSteps;

/// 1段ぶんの案内。
class TutorialStep {
  final String title;
  final String body;

  /// ボタンの文字。**null なら、実際に操作するまで進めない**
  /// (土地を選ぶ / 植える)。
  final String? nextLabel;
  const TutorialStep(this.title, this.body, {this.nextLabel});
}

/// その段の案内文。**短く。** 画面が狭いので、1段=2行までに収める。
///
/// [hasInsects] は「虫が湧いた」段の言い方を変えるのに使う。
/// 気温が合わなければ虫は湧かない — そのときも**嘘をつかない**
/// (原則4「生態に誠実」)。
TutorialStep tutorialStepContent(int step, {bool hasInsects = true}) {
  switch (step.clamp(0, kTutorialSteps - 1)) {
    case 0:
      return const TutorialStep(
        'Choose your land',
        'Charlotte or Kyoto. You can change it any time.',
      );
    case 1:
      return const TutorialStep(
        'Plant something',
        'Plants bring insects. Insects bring birds.',
      );
    case 2:
      return hasInsects
          ? const TutorialStep(
              'Insects came',
              'Birds come for these.',
              nextLabel: 'I see',
            )
          : const TutorialStep(
              'No insects yet',
              'They need the right temperature too. Another plant may help.',
              nextLabel: 'I see',
            );
    default:
      return const TutorialStep(
        'Now close the app',
        'Time passes on its own. Come back later and birds will have visited.',
        nextLabel: 'Start',
      );
  }
}
