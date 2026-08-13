/// 移植したロジックが Python 版と**同じ答えを返す**かを、総当たりで確かめる。
///
/// 手で書き写したテストには、書き写した人の思い込みも一緒に写る。ここでは
/// Python 版に入力を総当たりで食わせた答えの表(`tools/logic_fixtures.py` が作る)
/// を読み、Dart が再現できるかだけを見る。切り捨て除算・型変換・境界の不等号の
/// ズレは、ここで落ちる。
library;

import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

void main() {
  final f = File('test/fixtures/logic.json');
  late Map<String, dynamic> fx;

  setUpAll(() {
    if (!f.existsSync()) {
      fail('先に `py -3 tools/logic_fixtures.py` を実行して、Python 版の答えを'
          '用意すること。');
    }
    fx = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
  });

  test('群れ: Python 版と同じ答えになる(種の書き方 × 観察回数の総当たり)', () {
    var checked = 0;
    for (final c in fx['flock'] as List) {
      final bird = Map<String, dynamic>.from(c['bird'] as Map);
      final data = <String, dynamic>{'x': bird};

      expect(flockCap('x', data), c['cap'],
          reason: 'cap が違う: bird=$bird');
      expect(flockCap('nope', data), c['cap_missing'],
          reason: 'データに無い ID の cap が違う');

      for (final s in c['sizes'] as List) {
        final expected = s['size'];
        // Python 側が例外になった入力は、Dart でも「例外なく既定に落ちる」ことだけ見る
        if (expected is String && expected.startsWith('ERROR:')) {
          expect(() => flockSize('x', s['count'], data), returnsNormally);
          continue;
        }
        expect(flockSize('x', s['count'], data), expected,
            reason: 'size が違う: bird=$bird count=${s['count']}');
        checked++;
      }
    }
    expect(checked, greaterThan(300), reason: '総当たりの件数が想定より少ない');
  });

  test('バッジ: 節目の判定と一言が Python 版と一致する', () {
    for (final c in fx['badges'] as List) {
      final days = c['days'] as int?;
      final tier = badgeForDays(days);
      expect(tier?.threshold, c['threshold'], reason: 'days=$days の節目が違う');
      expect(tier?.icon, c['icon'], reason: 'days=$days のアイコンが違う');
      expect(tier?.label, c['label'], reason: 'days=$days の呼び名が違う');
      expect(badgeMessage('コマドリ', days), c['message'],
          reason: 'days=$days の一言が違う');
    }
  });

  group('Python の型変換をまねる部分', () {
    test('int(): 小数は0方向へ切り捨て、整数でない文字列は通さない', () {
      expect(pyInt(2), 2);
      expect(pyInt(2.7), 2);
      expect(pyInt(-2.7), -2);
      expect(pyInt('3'), 3);
      expect(pyInt('2.5'), isNull); // Python の int("2.5") は例外
      expect(pyInt('abc'), isNull);
      expect(pyInt(null), isNull);
      expect(pyInt(true), 1);
    });

    test('float(): 小数の文字列も通る', () {
      expect(pyFloat('0.8'), 0.8);
      expect(pyFloat(1), 1.0);
      expect(pyFloat('abc'), isNull);
      expect(pyFloat(''), isNull);
      expect(pyFloat(null), isNull);
    });
  });
}
