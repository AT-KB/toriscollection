/// 広告(AdMob)。`toris_collection/ads.py` の移植。
///
/// ## Streamlit 版の複雑さは全部捨てた
/// 現行は WebView の制約で「JS → localStorage → 1秒ポーリング → クエリ
/// パラメータでトップごとリロード」という片道経路を通していた
/// (`ads.py` の 2026-07-10 P1修正)。ネイティブは視聴完了の
/// コールバックを直接受け取れるので、その回り道は要らない。
///
/// ## 交渉不能の原則をコードに固定する
///  - **原則1 受動的** — 見なくても通常の到来確率は変わらない。効果は6時間で消える。
///  - **原則2 罰しない** — 読み込み失敗・視聴中断でペナルティ無し。黙って戻る。
///  - **原則3 声と癒しは無料** — **ラジオが鳴っている間はバナーを出さない**
///    (`ads.py` の `is_radio_active` と同じ)。全画面割り込みは実装しない。
///  - **原則4 生態に誠実** — 効果は「なぜ来たか」の生態ログに混ぜない。
library;

import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';
import 'package:toris_core/toris_core.dart' as core;

/// AdMob の広告ユニット(CEO 提供・2026-08-21)。
///
/// アプリ ID `ca-app-pub-9002945296291643~1195899268` は
/// `AndroidManifest.xml` の meta-data に書く(ここではない)。
class AdUnits {
  static const banner = 'ca-app-pub-9002945296291643/4334445334';
  static const reward = 'ca-app-pub-9002945296291643/7956060372';

  /// Google 公式のテスト用ユニット。実機で自分の広告を叩かないため、
  /// 動作確認はこちらでやる(自分の広告をクリックすると規約違反になる)。
  static const bannerTest = 'ca-app-pub-3940256099942544/6300978111';
  static const rewardTest = 'ca-app-pub-3940256099942544/5224354917';
}

/// テスト用ユニットを使うか。**実機確認の間は true。**
/// 公開ビルドで true のまま出すと収益が出ないので、上げる前に false に戻す。
const bool kUseTestAds = true;

String get bannerUnitId => kUseTestAds ? AdUnits.bannerTest : AdUnits.banner;
String get rewardUnitId => kUseTestAds ? AdUnits.rewardTest : AdUnits.reward;

/// SDK の初期化。`main()` から1回だけ呼ぶ。
///
/// 失敗しても投げない — 広告が無くてもアプリは全部動く(原則2)。
Future<void> initAds() async {
  try {
    // ⚠️ **待ち切らない。** このアプリはネットワーク無しで全部動くのに、
    // 広告 SDK の初期化を待って起動が止まったら本末転倒(原則1・2)。
    // 電波が悪いと initialize() は数十秒返らないことがある。
    await MobileAds.instance
        .initialize()
        .timeout(const Duration(seconds: 5));
  } catch (_) {
    // 電波が無い・Play 開発者サービスが無い・時間切れ。黙って諦める。
    // 広告が出ないだけで、アプリは全部動く。
  }
}

/// 今日もう受け取ったか。`ads.has_claimed_today` と同じ「ISO日付の文字列比較」。
bool hasClaimedToday(String? lastClaimDay, {DateTime? now}) =>
    lastClaimDay == todayKey(now: now);

/// 今日の日付(保存する形)。
String todayKey({DateTime? now}) {
  final d = now ?? DateTime.now();
  return '${d.year.toString().padLeft(4, '0')}-'
      '${d.month.toString().padLeft(2, '0')}-'
      '${d.day.toString().padLeft(2, '0')}';
}

/// この庭で**いま選べる**アイテム。
///
/// CEO 確定仕様(2026-07-09)により選ばせない = ここから**ランダムに1つ**。
/// 出す候補は `kOfferedItems` の3種だけ(CEO 2026-08-21)。
List<String> offeredItems(
    String biomeId, Map<String, dynamic> birdsData, List<String> feeders) {
  return [
    for (final id in core.kOfferedItems)
      if (core.itemIsAvailable(id, biomeId, birdsData, placedFeeders: feeders))
        id
  ];
}

