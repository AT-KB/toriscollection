/// ラジオの顔ぶれ。`radio.py` の移植。
///
/// ## ラジオは「蓄積するコレクション」
/// `radio.py` 冒頭の背骨をそのまま持ち込む:
///
/// > 観察した鳥だけが鳴く。会った鳥が増えるほどキャストが豊かになる。
/// > → render_radio は residents ではなく observed/discovered を読む。
/// > **これがコレクション性の構造的な保証。**
///
/// 嵐で庭が痩せて鳥が居なくなっても、ラジオは痩せない。庭は「会いに行く手段」、
/// ラジオは「目的」で、撹乱が触るのは手段の層だけ(交渉不能の原則2「罰しない」)。
library;

/// このバイオームで**実際に会った**鳥だけを返す。`radio.py` の
/// `observed_in_biome` と同じ。
///
/// ⚠️ **ここを外すと、会っていない鳥が最初から鳴く。** 移植で一度落ちていて、
/// 初回起動からラジオが鳴いていた(2026-08-21 CEO が発見)。掲載文の
/// "A radio made only of birds you've met" もこの関数が支えている。
List<String> observedInBiome(
        List<String> biomeBirds, Map<String, int> observed) =>
    [
      for (final id in biomeBirds)
        if ((observed[id] ?? 0) > 0) id
    ];
