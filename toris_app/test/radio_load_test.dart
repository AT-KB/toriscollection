/// ラジオの読み込みが**二重に走らない**こと、**古い失敗を画面に残さない**こと。
///
/// ## なぜこのファイルがあるか(2026-09-22 実機 Pixel 9a)
/// `.dev`(2.0.3+11)でラジオ画面を開くと、赤字で
/// `SoLoudNotInitializedException: SoLoud has not been initialized yet.`
/// が出たまま残っていた。force-stop して開き直しても再現。
/// ただし Listen は押せて、顔ぶれも出ている。
///
/// コードを読んで裏を取った原因は2つ:
///
/// 1. **`load()` が2経路から並行に呼ばれていた。**
///    `radio_page.dart` の `initState`(このとき `observed` は空)と、
///    庭を読み終えたあとの `didUpdateWidget` → `refreshObserved`。
///    `SoLoud.init()` は**すでに初期化済みの状態で呼ばれると deinit してから
///    入れ直す**(flutter_soloud 4.1.7 `soloud.dart` の `_initialize` は
///    `nativeIsInitialized` なら `_deinitAsync` → 再 init)。
///    2本目の init が1本目の足元を外し、1本目が例外で落ちる。
/// 2. **成功しても `error` を消していなかった。**
///    `catch` で `error = '$e'` と書くだけだったので、一度出た赤字は
///    **そのあと何回成功しても残り続ける**。
///
/// ⚠️ ここで見ているのは**直列化の仕組みと、結果の記録の仕方**だけ。
/// SoLoud を実際に初期化する経路は試験から触れないので、
/// **赤字が出ないことの確認は実機の手作業**(報告に「未確認」と書くこと)。
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/radio/radio_engine.dart';

void main() {
  group('直列化(TaskQueue)', () {
    test('重ねて呼んでも、一度に走るのは1本だけ', () async {
      // ⚠️ **ここが不具合の本体。** 2本が同時に SoLoud を触ると、
      // 片方の init がもう片方の音源を巻き込んで落とす。
      final q = TaskQueue();
      var inFlight = 0;
      var maxInFlight = 0;
      final order = <int>[];

      Future<void> task(int id, int ticks) async {
        inFlight++;
        if (inFlight > maxInFlight) maxInFlight = inFlight;
        for (var i = 0; i < ticks; i++) {
          await Future<void>.delayed(Duration.zero);
        }
        order.add(id);
        inFlight--;
      }

      // 待たずに3本投げる = 実機で起きていたこと。
      final a = q.add(() => task(1, 5));
      final b = q.add(() => task(2, 1));
      final c = q.add(() => task(3, 3));
      await Future.wait([a, b, c]);

      expect(maxInFlight, 1,
          reason: '2本以上が同時に走っている。SoLoud の初期化と音源読み込みが競合する');
      expect(order, [1, 2, 3], reason: '投げた順に、前のものを待ってから始まること');
    });

    test('1本目が落ちても、次は止まらない', () async {
      // 読み込みは何度でもやり直せる。失敗が行列を詰まらせてはいけない。
      final q = TaskQueue();
      var ran = false;
      final bad = q.add(() async => throw StateError('落ちた'));
      final good = q.add(() async => ran = true);

      await expectLater(bad, throwsStateError);
      await good;
      expect(ran, isTrue, reason: '前が落ちると次が永久に走らない = ラジオが二度と鳴らない');
    });

    test('走っている間は busy、終われば戻る', () async {
      final q = TaskQueue();
      expect(q.busy, isFalse);
      final f = q.add(() => Future<void>.delayed(Duration.zero));
      await f;
      expect(q.busy, isFalse);
    });
  });

  group('読み込みの結果の記録', () {
    test('成功したら、古い失敗は消える', () async {
      // **これが「赤字が永久に残る」の直し。**
      final e = RadioEngine();
      expect(e.error, isNull);

      e.recordLoadResult(
          StateError('SoLoudNotInitializedException: not initialized yet'));
      expect(e.error, isNotNull);
      expect(e.ready, isFalse);

      e.recordLoadResult(null);
      expect(e.error, isNull,
          reason: '成功しても消さないと、一度出た赤字が画面に残り続ける');
      expect(e.ready, isTrue);
    });

    test('失敗したら ready を立てない', () {
      final e = RadioEngine();
      e.recordLoadResult(null);
      expect(e.ready, isTrue);
      e.recordLoadResult(StateError('また落ちた'));
      expect(e.ready, isFalse,
          reason: '落ちたのに ready のままだと、鳴らない Listen が押せてしまう');
      expect(e.error, contains('また落ちた'));
    });
  });
}