/// ランダムに1つ選ぶ。候補が無ければ null。
String? pickItem(
    String biomeId, Map<String, dynamic> birdsData, List<String> feeders,
    {Random? rng}) {
  final pool = offeredItems(biomeId, birdsData, feeders);
  if (pool.isEmpty) return null;
  return pool[(rng ?? Random()).nextInt(pool.length)];
}

/// リワード動画の結果。`ads.py` の `ad_result=success|fail|unavailable` と同じ3値。
enum AdResult { success, fail, unavailable }

/// リワード動画を1本見せる。**報酬が確定したときだけ** [AdResult.success]。
///
/// 読み込めない(電波が無い等)は [AdResult.unavailable]、
/// 途中で閉じた・報酬が付かなかったは [AdResult.fail]。
/// どちらも**何も奪わない**。翌日また出る(原則2)。
Future<AdResult> showRewardedAd() async {
  RewardedAd? ad;
  // ⚠️ **`RewardedAd.load()` の Future は「要求を出した」時点で完了する。**
  // 読み込めたかどうかはコールバックでしか分からないので、そこまで待つ
  // (2026-08-21 実機で発覚 — 待たずに諦めていて、広告が出た試しが無かった)。
  final loadDone = Completer<void>();
  void loaded() {
    if (!loadDone.isCompleted) loadDone.complete();
  }

  try {
    await RewardedAd.load(
      adUnitId: rewardUnitId,
      request: const AdRequest(),
      rewardedAdLoadCallback: RewardedAdLoadCallback(
        onAdLoaded: (a) {
          ad = a;
          loaded();
        },
        onAdFailedToLoad: (_) {
          ad = null;
          loaded();
        },
      ),
    );
    // 電波が悪いときに永久に待たない。切れたら「今日は無し」でいい(原則2)。
    await loadDone.future.timeout(const Duration(seconds: 20));
  } catch (_) {
    return AdResult.unavailable;
  }
  final loadedAd = ad;
  if (loadedAd == null) return AdResult.unavailable;

  var earned = false;
  final done = Completer<void>();
  void finish() {
    if (!done.isCompleted) done.complete();
  }

  loadedAd.fullScreenContentCallback = FullScreenContentCallback(
    onAdDismissedFullScreenContent: (a) {
      a.dispose();
      finish();
    },
    onAdFailedToShowFullScreenContent: (a, _) {
      a.dispose();
      finish();
    },
  );
  await loadedAd.show(onUserEarnedReward: (_, _) => earned = true);
  await done.future;
  return earned ? AdResult.success : AdResult.fail;
}

/// ホーム下部の静かなバナー1枚。
///
/// [radioPlaying] が true の間は**何も描かない**(原則3)。読み込みに失敗した
/// ときも高さ0で消える — 「広告が入るはずの空白」を残さない。
class QuietBanner extends StatefulWidget {
  final bool radioPlaying;
  const QuietBanner({super.key, required this.radioPlaying});

  @override
  State<QuietBanner> createState() => _QuietBannerState();
}

class _QuietBannerState extends State<QuietBanner> {
  BannerAd? _ad;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final ad = BannerAd(
      adUnitId: bannerUnitId,
      size: AdSize.banner,
      request: const AdRequest(),
      listener: BannerAdListener(
        onAdLoaded: (_) {
          if (mounted) setState(() => _loaded = true);
        },
        onAdFailedToLoad: (a, _) {
          a.dispose();
          if (mounted) setState(() => _loaded = false);
        },
      ),
    );
    _ad = ad;
    ad.load();
  }

  @override
  void dispose() {
    _ad?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.radioPlaying || !_loaded || _ad == null) {
      return const SizedBox.shrink();
    }
    return SizedBox(
      width: _ad!.size.width.toDouble(),
      height: _ad!.size.height.toDouble(),
      child: AdWidget(ad: _ad!),
    );
  }
}
