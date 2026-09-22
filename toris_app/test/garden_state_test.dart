/// 庭の状態の**往復**。書いたものが、そのまま読み戻せること。
///
/// ## なぜ要るか(2026-08-15)
/// `toState()` は図鑑(`discovered`)と会った日数(`bird_days`)を書いていたのに、
/// `applyState()` がそれを読み戻していなかった。**アプリを閉じるたびに図鑑が
/// 白紙に戻っていた。** 交渉不能の原則2「罰しない」に正面から反する状態を、
/// 実機で何度も開きながら見逃した。
///
/// 見逃した理由ははっきりしていて、**往復を一度も試していなかった**から。
/// 画面を開いて「出ている」ことは確かめたが、閉じて開き直していない。
/// ここでその往復を機械にやらせる。
library;

import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:toris_app/garden/garden_state.dart';
import 'package:toris_core/toris_core.dart' as core;

/// テスト用の最小データ。実データは要らない(見るのは状態の受け渡しだけ)。
GardenData _data() => const GardenData(
      {
        'blue_jay': {'english': 'Blue Jay'},
        'song_sparrow': {'english': 'Song Sparrow'},
      },
      {
        'sakura': {'english': 'Cherry', 'biome': ['kyoto']},
        'sunflower': {'english': 'Sunflower', 'biome': ['charlotte']},
      },
      {},
      {
        'kyoto': {'name_en': 'Kyoto', 'max_plants': 4},
        'charlotte': {'name_en': 'Charlotte', 'max_plants': 4},
      },
      {},
      {},
    );

/// ひととおり埋まった庭を作る。
Garden _filled() {
  final g = Garden(_data(), biomeId: 'kyoto');
  g.planted.add('sakura');
  g.setFeeder('feeder_open');
  g.visiting.addAll(['blue_jay', 'song_sparrow']);
  g.discovered.addAll(['blue_jay', 'song_sparrow']);
  g.observed['blue_jay'] = 7;
  g.birdDays['blue_jay'] = 12;
  g.lastMetDay['blue_jay'] = '2026-08-15';
  g.lastSeenAt = DateTime(2026, 8, 15, 9, 30, 0);
  return g;
}

