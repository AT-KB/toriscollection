/// 画面に出る「一文」を組み立てる層。
///
/// 現行では文の組み立ては**表示側**にある(`radio.py._lineup_story_text` /
/// `disturbance.disturbance_story` / `absence_loop.summarize_events`)。
/// ロジック側(`ecology.py`)は i18n に依存せず、種類だけを返す。
/// その切り分けはそのまま守り、ここに文だけを集める。
///
/// **文言は出荷済みの英語**(`i18n.py` の TRANSLATIONS)を引き写す。
/// 自分で英語を書かない — 一度それで画面が日本語になり、
/// 一度は天敵の分類表を作って間違えた。
library;

import 'ecology.dart';

// ─────────────────────────────────────────────────────────────
// ① 今日の顔ぶれが「なぜ一緒にいるか」(`radio.py._lineup_story_text`)
// ─────────────────────────────────────────────────────────────

/// 顔ぶれが2種未満で、語れることが無いときの一文。
const String kLineupFallback =
    'Birds that favor the same surroundings and forage in similar ways '
    'appear together';

/// `lineupStory` の種類を一文にする。語れることが無ければ空文字。
String lineupStoryText(LineupStory? story) {
  if (story == null) return '';
  switch (story.kind) {
    case 'guild':
      final g = guildLabel(story.guild ?? 'other');
      return 'Today the cast mostly shares a taste for $g — in the same '
          'surroundings they quietly share out the foraging and move together.';
    case 'climate':
      return 'Their ways of foraging differ, but these are birds that favor '
          'a similar climate. They meet in the garden of the same season.';
    case 'mixed':
      return 'A cast gathered by the cues of the same garden.';
  }
  return '';
}

// ─────────────────────────────────────────────────────────────
// ② 撹乱の一文(`disturbance.disturbance_story`)
// ─────────────────────────────────────────────────────────────

/// 撹乱の呼び名。`DISTURBANCES` の label を英語にしたもの。
const Map<String, String> kDisturbanceLabels = {
  'storm': 'Storm',
  'lightning': 'Lightning',
  'logging': 'Felling',
};

/// 撹乱を1文で語る。
///
/// **倒れなかった時も語る** — 「持ちこたえた」と言う。何も出さないと、
/// 嵐が来たこと自体が無かったことになる。
/// 倒れたぶんは純減で、自動では植え直さない(原則2「罰しない」— 減るのは
/// 庭の植生だけで、図鑑も会った日数も減らない)。
String disturbanceStory(String type, String icon, List<String> removedNames) {
  final label = kDisturbanceLabels[type] ?? 'Storm';
  if (removedNames.isNotEmpty) {
    return '$icon $label passed through the garden, '
        'and ${removedNames.join(', ')} was knocked down.';
  }
  return '$icon $label passed through the garden, but the plants held on.';
}

// ─────────────────────────────────────────────────────────────
// ③ 留守のあいだの要約と、相対時刻
//    (`absence_loop.summarize_events` / `humanize_delta`)
// ─────────────────────────────────────────────────────────────

/// 留守のあいだの立ち寄りを1行にまとめる。
///
/// 1種だけなら名前で言い、複数種なら件数と種数で言う。
/// [names] は鳥ID → 表示名。件数は**イベントの数**(同じ鳥が何度来てもよい)。
String summarizeEvents(
    List<String> birdIdsInOrder, String Function(String) nameOf) {
  if (birdIdsInOrder.isEmpty) return '';
  final n = birdIdsInOrder.length;
  final species = birdIdsInOrder.toSet();
  if (species.length == 1) {
    return '${nameOf(species.first)} stopped by $n times';
  }
  return '$n visits (${species.length} species)';
}

/// 「2時間前」のような相対時刻。`humanize_delta` と同じ区切り。
///
/// 未来の時刻(時計がずれている等)でも落ちない — 「まもなく」と言う。
String humanizeDelta(DateTime arrived, DateTime now) {
  final seconds = now.difference(arrived).inSeconds;
  if (seconds < 0) return 'Moments ago';
  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return '${seconds ~/ 60} min ago';
  if (seconds < 86400) return '${seconds ~/ 3600} hr ago';
  return '${seconds ~/ 86400} days ago';
}

/// 留守のあいだの見出し。`🌙 While you were away: {summary}`
String awayHeadline(String summary) => '🌙 While you were away: $summary';

/// 折りたたみの見出し。
const String kSeeWhatHappened = 'See what happened';
