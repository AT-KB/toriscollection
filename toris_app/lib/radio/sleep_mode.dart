/// 睡眠モード — 環境音を流しながら画面を暗くし、決めた時間で静かに止める。
///
/// **これは Streamlit では作れなかった機能**である。ブラウザの中では、画面が
/// 消えた時点で音が止まり、時間で止めることもできなかった。移行の理由そのもの。
///
/// 作りの要点:
///  - **画面を起こし続けない。** 端末のスリープ時間どおりに消えてよい。
///    音が止まらないようにするのは画面ではなく、フォアグラウンドサービスの役目。
///  - **終わりは切らずに沈める。** 最後の1分をかけて音量を落とす。眠りかけの
///    ところで音が急に消えると、かえって目が覚める。
///  - 交渉不能の原則1「受動的である」に沿い、**急かさない**。残り時間の
///    カウントダウンを大きく出したりはしない。
library;

import 'package:flutter/services.dart';

class RadioNative {
  static const _ch = MethodChannel('toris/radio');

  /// 鳴っている間だけフォアグラウンドサービスを立てる。
  /// これが無いと、画面が消えて背面に回った時点で OS に音を絞られる。
  static Future<void> startForeground() =>
      _ch.invokeMethod<void>('startForeground');

  static Future<void> stopForeground() =>
      _ch.invokeMethod<void>('stopForeground');

  /// 通知の「Stop」が押されたか。
  static Future<bool> stopRequested() async =>
      await _ch.invokeMethod<bool>('stopRequested') ?? false;

  static Future<void> clearStopRequest() =>
      _ch.invokeMethod<void>('clearStopRequest');

  /// 画面の明るさ。-1 で端末の設定に戻す。
  static Future<void> setBrightness(double v) =>
      _ch.invokeMethod<void>('setBrightness', {'value': v});
}

/// 選べる長さ。数字は「眠りにつくまで」の見当。
/// 90分は睡眠1周期ぶんで、寝入りに使う人向け。
const List<int> kSleepMinutes = [15, 30, 60, 90];

/// 終わりに音を沈めていく時間。切らずに沈める。
const Duration kFadeOut = Duration(minutes: 1);
