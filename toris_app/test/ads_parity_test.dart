/// きょうの道具の「1日1回」を、Python 版(`ads.has_claimed_today` /
/// `ads.mark_claimed_today`)と同じ答えにする(2026-11-10)。
///
/// 表は `tools/parity2_fixtures.py` が Python 版を動かして作る。
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/ads/ads.dart' as ads;

void main() {
  test('hasClaimedToday / todayKey は Python と同じ', () {
    final fx = jsonDecode(
            File('../toris_core/test/fixtures/parity2.json').readAsStringSync())
        as Map<String, dynamic>;
    final c = fx['claimed_today'] as Map;
    final now = DateTime.parse('${c['today']}T12:00:00');
    // mark_claimed_today が書く文字列 = todayKey
    expect(ads.todayKey(now: now), c['marked']);
    for (final k in c['cases'] as List) {
      expect(ads.hasClaimedToday(k['stored'] as String?, now: now), k['want'],
          reason: 'stored=${k['stored']}');
    }
  });
}
