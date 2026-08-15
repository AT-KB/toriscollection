/// 「今日の庭アイテム」。`garden_items.py` の移植(確率に効く部分)。
///
/// 広告を1回見ると、1日1回だけ置ける、**6時間だけ効くおまけ**。
/// 効果は「到来確率を少し上げる」か「退去率を少し下げる」の**加点方向だけ**。
/// ペナルティは無い(交渉不能の原則2「罰しない」)。見なくても鳥の声・ラジオ・
/// 図鑑は何も変わらない(原則3)。
///
/// ## ⚠️ 広告はまだ入っていない
/// 置く導線(広告)が無いので、いまはどのアイテムも配置されない。それでも
/// **確率に効くロジックなので移した**(CEO 2026-08-16「呼ぶ確率とかのロジックは
/// 基本すべて移すこと、推測ではなく忠実に」)。広告を入れる段で画面を足せば、
/// 計算はここに揃っている。
///
/// 対象種の絞り込みは**既存のデータ項目だけ**を根拠にする
/// (eats_plants / eats_insects / english / wariness / biome_pref)。
/// 新しい恣意的な指標は作らない(原則4)。
library;

/// 1回の配置が効く時間。
const int kItemDurationHours = 6;

const String kEffectArrivalBonus = 'arrival_bonus';
const String kEffectDepartureReduction = 'departure_reduction';

class GardenItem {
  final String emoji;
  final String effectKind;

  /// 到来確率に足す値(pp)、または退去率から引く値。
  final double value;

  /// 1種だけを狙うアイテムはここに種ID。無ければ null。
  final String? singleTarget;
  const GardenItem(this.emoji, this.effectKind, this.value,
      {this.singleTarget});

  /// Python は `if "single_target" in item` で見る(値ではなく**キーの有無**)。
  bool get hasSingleTarget => singleTarget != null;
}

/// 6種。値は `garden_items.py` の ITEMS と同じ。
const Map<String, GardenItem> kGardenItems = {
  'feeder': GardenItem('🌻', kEffectArrivalBonus, 0.010),
  'hummingbird_feeder': GardenItem('🌺', kEffectArrivalBonus, 0.060,
      singleTarget: 'ruby_throated_hummingbird'),
  'suet_feeder': GardenItem('🧈', kEffectArrivalBonus, 0.025),
  'bird_bath': GardenItem('💧', kEffectDepartureReduction, 0.050),
  'nyjer_feeder': GardenItem('🌾', kEffectArrivalBonus, 0.050),
  'squirrel_baffle': GardenItem('🛡', kEffectArrivalBonus, 0.030),
};

/// ニジャーシードを好むのは goldfinch 系統だけ。
/// データに属(genus)が無いため、対象を明示する(提案書§3 の裁量判断)。
const Set<String> kNyjerTargets = {'kawarahiwa', 'american_goldfinch'};

/// 水系専門種の除外。カワセミは魚食で庭の給餌器と無関係なので、
/// 警戒心の閾値だけで機械的に対象にすると不誠実な理由付けになる。
const Set<String> kWaterSpecialistExclude = {'kawasemi'};

/// このアイテムが、この土地で効果を持つ鳥ID。
Set<String> targetBirdIds(
    String itemId, String biomeId, Map<String, dynamic> birdsData) {
  final item = kGardenItems[itemId];
  if (item == null) return {};

  List<String> prefs(Object? b) =>
      (((b as Map?)?['biome_pref'] as List?) ?? const [])
          .map((e) => '$e')
          .toList();

  if (item.hasSingleTarget) {
    final bid = item.singleTarget!;
    final bird = birdsData[bid];
    if (bird != null && prefs(bird).contains(biomeId)) return {bid};
    return {};
  }

  // バードバスは全種共通。個別の対象リストは持たない。
  if (itemId == 'bird_bath') return {};

  final out = <String>{};
  birdsData.forEach((bid, b) {
    if (!prefs(b).contains(biomeId)) return;
    final m = (b as Map?) ?? const {};
    switch (itemId) {
      case 'feeder':
        if ((m['eats_plants'] as List?)?.isNotEmpty ?? false) out.add(bid);
        break;
      case 'suet_feeder':
        if ('${m['english'] ?? ''}'.toLowerCase().contains('woodpecker')) {
          out.add(bid);
        }
        break;
      case 'nyjer_feeder':
        if (kNyjerTargets.contains(bid)) out.add(bid);
        break;
      case 'squirrel_baffle':
        final w = (m['wariness'] as num?)?.toDouble() ?? 0.0;
        if (w >= 0.55 && !kWaterSpecialistExclude.contains(bid)) out.add(bid);
        break;
    }
  });
  return out;
}

