/// 図鑑の「好きなもの / 好きな場所 / こわいもの」。
/// `bird_profile.py` と `predators.py` の移植。
///
/// 交渉不能の原則4「生態に誠実」:
///   好きなもの = 実際に食べるもの(eats_plants / eats_insects)
///   好きな場所 = 実際の biome_pref
///   こわいもの = **GloBI の実際の捕食記録**
/// 作り話の「かわいい豆知識」は入れない。
///
/// ## ⚠️ 分類の表を自分で作らないこと(2026-08-16 の監査で見つけた)
/// 私は Dart 側に7つの分類(raptor / owl / snake / **mammal** / cat /
/// **corvid** / **other**)を手で書いていた。実際の `predators.py` は**12分類**で、
/// mammal・corvid・other は**存在しない**。データが使っている
/// crow / falcon / fox / rodent / weasel が表に無く、図鑑には生のキーが
/// そのまま出ていた。表は Python から引き写すこと。
library;

/// 分類キー → 表示名。`predators.CATEGORY_LABELS` の**出荷済みの英語**
/// (`i18n.py` の TRANSLATIONS を引き写した)。
///
/// **順序も Python と同じ**にしてある(表示順ではなく、表の同一性の確認用)。
const Map<String, String> kPredatorLabels = {
  'raptor': 'Hawks',
  'owl': 'Owls',
  'falcon': 'Falcons',
  'snake': 'Snakes',
  'crow': 'Crows and jays',
  'shrike': 'Shrikes',
  'cat': 'Cats',
  'raccoon': 'Raccoons',
  'weasel': 'Weasels',
  'fox': 'Foxes',
  'squirrel': 'Squirrels',
  'rodent': 'Mice and rats',
};

/// その鳥の天敵カテゴリのキー。無ければ空。
///
/// **表に無いキーは静かに落とす**(`predators.categories` と同じ)。
/// データが増えても、知らない分類を画面に出さないための安全弁。
List<String> predatorCategories(
    String birdId, Map<String, dynamic> predatorsData) {
  final rec = predatorsData[birdId] as Map?;
  if (rec == null) return const [];
  return [
    for (final c in ((rec['categories'] as List?) ?? const []))
      if (kPredatorLabels.containsKey('$c')) '$c'
  ];
}

/// 天敵が「同属の近縁種の記録」由来か。
bool predatorIsGenusLevel(String birdId, Map<String, dynamic> predatorsData) {
  final rec = predatorsData[birdId] as Map?;
  return rec != null && rec['level'] == 'genus';
}

/// その鳥の天敵カテゴリを、表示名にして返す。
List<String> predatorLabels(
        String birdId, Map<String, dynamic> predatorsData) =>
    [
      for (final k in predatorCategories(birdId, predatorsData))
        kPredatorLabels[k]!
    ];

/// 天敵のデータがあるか。
bool predatorHasData(String birdId, Map<String, dynamic> predatorsData) =>
    predatorCategories(birdId, predatorsData).isNotEmpty;

/// 「好きなもの」の1件。
class ProfileLike {
  /// 'plant' か 'insect'。
  final String kind;
  final String id;
  const ProfileLike(this.kind, this.id);
}

/// 「好きなもの」= 実際に食べる植物・昆虫。
///
/// **図鑑に載っていない ID は静かに除外する**(データ更新への安全弁)。
/// 並びは Python と同じ「植物 → 昆虫」で、それぞれ元の並び順のまま。
List<ProfileLike> profileLikes(Map<String, dynamic> bird,
    Map<String, dynamic> plants, Map<String, dynamic> insects) {
  final out = <ProfileLike>[];
  for (final p in ((bird['eats_plants'] as List?) ?? const [])) {
    if (plants['$p'] != null) out.add(ProfileLike('plant', '$p'));
  }
  for (final i in ((bird['eats_insects'] as List?) ?? const [])) {
    if (insects['$i'] != null) out.add(ProfileLike('insect', '$i'));
  }
  return out;
}

/// 「好きな場所」= 実際に好む土地。載っていない ID は除外する。
List<String> profileHome(
    Map<String, dynamic> bird, Map<String, dynamic> biomes) {
  final out = <String>[];
  for (final b in ((bird['biome_pref'] as List?) ?? const [])) {
    if (biomes['$b'] != null) out.add('$b');
  }
  return out;
}

/// 「こわいもの」。
class ProfileFears {
  final List<String> categories;
  final bool genusLevel;
  const ProfileFears(this.categories, this.genusLevel);
}

/// 図鑑プロフィールの全項目。`bird_profile.build` と同じ。
///
/// 各項目は空になりうる。**空の行は表示側で出さない**(静かなトーン)。
class BirdProfile {
  final List<ProfileLike> likes;
  final List<String> home;
  final ProfileFears fears;
  const BirdProfile(this.likes, this.home, this.fears);
}

BirdProfile buildBirdProfile({
  required String birdId,
  required Map<String, dynamic> bird,
  required Map<String, dynamic> plants,
  required Map<String, dynamic> insects,
  required Map<String, dynamic> biomes,
  required Map<String, dynamic> predatorsData,
}) =>
    BirdProfile(
      profileLikes(bird, plants, insects),
      profileHome(bird, biomes),
      ProfileFears(predatorCategories(birdId, predatorsData),
          predatorIsGenusLevel(birdId, predatorsData)),
    );

/// 「こわいもの」だけを取り出す。`bird_profile.fears` と同じ。
ProfileFears profileFears(String birdId, Map<String, dynamic> predatorsData) =>
    ProfileFears(predatorCategories(birdId, predatorsData),
        predatorIsGenusLevel(birdId, predatorsData));
