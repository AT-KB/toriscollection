/// まだ Python と突き合わせていなかった移植を、同じ入力で比べる(2026-11-10)。
///
/// 表は `tools/parity2_fixtures.py` が Python 版を総当たりで動かして作る。
/// 期待値を手で書かない(書き写した人の思い込みも一緒に写るため)。
///
/// 対象: temperatureFit / currentTemperature / coOccurrenceMatrix /
/// animalsPresent / raptorsPresent / profileLikes / profileHome / profileFears /
/// plantSensitivity / getCentrality / loadCentralities / centralityIsAvailable /
/// parseIso / encodeCurrentState
library;

import 'dart:convert';
import 'dart:io';

import 'package:test/test.dart';
import 'package:toris_core/toris_core.dart';

Map<String, dynamic> _j(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

void main() {
  final fx = _j('parity2.json');
  final birds = _j('birds.json');
  final plants = _j('plants.json');
  final insects = _j('insects.json');
  final biomes = _j('biomes.json');
  final season = _j('season_offset.json');
  final predators = _j('predators.json');

  test('temperatureFit は Python と同じ(1800通り)', () {
    final rows = fx['temperature_fit'] as List;
    expect(rows.length, greaterThan(100));
    for (final c in rows) {
      final got = temperatureFit((c['temp'] as num).toDouble(), c['range'] as List);
      expect(got, closeTo((c['want'] as num).toDouble(), 1e-12),
          reason: 'temp=${c['temp']} range=${c['range']}');
    }
  });

  test('currentTemperature は Python と同じ(土地 × 12か月)', () {
    for (final c in fx['current_temperature'] as List) {
      final got = currentTemperature(
          c['biome'] as String, c['month'] as int, biomes, season);
      expect(got, closeTo((c['want'] as num).toDouble(), 1e-12),
          reason: '${c['biome']} ${c['month']}月');
    }
  });

  test('coOccurrenceMatrix は Python と同じ', () {
    for (final c in fx['co_occurrence_matrix'] as List) {
      final ids = [for (final x in c['ids'] as List) '$x'];
      final got = coOccurrenceMatrix(ids, birds);
      final want = c['want'] as List;
      expect(got.length, want.length);
      for (var i = 0; i < want.length; i++) {
        for (var j = 0; j < want.length; j++) {
          expect(got[i][j], closeTo((want[i][j] as num).toDouble(), 1e-12),
              reason: '${ids[i]} × ${ids[j]}');
        }
      }
    }
  });

  test('animalsPresent / raptorsPresent は Python と同じ', () {
    for (final c in fx['feeder_chain'] as List) {
      final f = [for (final x in c['features'] as List) '$x'];
      final p = [for (final x in c['plants'] as List) '$x'];
      final a = animalsPresent(f, p, baffled: c['baffled'] as bool);
      expect(a, [for (final x in c['animals'] as List) '$x'],
          reason: 'features=$f plants=$p baffled=${c['baffled']}');
      expect(raptorsPresent(a), [for (final x in c['raptors'] as List) '$x']);
    }
  });

  test('profileLikes / profileHome / profileFears は Python と同じ(全37種)', () {
    final rows = fx['bird_profile'] as List;
    expect(rows.length, 37);
    for (final c in rows) {
      final id = c['id'] as String;
      final b = (birds[id] as Map).cast<String, dynamic>();
      expect(
          [for (final l in profileLikes(b, plants, insects)) [l.kind, l.id]],
          c['likes'],
          reason: '$id の好きなもの');
      expect(profileHome(b, biomes), c['home'], reason: '$id の好きな場所');
      final f = profileFears(id, predators);
      final want = c['fears'] as Map;
      expect(f.categories, want['categories'], reason: '$id のこわいもの');
      expect(f.genusLevel, want['genus_level'], reason: '$id の属レベル');
    }
  });

  test('plantSensitivity は Python と同じ(範囲外・文字列・欠けも)', () {
    final ps = fx['plant_sensitivity'] as Map;
    final pd = (ps['plants'] as Map).cast<String, dynamic>();
    for (final c in ps['cases'] as List) {
      expect(plantSensitivity(c['id'] as String, pd),
          closeTo((c['want'] as num).toDouble(), 1e-12),
          reason: '${c['id']}');
    }
    (ps['real'] as Map).forEach((id, want) {
      expect(plantSensitivity('$id', plants),
          closeTo((want as num).toDouble(), 1e-12),
          reason: '出荷データの $id');
    });
  });

  test('getCentrality / loadCentralities / centralityIsAvailable は Python と同じ', () {
    final c = fx['centrality'] as Map;
    final table = loadCentralities((c['table'] as Map).cast<String, dynamic>());
    expect(centralityIsAvailable(table), isTrue);
    expect(centralityIsAvailable(const {}), isFalse);
    expect(centralityIsAvailable(null), isFalse);
    for (final k in c['cases'] as List) {
      final got = getCentrality(k['name'] as String, table,
          useCorrected: k['corrected'] as bool);
      final want = k['want'];
      if (want == null) {
        expect(got, isNull, reason: '${k['name']} corrected=${k['corrected']}');
      } else {
        expect(got, closeTo((want as num).toDouble(), 1e-20),
            reason: '${k['name']} corrected=${k['corrected']}');
      }
    }
  });

  test('parseIso は Python と同じ(読めないものは null)', () {
    for (final c in fx['parse_iso'] as List) {
      final got = parseIso(c['in']);
      final want = c['want'] as String?;
      if (want == null) {
        expect(got, isNull, reason: '${c['in']}');
      } else {
        expect(got, DateTime.parse(want), reason: '${c['in']}');
      }
    }
  });

  test('encodeCurrentState は Python と同じ中身になる', () {
    // 圧縮のバイト列は実装で揺れうるので、**解いた中身**で比べる。
    final e = fx['encode_current_state'] as Map;
    final state = (e['state'] as Map).cast<String, dynamic>();
    final now = DateTime.parse(e['now'] as String);
    final mine = decodeSave(encodeCurrentState(state, now: now));
    final theirs = decodeSave(e['code'] as String);
    expect(mine, isNotNull);
    expect(theirs, isNotNull, reason: 'Python のコードを Dart が読めない');
    // 集合(Set)は JSON にできないので、並べた list にして比べる。
    Object? norm(Object? v) => v is Set
        ? (v.map((e) => '$e').toList()..sort())
        : v is Map
            ? {for (final e in v.entries) '${e.key}': norm(e.value)}
            : v is List
                ? [for (final x in v) norm(x)]
                : v;
    expect(jsonEncode(norm(mine)), jsonEncode(norm(theirs)));
  });
}
