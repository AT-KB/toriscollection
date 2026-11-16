/// 録音者のクレジットと、短い試聴。軸「ドット絵の鳥が、本物の声で鳴く庭」(2026-11-13)。
///
/// 「本物の録音」と言うだけでは見えない。**誰の録音かを、鳴っている行に出す**
/// (原則4「生態に誠実」。xeno-canto のライセンスの表記義務にも当たる)。
/// 元は `assets/birds/_credits.json`(`tools/bird_audio_collect.py` が書く)。
library;

import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_soloud/flutter_soloud.dart';

import 'i18n.dart';

class BirdCredit {
  final String recordist;
  final String url;
  final String license;
  const BirdCredit(this.recordist, this.url, this.license);
}

/// 鳥ID → クレジット。起動時に `loadBirdCredits` で入れる。無ければ空。
final Map<String, BirdCredit> _credits = {};

Future<void> loadBirdCredits() async {
  try {
    final raw = await rootBundle.loadString('assets/birds/_credits.json');
    for (final e in (jsonDecode(raw) as List)) {
      final m = e as Map;
      final id = '${m['id']}';
      final who = '${m['recordist'] ?? ''}'.trim();
      if (id.isEmpty || who.isEmpty) continue;
      _credits[id] = BirdCredit(who, '${m['url'] ?? ''}', '${m['license'] ?? ''}');
    }
  } catch (_) {
    // 読めなければクレジットの行が出ないだけ。アプリは止めない。
  }
}

BirdCredit? creditOf(String birdId) => _credits[birdId];

/// 試験から中身を差し替える窓。
void setCreditsForTest(Map<String, BirdCredit> m) => _credits
  ..clear()
  ..addAll(m);

/// 「🎙 録音: Peter Boesman · xeno-canto」。録音が無い種は null(行を出さない)。
String? creditLine(String birdId) {
  final c = _credits[birdId];
  if (c == null) return null;
  return '🎙 ${t('Recording')}: ${c.recordist} · xeno-canto';
}

/// 土地を選んだときに3秒だけ聴かせる、その土地の代表の鳥(軸を最初の60秒で)。
const Map<String, String> kSignatureBird = {
  'kyoto': 'mejiro',
  'charlotte': 'northern_cardinal',
};

SoundHandle? _previewHandle;
AudioSource? _previewSrc;

/// 録音を [seconds] 秒だけ鳴らして、静かに止める。
///
/// 試聴は**ラジオでも儀式でもない**。図鑑にも慣れにも数えない。
/// 「会えた鳥だけがラジオで歌う」の約束は、ここでは触らない(試聴は庭の外の音)。
/// 音が出せない状態(目覚ましが鳴っている等)なら、黙って何もしない。
Future<void> playPreview(String birdId, {double seconds = 3}) async {
  try {
    if (!SoLoud.instance.isInitialized) await SoLoud.instance.init();
    await stopPreview();
    final src = await SoLoud.instance.loadAsset('assets/birds/$birdId.mp3');
    _previewSrc = src;
    final h = SoLoud.instance.play(src, volume: 0.9);
    _previewHandle = h;
    final total = Duration(milliseconds: (seconds * 1000).round());
    SoLoud.instance
        .fadeVolume(h, 0, Duration(milliseconds: (seconds * 1000).round()));
    SoLoud.instance.scheduleStop(h, total);
  } catch (_) {}
}

Future<void> stopPreview() async {
  final h = _previewHandle;
  final s = _previewSrc;
  _previewHandle = null;
  _previewSrc = null;
  try {
    if (h != null) await SoLoud.instance.stop(h);
    if (s != null) await SoLoud.instance.disposeSource(s);
  } catch (_) {}
}