/// この土地でこのアイテムに意味があるか(選べるか)。
bool itemIsAvailable(
    String itemId, String biomeId, Map<String, dynamic> birdsData) {
  if (!kGardenItems.containsKey(itemId)) return false;
  if (itemId == 'bird_bath') {
    return birdsData.values.any((b) =>
        (((b as Map?)?['biome_pref'] as List?) ?? const [])
            .map((e) => '$e')
            .contains(biomeId));
  }
  return targetBirdIds(itemId, biomeId, birdsData).isNotEmpty;
}

/// 置いたアイテム。
class ItemPlacement {
  final String itemId;
  final DateTime placedAt;
  final DateTime expiresAt;
  const ItemPlacement(this.itemId, this.placedAt, this.expiresAt);
}

/// 置く。`place_item` と同じ(6時間後に切れる)。
ItemPlacement placeItem(String itemId, {DateTime? now}) {
  final t = now ?? DateTime.now();
  return ItemPlacement(
      itemId, t, t.add(const Duration(hours: kItemDurationHours)));
}

/// その時刻でまだ効いているか。**両端を含む**(Python の `placed <= at <= expires`)。
bool itemIsActive(ItemPlacement? p, {DateTime? at}) {
  if (p == null) return false;
  final t = at ?? DateTime.now();
  return !p.placedAt.isAfter(t) && !t.isAfter(p.expiresAt);
}

/// 残り時間(時間)。効いていなければ 0。
double itemHoursRemaining(ItemPlacement? p, {DateTime? at}) {
  if (!itemIsActive(p, at: at)) return 0.0;
  final t = at ?? DateTime.now();
  final s = p!.expiresAt.difference(t).inMicroseconds / 1e6;
  return s < 0 ? 0.0 : s / 3600;
}

/// `runTurn` に渡す「鳥ID → 到来確率に足す値」。
/// 未配置・期限切れ・到来確率アップ系でなければ、常に 0 を返す
/// (＝ 今までの挙動から一切変わらない)。
double Function(String) makeArrivalBonusFn(
    ItemPlacement? p, String biomeId, Map<String, dynamic> birdsData,
    {DateTime? at}) {
  if (!itemIsActive(p, at: at)) return (_) => 0.0;
  final item = kGardenItems[p!.itemId];
  if (item == null || item.effectKind != kEffectArrivalBonus) return (_) => 0.0;
  final targets = targetBirdIds(p.itemId, biomeId, birdsData);
  return (bid) => targets.contains(bid) ? item.value : 0.0;
}

/// `runTurn` に渡す退去率の減算値。効いていなければ 0。
double itemDepartureBonus(ItemPlacement? p, {DateTime? at}) {
  if (!itemIsActive(p, at: at)) return 0.0;
  final item = kGardenItems[p!.itemId];
  if (item == null || item.effectKind != kEffectDepartureReduction) return 0.0;
  return item.value;
}

/// その鳥が、いま効いているアイテムの対象か。
///
/// **「なぜ来たか」の理由文のためだけ**に使う。生態ログの中身を書き換えるのでは
/// なく、食物網由来の理由が無いときに「アイテムに誘われた」と正直に言うための判定
/// (原則4「捏造しない」)。
bool isItemBoostedArrival(String birdId, ItemPlacement? p, String biomeId,
    Map<String, dynamic> birdsData,
    {DateTime? at}) {
  if (!itemIsActive(p, at: at)) return false;
  final item = kGardenItems[p!.itemId];
  if (item == null || item.effectKind != kEffectArrivalBonus) return false;
  return targetBirdIds(p.itemId, biomeId, birdsData).contains(birdId);
}