void main() {
  test('閉じて開き直しても、庭の中身が1つも欠けない', () {
    final before = _filled();
    final after = Garden(_data())..applyState(before.toState());

    expect(after.biomeId, before.biomeId, reason: '土地');
    expect(after.planted, before.planted, reason: '植えたもの');
    expect(after.feeders, before.feeders, reason: '餌台');
    expect(after.visiting.toSet(), before.visiting.toSet(), reason: '来ている鳥');
    expect(after.discovered, before.discovered, reason: '図鑑(来訪済み)');
    expect(after.observed, before.observed, reason: '近くで会った回数');
    expect(after.birdDays, before.birdDays, reason: '会った日数');
    expect(after.lastMetDay, before.lastMetDay, reason: '最後に数えた日');
    expect(after.lastSeenAt, before.lastSeenAt, reason: '前回見た時刻');
  });

  test('書いたキーは、必ず読み戻される(片道になっていないこと)', () {
    // これが**実際に起きた不具合そのもの**。toState に足したのに applyState に
    // 足し忘れると、その項目は毎回失われる。キー単位で見る。
    final before = _filled();
    final state = before.toState();
    final after = Garden(_data())..applyState(state);
    final back = after.toState();

    for (final key in state.keys) {
      if (key == 'saved_at') continue; // 保存した瞬間の時刻。毎回変わってよい
      expect(back[key], isNotNull, reason: '$key が読み戻されていない');
      expect('${back[key]}', '${state[key]}', reason: '$key が往復で変わった');
    }
  });

  group('「なぜ来たか」を外したあとの、古いセーブとの互換', () {
    // ## なぜ要るか(2026-09-22、CEO 判断で eco_log を製品から削除)
    // **書かなくするのはよいが、古いセーブや古い引っ越しコードに `eco_log` が
    // 入っていても読めて落ちないこと。** ここが崩れると、既存ユーザーの
    // 進行データが読めなくなる = 進行が消えたのと同じ。
    //
    // 鍵は `save_code.dart` の `saveKeys` に **`eco_log` を残したまま**に
    // したこと。外すと Python 版(`save_code.py` の SAVE_KEYS)と食い違い、
    // `save_code_test.dart` の往復も `tools/save_code_fixtures.py --verify`
    // も通らなくなる。

    /// 旧版が書いたセーブコードを、当時の形そのままで作る。
    String oldCode() {
      final g = _filled();
      final state = Map<String, dynamic>.from(g.toState());
      // 当時は toState() がこれを書いていた。
      state['eco_log'] = [
        {
          'bird': 'blue_jay',
          'text': 'drawn to Sakura',
          'at': '2026-08-01T10:00:00',
          'plant': 'sakura',
          'insect': null,
        },
        {
          'bird': 'song_sparrow',
          'text': 'drawn to Sunflower',
          'at': '2026-08-02T10:00:00',
          'plant': 'sunflower',
          'insect': null,
        },
      ];
      return core.encodeSave(state);
    }

    test('eco_log の入った古いセーブコードが、そのまま読める', () {
      final decoded = core.decodeSave(oldCode());
      expect(decoded, isNotNull, reason: '古いコードが読めない = 進行が消える');
      expect(decoded!['eco_log'], isNotNull,
          reason: 'saveKeys から eco_log を外すと、ここが落ちる。'
              'Python 版の SAVE_KEYS と食い違い、往復の突き合わせも崩れる');
      // 庭の中身は全部そろっている。
      expect(decoded['biome'], 'kyoto');
      expect(decoded['discovered'], isNotNull);
      expect(decoded['bird_days'], isNotNull);
    });

    test('eco_log の入った古いセーブを読み込んでも、例外を投げず中身が欠けない',
        () {
      final before = _filled();
      final decoded = core.decodeSave(oldCode())!;
      final after = Garden(_data())..applyState(decoded);

      expect(after.biomeId, before.biomeId);
      expect(after.planted, before.planted);
      expect(after.discovered, before.discovered, reason: '図鑑');
      expect(after.observed, before.observed, reason: '近くで会った回数');
      expect(after.birdDays, before.birdDays, reason: '会った日数');
      expect(after.lastSeenAt, before.lastSeenAt);
    });

    test('新しく書くセーブには eco_log を入れない', () {
      final state = _filled().toState();
      expect(state.containsKey('eco_log'), isFalse,
          reason: '書かなくすると決めた。書いていたら削除できていない');
    });

    test('古いセーブを読んで書き直しても、庭の中身は落ちない', () {
      // 引っ越しコードを貼って、そのまま新しいコードを書き出す道すじ。
      final g = Garden(_data())..applyState(core.decodeSave(oldCode())!);
      final again = Garden(_data())..applyState(
          core.decodeSave(core.encodeSave(g.toState()))!);
      expect(again.discovered, _filled().discovered);
      expect(again.birdDays, _filled().birdDays);
      expect(again.observed, _filled().observed);
    });
  });

  test('会った日数は、同じ日に開き直しても増えない', () {
    // `last` を保存していなかった頃は、閉じて開くたびに1日ぶん増えていた。
    final g = _filled();
    final today = DateTime.now();
    final key = '${today.year}-${today.month.toString().padLeft(2, '0')}-'
        '${today.day.toString().padLeft(2, '0')}';
    g.lastSeenAt = today;
    g.birdDays['blue_jay'] = 3;
    g.lastMetDay['blue_jay'] = key;

    final reopened = Garden(_data())..applyState(g.toState());
    // 5分未満なので庭は動かないが、日数の数え直しは走る
    reopened.catchUp(_FixedRandom());
    expect(reopened.birdDays['blue_jay'], 3, reason: '同じ日に二度数えている');
  });

  test('図鑑は、庭が痩せても減らない(原則2「罰しない」)', () {
    final g = _filled();
    g.planted.clear(); // 撹乱で全部倒れた想定
    final after = Garden(_data())..applyState(g.toState());
    expect(after.discovered, containsAll(['blue_jay', 'song_sparrow']));
    expect(after.birdDays['blue_jay'], 12);
  });

  /// 留守の時計が**貯まる**こと。
  ///
  /// ## なぜ要るか(2026-08-18)
  /// CEO「なんで到来全然しないの」。調べたら、短い間隔で開き直すと
  /// **経過時間がそのたびに 0 に戻されて**いた。`catchUp` は 5分未満なら
  /// 何も起こさないのが正しいのに、最後の `lastSeenAt = now` を
  /// **無条件で**書いていたため、数分おきに開くと時計が一生進まない。
  /// 1日中開いても 0 コマ。鳥は永遠に来ない。
  ///
  /// 進まなかったときは、**時計を据え置く**のが正しい。
  test('5分未満で開き直しても、留守の時計は巻き戻らない', () {
    final g = Garden(_data(), biomeId: 'kyoto');
    g.planted.add('sakura');
    // 2分前に開いたばかり。ここで開き直してもコマは進まない(5分未満)。
    final t0 = DateTime.now().subtract(const Duration(minutes: 2));
    g.lastSeenAt = t0;
    g.catchUp(Random(1));
    expect(g.lastTicks, 0, reason: '5分未満なので何も起きないのが正しい');
    expect(g.lastSeenAt, t0,
        reason: '進まなかったのだから時計は据え置き。ここが now になると、'
            '短い間隔で開くたびに経過時間が消え、鳥が永遠に来なくなる');
  });
}

/// 乱数は使わせない(この試験は時間の判定だけを見る)。
class _FixedRandom implements Random {
  @override
  bool nextBool() => false;
  @override
  double nextDouble() => 0.5;
  @override
  int nextInt(int max) => 0;
}
