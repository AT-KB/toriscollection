/// 目覚ましの設定をネイティブに渡す窓口。
///
/// 実際に鳴らすのは Android 側(`BirdAlarmService`)で、ここは時刻と鳥を渡すだけ。
/// **アプリを閉じていても、通信ができなくても鳴る必要がある**ため、音は APK に
/// 同梱したものだけを使い、サーバーには一切依存しない
/// (現行版は Render のコールドスタートが実測22.7秒。朝いちばんを預けられない)。
library;

import 'package:flutter/services.dart';

/// 目覚ましに使える鳥。**さえずり(song)のみ**。
///
/// 地鳴き・警戒声(call)は入れない。McFarlane ら(2020)は、耳障りな音で起きると
/// 睡眠慣性(朝のぼんやり)が強まり、**メロディのある音だけ**が注意の脱落を有意に
/// 減らしたと報告している。アオカケスの "ジェー!" のような叫びは、研究が名指しで
/// 避けるべきとしたものそのもの。
///
/// 並び順はネイティブ側 `BirdAlarmSounds.KEYS` と**同じにしておくこと**。
/// その順序がそのまま「夜明けのコーラスで加わる順」になる。
const List<({String key, String name})> alarmBirds = [
  (key: 'northern_cardinal', name: 'Northern Cardinal'),
  (key: 'american_robin', name: 'American Robin'),
  (key: 'song_sparrow', name: 'Song Sparrow'),
  (key: 'carolina_wren', name: 'Carolina Wren'),
  (key: 'eastern_bluebird', name: 'Eastern Bluebird'),
];

class AlarmSetting {
  final bool enabled;
  final int hour;
  final int minute;
  final String sound;

  const AlarmSetting({
    required this.enabled,
    required this.hour,
    required this.minute,
    required this.sound,
  });

  String get hhmm =>
      '${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}';
}

class Alarm {
  static const _ch = MethodChannel('toris/alarm');

  /// 設定する。**false が返ったら**「正確なアラーム」が未許可なので、
  /// [openExactAlarmSettings] で設定画面へ案内する。
  static Future<bool> set(int hour, int minute, String sound) async {
    final ok = await _ch.invokeMethod<bool>('set', {
      'hour': hour,
      'minute': minute,
      'sound': sound,
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
      sound: (m?['sound'] as String?) ?? 'northern_cardinal',
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
