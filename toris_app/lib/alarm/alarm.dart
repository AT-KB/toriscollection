/// 目覚ましの設定をネイティブに渡す窓口。
///
/// 実際に鳴らすのは Android 側(`BirdAlarmService`)で、ここは時刻と鳥を渡すだけ。
/// **アプリを閉じていても、通信ができなくても鳴る必要がある**ため、音は APK に
/// 同梱したものだけを使い、サーバーには一切依存しない
/// (現行版は Render のコールドスタートが実測22.7秒。朝いちばんを預けられない)。
library;

import 'package:flutter/services.dart';

/// 目覚ましに鳴らせる鳥。**アルファベット順**(CEO 2026-08-19)。
///
/// ⚠️ これは「鳴らせる全部」であって、**選べるものではない**。
/// 選べるのは [selectableAlarmBirds] — 会えた鳥＋最初から居る3種だけ。
///
/// ## ここに入る条件
/// (1) **さえずり(song)であること。** 地鳴き・警戒声(call)は入れない。
///     McFarlane ら(2020)— 耳障りな音で起きると睡眠慣性が強まり、
///     メロディのある音だけが注意の脱落を有意に減らした。
/// (2) **ドット絵があること。** 顔が並ばないと選べない。
///     Song Sparrow は絵が無いので入っていない。
///
/// ⚠️ 土地では絞らない(CEO 2026-08-19「目覚ましは土地で絞らなくていい」)。
/// 加わる2羽は会えた鳥＝その土地の鳥なので、1羽目を自由に選んでも
/// 生態の嘘にはならない。
///
/// ⚠️ 並びは**表示のため**のもの。ネイティブ側 `BirdAlarmSounds.KEYS` は
/// **足りないときの埋め順**なので、順序は別。中身が同じことは試験で見ている。
const List<({String key, String name})> alarmBirds = [
  (key: 'american_goldfinch', name: 'American Goldfinch'),
  (key: 'american_robin', name: 'American Robin'),
  (key: 'tsubame', name: 'Barn Swallow'),
  (key: 'blue_jay', name: 'Blue Jay'),
  (key: 'hiyodori', name: 'Brown-eared Bulbul'),
  (key: 'carolina_wren', name: 'Carolina Wren'),
  (key: 'kawasemi', name: 'Common Kingfisher'),
  (key: 'downy_woodpecker', name: 'Downy Woodpecker'),
  (key: 'eastern_bluebird', name: 'Eastern Bluebird'),
  (key: 'kakesu', name: 'Eurasian Jay'),
  (key: 'suzume', name: 'Eurasian Tree Sparrow'),
  (key: 'uguisu', name: 'Japanese Bush Warbler'),
  (key: 'kogera', name: 'Japanese Pygmy Woodpecker'),
  (key: 'shijukara', name: 'Japanese Tit'),
  (key: 'mejiro', name: 'Japanese White-eye'),
  (key: 'enaga', name: 'Long-tailed Tit'),
  (key: 'mourning_dove', name: 'Mourning Dove'),
  (key: 'kibitaki', name: 'Narcissus Flycatcher'),
  (key: 'northern_cardinal', name: 'Northern Cardinal'),
  (key: 'kawarahiwa', name: 'Oriental Greenfinch'),
  (key: 'pileated_woodpecker', name: 'Pileated Woodpecker'),
  (key: 'tufted_titmouse', name: 'Tufted Titmouse'),
  (key: 'yamagara', name: 'Varied Tit'),
];

/// 何も会っていなくても最初から選べる3種。
///
/// CEO 2026-08-19「Bluejay、Northern Cardinal, Goldfinch だけ初期設定でいる感じ」。
/// 目覚ましは**起きるための道具**なので、始めた初日から使えないと困る。
const Set<String> kStarterAlarmBirds = {
  'blue_jay',
  'northern_cardinal',
  'american_goldfinch',
};

/// いま選べる鳥。**会えた鳥＋最初から居る3種**(CEO 2026-08-19)。
///
/// [met] は近くで出会った鳥(儀式が成立した種)。順はアルファベットのまま。
List<({String key, String name})> selectableAlarmBirds(Iterable<String> met) {
  final allow = {...kStarterAlarmBirds, ...met};
  return [for (final b in alarmBirds) if (allow.contains(b.key)) b];
}

/// 画面の名前は `alarmBirds` を使う。並びの一致は試験で見ている。
const List<({String key, String name})> dawnChorus = alarmBirds;

/// 鍵から表示名を引く。知らない鍵はそのまま返す。
String alarmBirdName(String key) {
  for (final b in alarmBirds) {
    if (b.key == key) return b.name;
  }
  return key;
}


class AlarmSetting {
  final bool enabled;
  final int hour;
  final int minute;

  /// 選ばれている1羽目。未設定なら null。
  final String? first;

  const AlarmSetting({
    required this.enabled,
    required this.hour,
    required this.minute,
    this.first,
  });

  String get hhmm =>
      '${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}';
}

class Alarm {
  static const _ch = MethodChannel('toris/alarm');

  /// 設定する。**false が返ったら**「正確なアラーム」が未許可なので、
  /// [openExactAlarmSettings] で設定画面へ案内する。
  /// [first] は1羽目。[met] は**近くで出会った鳥**の並び(2羽目・3羽目の元)。
  static Future<bool> set(int hour, int minute,
      {required String first, required List<String> met}) async {
    final ok = await _ch.invokeMethod<bool>('set', {
      'hour': hour,
      'minute': minute,
      'first': first,
      'met': met.join(','),
    });
    return ok ?? false;
  }

  static Future<void> cancel() => _ch.invokeMethod<void>('cancel');

  static Future<AlarmSetting> get() async {
    final m = await _ch.invokeMapMethod<String, dynamic>('get');
    return AlarmSetting(
      enabled: (m?['enabled'] as bool?) ?? false,
      hour: (m?['hour'] as int?) ?? 7,
      minute: (m?['minute'] as int?) ?? 0,
      first: m?['first'] as String?,
    );
  }

  /// Android 12+ の「正確なアラーム」が許可されているか。
  static Future<bool> canScheduleExact() async =>
      await _ch.invokeMethod<bool>('canScheduleExact') ?? true;

  static Future<void> openExactAlarmSettings() =>
      _ch.invokeMethod<void>('openExactAlarmSettings');

  /// 通知の許可があるか(Android 13+)。
  ///
  /// 無いと、鳴っている最中の通知が出ず、**止める手立てが画面に出ない**。
  /// 音は鳴るので、ユーザーから見れば「止められない目覚まし」になる。
  static Future<bool> hasNotificationPermission() async =>
      await _ch.invokeMethod<bool>('hasNotificationPermission') ?? true;

  static Future<void> requestNotificationPermission() =>
      _ch.invokeMethod<void>('requestNotificationPermission');

  /// いま鳴っているか。鳴っていれば画面に「止める」を出す。
  static Future<bool> isRinging() async =>
      await _ch.invokeMethod<bool>('isRinging') ?? false;

  static Future<void> stopRinging() => _ch.invokeMethod<void>('stopRinging');

  /// **いま鳴いている鳥**(鳴き始めた順)。鳴っていなければ空。
  ///
  /// 順番も時刻も Dart 側では組み立てない。ネイティブが実際に音を足した
  /// ところだけを返すので、画面に出る名前は必ず鳴っている鳥になる。
  static Future<List<String>> ringingBirds() async {
    final v = await _ch.invokeMethod<List<Object?>>('ringingBirds');
    return [for (final e in v ?? const []) '$e'];
  }
}
