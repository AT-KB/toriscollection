/// 録音者のクレジット(`lib/credits.dart`)。軸「ドット絵の鳥が、本物の声で鳴く庭」。
///
/// 主張台帳(`06_監査.md` §3)の「鳴き声は実録音・録音者をアプリ内で明記」の検査。
/// 同梱している録音の全部に録音者が付いていて、画面に出す1行が組めることを見る。
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/credits.dart';
import 'package:toris_app/i18n.dart';

void main() {
  test('同梱している録音は全部、録音者と xeno-canto の URL が付いている', () {
    final mp3s = Directory('assets/birds')
        .listSync()
        .map((f) => f.uri.pathSegments.last)
        .where((n) => n.endsWith('.mp3'))
        .map((n) => n.substring(0, n.length - 4))
        .toSet();
    expect(mp3s, isNotEmpty);
    final raw = jsonDecode(File('assets/birds/_credits.json').readAsStringSync())
        as List;
    final byId = {for (final e in raw) '${(e as Map)['id']}': e as Map};
    for (final id in mp3s) {
      final c = byId[id];
      expect(c, isNotNull, reason: '$id.mp3 の録音者が _credits.json に無い');
      expect('${c!['recordist']}'.trim(), isNotEmpty, reason: '$id の録音者が空');
      expect('${c['url']}', startsWith('https://xeno-canto.org/'),
          reason: '$id の出典 URL');
    }
  });

  test('画面に出す1行は「🎙 録音: 名前 · xeno-canto」。無い種は null', () {
    setCreditsForTest({
      'shijukara': const BirdCredit('Peter Boesman', 'https://xeno-canto.org/285681', ''),
    });
    L10n.lang.value = Lang.en;
    expect(creditLine('shijukara'), '🎙 Recording: Peter Boesman · xeno-canto');
    L10n.lang.value = Lang.ja;
    expect(creditLine('shijukara'), '🎙 録音: Peter Boesman · xeno-canto');
    expect(creditLine('no_such_bird'), isNull);
  });

  test('土地の代表の鳥には録音がある(土地を選んだ直後の試聴)', () {
    for (final id in kSignatureBird.values) {
      expect(File('assets/birds/$id.mp3').existsSync(), isTrue, reason: id);
    }
  });
}
