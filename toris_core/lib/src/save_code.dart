/// セーブコード(ローカル保存)の読み書き。`toris_collection/save_code.py` の移植。
///
/// **ここは互換を絶対に壊せない。** 既存ユーザーの進行データは、この文字列としてのみ
/// 手元に残っている(サーバーには一切送っていない)。Flutter 版が Python 版の書いた
/// コードを読めなければ、進行が消えたのと同じことになる。
/// 提案書 §3「セーブコードの互換だけは必ず守る」がこれ。
///
/// 形式は Python 版と同じ:
///   JSON(コンパクト・非ASCIIはそのまま) -> zlib(level 9) -> base64(urlsafe, パディング有)
/// 旧形式(zlib 圧縮前に書き出されたコード)も読める。
library;

import 'dart:convert';
import 'dart:io';

/// セーブコードのフォーマットバージョン。Python 版の SAVE_FORMAT_VERSION と揃える。
const int saveFormatVersion = 1;

/// Python 側で set 型として持たれているキー。JSON では並び順の決まった配列にする。
const List<String> setKeys = ['residents', 'discovered', 'mementos_set'];

/// セーブコードに載せてよいキー。ここに無いものは読み書きとも無視する
/// (将来のフォーマット変更・改ざんへの安全弁)。Python 版の SAVE_KEYS と同じ順序。
const List<String> saveKeys = [
  'biome',
  'planted',
  'planted_at_map',
  // 置いた餌台(feeder_chain)。開放型かかご型かで、リス→タカの連鎖が変わる。
  'feeders',
  'residents',
  'discovered',
  'bird_days',
  'mementos',
  'mementos_set',
  'bird_notes',
  'observed',
  'eco_log',
  'current_tester_id',
  'saved_at',
];

final ZLibCodec _zlib = ZLibCodec(level: 9);

/// 進行データからセーブ対象のキーだけを抜き出す。
/// set 相当(Dart では Set)は、Python 版と同じく**並べ替えた配列**にする。
Map<String, dynamic> _buildPayload(Map<String, dynamic> state) {
  final payload = <String, dynamic>{};
  for (final key in saveKeys) {
    if (!state.containsKey(key)) continue;
    var value = state[key];
    if (setKeys.contains(key) && value is Set) {
      final list = value.toList();
      try {
        list.sort((a, b) => Comparable.compare(a as Comparable, b as Comparable));
      } catch (_) {
        // 並べ替えられない中身なら、そのままの順で出す(Python 版と同じ振る舞い)
      }
      value = list;
    }
    payload[key] = value;
  }
  return payload;
}

/// 復元したデータのうち、set 相当のキーを Set に戻す。
Map<String, dynamic> _restorePayload(Map<String, dynamic> data) {
  final restored = Map<String, dynamic>.from(data);
  for (final key in setKeys) {
    final v = restored[key];
    if (v == null || v is Set) continue;
    restored[key] = v is Iterable ? v.toSet() : <dynamic>{};
  }
  return restored;
}

/// 進行データをセーブコード(1本の文字列)にする。
String encodeSave(Map<String, dynamic> state) {
  final envelope = {'v': saveFormatVersion, 'data': _buildPayload(state)};
  // jsonEncode は Python の separators=(',',':') と同じ詰め方で、
  // 非ASCIIもそのまま出す(ensure_ascii=False 相当)。
  final raw = utf8.encode(jsonEncode(envelope));
  return base64Url.encode(_zlib.encode(raw));
}

/// セーブコードを復元する。
///
/// 壊れたコード・不正な JSON・バージョン違い・想定外の型では、例外を投げず
/// null を返す(Python 版と同じ流儀。読めないものは静かに拒否する)。
Map<String, dynamic>? decodeSave(String? code) {
  if (code == null || code.trim().isEmpty) return null;

  List<int> decoded;
  try {
    decoded = base64Url.decode(code.trim());
  } catch (_) {
    return null;
  }

  // 新形式(zlib)を先に試し、だめなら旧形式(生 JSON)として扱う。
  List<int> raw;
  try {
    raw = _zlib.decode(decoded);
  } catch (_) {
    raw = decoded;
  }

  Object? envelope;
  try {
    envelope = jsonDecode(utf8.decode(raw));
  } catch (_) {
    return null;
  }

  if (envelope is! Map) return null;
  if (envelope['v'] != saveFormatVersion) return null;

  final data = envelope['data'];
  if (data is! Map) return null;

  final cleaned = <String, dynamic>{};
  data.forEach((k, v) {
    if (k is String && saveKeys.contains(k)) cleaned[k] = v;
  });
  return _restorePayload(cleaned);
}

/// 保存した瞬間の時刻(saved_at)を付けたスナップショットを作る。
///
/// 復元時に「離れていた時間」を数えて不在中ループを再現するために要る。
/// Python 版は `datetime.isoformat(timespec='seconds')` を使う。同じ形
/// (`2026-08-13T09:15:30`・タイムゾーンなし・秒まで)になるよう自分で組み立てる。
Map<String, dynamic> buildCurrentSnapshot(Map<String, dynamic> state,
    {DateTime? now}) {
  final snapshot = <String, dynamic>{};
  for (final key in saveKeys) {
    if (state.containsKey(key)) snapshot[key] = state[key];
  }
  snapshot['saved_at'] = isoSeconds(now ?? DateTime.now());
  return snapshot;
}

/// `2026-08-13T09:15:30` の形。Python の isoformat(timespec='seconds') と同じ。
String isoSeconds(DateTime t) {
  String two(int n) => n.toString().padLeft(2, '0');
  return '${t.year.toString().padLeft(4, '0')}-${two(t.month)}-${two(t.day)}'
      'T${two(t.hour)}:${two(t.minute)}:${two(t.second)}';
}

/// `buildCurrentSnapshot` + `encodeSave` をまとめたもの。
String encodeCurrentState(Map<String, dynamic> state, {DateTime? now}) =>
    encodeSave(buildCurrentSnapshot(state, now: now));
