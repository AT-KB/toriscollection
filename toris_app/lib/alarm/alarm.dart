/// 目覚ましの設定をネイティブに渡す窓口。
///
/// 実際に鳴らすのは Android 側(`BirdAlarmService`)で、ここは時刻と鳥を渡すだけ。
/// **アプリを閉じていても、通信ができなくても鳴る必要がある**ため、音は APK に
/// 同梱したものだけを使い、サーバーには一切依存しない
/// (現行版は Render のコールドスタートが実測22.7秒。朝いちばんを預けられない)。
library;

import 'package:flutter/services.dart';

/// 目覚ましに選べる鳥。**並びはネイティブ側 `BirdAlarmSounds.KEYS` と同じ。**
///
/// ## 2026-08-19 の作り直し(CEO)
/// 「選択はできるようにして、最初の1羽とあとはランダムで3羽まで加わる作りに。
///  ただしその加わる残り2羽は、出会った鳥であってほしい」
///
/// - **1羽目**: ここから選ぶ(23種)。
/// - **2羽目・3羽目**: その朝ごとに、**近くで出会った鳥**から選ばれる。
///   出会いが足りなければ既定の並びから埋める(目覚ましは起きるための道具で、
///   始めたばかりの人の朝が薄い音になるのは避ける)。
///
/// 23種になったのは、ネイティブが `res/raw` ではなく **Flutter の assets を
/// 直に読む**ようにしたから。音を複製しないので APK も太らない。
///
/// **さえずり(song)のみ**。地鳴き・警戒声(call)は入れない。McFarlane ら
/// (2020)は、耳障りな音で起きると睡眠慣性が強まり、**メロディのある音だけ**が
/// 注意の脱落を有意に減らしたと報告している。アオカケスの "ジェー!" のような
/// 叫びは、研究が名指しで避けるべきとしたものそのもの。
///
/// ⚠️ ドット絵がある種だけ。Song Sparrow は絵が無いので**入っていない**。
const List<({String key, String name})> alarmBirds = [
  (key: 'northern_cardinal', name: 'Northern Cardinal'),
  (key: 'american_robin', name: 'American Robin'),
  (key: 'american_goldfinch', name: 'American Goldfinch'),
  (key: 'blue_jay', name: 'Blue Jay'),
  (key: 'carolina_wren', name: 'Carolina Wren'),
  (key: 'downy_woodpecker', name: 'Downy Woodpecker'),
  (key: 'eastern_bluebird', name: 'Eastern Bluebird'),
  (key: 'enaga', name: 'Long-tailed Tit'),
  (key: 'hiyodori', name: 'Brown-eared Bulbul'),
  (key: 'kakesu', name: 'Eurasian Jay'),
  (key: 'kawarahiwa', name: 'Oriental Greenfinch'),
  (key: 'kawasemi', name: 'Common Kingfisher'),
  (key: 'kibitaki', name: 'Narcissus Flycatcher'),
  (key: 'kogera', name: 'Japanese Pygmy Woodpecker'),
  (key: 'mejiro', name: 'Japanese White-eye'),
  (key: 'mourning_dove', name: 'Mourning Dove'),
  (key: 'pileated_woodpecker', name: 'Pileated Woodpecker'),
  (key: 'shijukara', name: 'Japanese Tit'),
  (key: 'suzume', name: 'Eurasian Tree Sparrow'),
  (key: 'tsubame', name: 'Barn Swallow'),
  (key: 'tufted_titmouse', name: 'Tufted Titmouse'),
  (key: 'uguisu', name: 'Japanese Bush Warbler'),
  (key: 'yamagara', name: 'Varied Tit'),
];

/// 画面の名前は `alarmBirds` を使う。並びの一致は試験で見ている。
const List<({String key, String name})> dawnChorus = alarmBirds;


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
