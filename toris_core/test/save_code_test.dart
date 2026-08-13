/// セーブコードの互換テスト。
///
/// ここは「Dart 単体で筋が通っている」ことでは足りない。**Python 版が書いた実物を
/// 読めること**、そして**Dart が書いたものを Python 版が読めること**の両方を見る。
/// 前者はこのファイルで、後者は書き出した from_dart.json を
/// `py -3 tools/save_code_fixtures.py --verify` が確かめる。
///
/// 実行:
///   py -3 tools/save_code_fixtures.py         # Python が書いたコードを用意
///   dart test                                  # ここ
///   py -3 tools/save_code_fixtures.py --verify # Dart が書いたコードを読み返す
library;

import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

/// 比較しやすいよう、Set を並べ替えた配列に戻す(Python 側の書き方に合わせる)。
Object? normalize(Object? v) {
  if (v is Set) {
    final l = v.toList()
      ..sort((a, b) => Comparable.compare(a as Comparable, b as Comparable));
    return l;
  }
  if (v is Map) {
    return v.map((k, val) => MapEntry(k, normalize(val)));
  }
  if (v is List) return v.map(normalize).toList();
  return v;
}

void main() {
  final fixturesDir = Directory('test/fixtures');
  final fromPython = File('${fixturesDir.path}/from_python.json');

  group('Python 版との互換', () {
    late Map<String, dynamic> fixtures;

    setUpAll(() {
      if (!fromPython.existsSync()) {
        fail('先に `py -3 tools/save_code_fixtures.py` を実行して、'
            'Python 版が書いたセーブコードを用意すること。');
      }
      fixtures = jsonDecode(fromPython.readAsStringSync()) as Map<String, dynamic>;
    });

    test('Python が書いたコードを Dart が読める', () {
      final produced = <Map<String, dynamic>>[];
      for (final c in fixtures['cases'] as List) {
        final name = c['name'] as String;
        final expected = c['state'] as Map<String, dynamic>;
        final decoded = decodeSave(c['code'] as String);

        expect(decoded, isNotNull, reason: '$name: 読めなかった');
        final got = decoded!.map((k, v) => MapEntry(k, normalize(v)));
        expect(got, equals(expected), reason: '$name: 中身が違う');

        // 読めた状態をそのまま書き戻し、Python 側に読ませる材料にする
        produced.add({'name': name, 'state': expected, 'code': encodeSave(decoded)});
      }
      fixturesDir.createSync(recursive: true);
      File('${fixturesDir.path}/from_dart.json')
          .writeAsStringSync(const JsonEncoder.withIndent(' ').convert(produced));
    });

    test('読めないコードは例外を投げずに null を返す', () {
      for (final e in fixtures['edge'] as List) {
        final name = e['name'] as String;
        final expect0 = e['expect'];
        final got = decodeSave(e['code'] as String);
        if (expect0 == null) {
          expect(got, isNull, reason: '$name: null であるべき');
        } else {
          expect(got, isNotNull, reason: '$name: 読めるべき');
          final norm = got!.map((k, v) => MapEntry(k, normalize(v)));
          expect(norm, equals(expect0), reason: '$name: 中身が違う');
        }
      }
    });
  });

  group('Dart 単体', () {
    test('書いて読むと元に戻る', () {
      final state = {
        'biome': 'kyoto',
        'discovered': {'b', 'a', 'c'},
        'bird_days': {'a': 2},
        'bird_notes': {'a': '枝の上に🐦'},
      };
      final back = decodeSave(encodeSave(state))!;
      expect(back['biome'], 'kyoto');
      expect(back['discovered'], isA<Set>());
      expect((back['discovered'] as Set).toList()..sort(), ['a', 'b', 'c']);
      expect(back['bird_notes'], {'a': '枝の上に🐦'});
    });

    test('知らないキーは落とす', () {
      final code = encodeSave({'biome': 'kyoto'});
      final decoded = decodeSave(code)!;
      expect(decoded.containsKey('biome'), isTrue);
      // 保存対象外のキーは、そもそも書き出されない
      expect(encodeSave({'secret': 'x'}), equals(encodeSave({})));
    });

    test('saved_at は Python の isoformat(timespec=seconds) と同じ形', () {
      final s = buildCurrentSnapshot({'biome': 'kyoto'},
          now: DateTime(2026, 8, 13, 9, 5, 3));
      expect(s['saved_at'], '2026-08-13T09:05:03');
    });

    test('空でも壊れない', () {
      expect(decodeSave(encodeSave({})), equals(<String, dynamic>{}));
      expect(decodeSave(null), isNull);
      expect(decodeSave('   '), isNull);
    });
  });
}
