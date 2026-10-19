/// 表示言語の切り替え。**英語が既定**(CEO 承認・`HANDOFF_I18N_2026-07-17.md` §1)。
///
/// ## なぜ辞書が「英語 → 日本語」なのか
/// 現行(Streamlit)の `i18n.py` は **日本語原文 → 英訳** を持っている。
/// ところが Flutter の画面の文言は、その英訳を引き写したものではなく
/// **新しく書かれたもの**だった(2026-10-19 に 84 件を機械的に突き合わせて、
/// `i18n.py` から日本語が取れたのは **9 件だけ**)。
/// だから Flutter 側は**画面にある英語を鍵にして日本語を引く**形にしてある。
/// 鍵が英語そのものなので、辞書に無い文言は**英語のまま出る**(落ちない)。
///
/// ⚠️ **`toris_core` は日本語の原文をそのまま返す**(`badges.dart` の方針)。
/// 訳を当てるのは**表示側の仕事**で、この分担は壊さない。
///
/// ## トーン(交渉不能の原則5「かわいさ最優先」/ 原則1「受動的」)
/// 直訳しない。**急かさない。命令形を足さない。** 英語の原文が静かなら
/// 日本語も静かに。事務的な言い回しは避ける。
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum Lang { en, ja }

/// 画面の文言を引く。**辞書に無ければ英語のまま返す。**
String t(String en) => L10n.t(en);

class L10n {
  /// いまの言語。画面はこれを見て建て直す(`main.dart` の `ValueListenableBuilder`)。
  static final ValueNotifier<Lang> lang = ValueNotifier<Lang>(Lang.en);

  static const _key = 'app_lang';

  /// 覚えていた言語を戻す。**読めなければ英語**(既定が EN なので安全側)。
  static Future<void> restore() async {
    try {
      final p = await SharedPreferences.getInstance();
      final v = p.getString(_key);
      // ⚠️ **両方向に書く。** 「ja のときだけ日本語にする」と書いていて、
      // 試験(「英語に戻したことも覚えている」)に捕まった。起動時はたまたま
      // 英語から始まるので表には出ないが、**戻す道が無い**のは作りとして穴。
      if (v == 'ja') {
        lang.value = Lang.ja;
      } else if (v == 'en') {
        lang.value = Lang.en;
      }
    } catch (_) {
      // 端末の保存が読めないことがある。既定(EN)のまま続ける。
    }
  }

  /// 切り替えて覚える。
  static Future<void> set(Lang l) async {
    lang.value = l;
    try {
      final p = await SharedPreferences.getInstance();
      await p.setString(_key, l == Lang.ja ? 'ja' : 'en');
    } catch (_) {}
  }

  static String t(String en) =>
      lang.value == Lang.en ? en : (ja[en] ?? en);

  /// 試験から中身を見るための窓。
  static Map<String, String> get dictionary => ja;

  /// 英語 → 日本語。**鍵は画面に出ている英語そのもの。**
  static const Map<String, String> ja = {
    // ── タブ ──
    'Radio': 'ラジオ',
    'Garden': '庭',
    'Guide': '図鑑',
    'Network': 'つながり',
    'Wake': '目覚まし',

    // ── 目覚まし(alarm_page.dart) ──
    'Wake with the birds': '鳥の声で起きる',
    'Starts almost too quiet to hear, then grows.':
        '聞こえるか聞こえないかの音から始まって、少しずつ大きくなります。',
    'Set': 'セット',
    'Turn off': '解除',
    'Turned off': '解除しました',
    'First to sing': '最初に鳴く鳥',
    'Stop the birds': '鳥を止める',
    'Your morning callers': '今朝きてくれた鳥',
    'Not set right now': 'いまはセットされていません',
    'Notifications are turned off': '通知が切れています',
    'You will not see a way to stop the alarm':
        '鳴っているときに、止める方法が画面に出ません',
    'Allow': '許可する',
    'Exact timing is not allowed': '正確な時刻で鳴らす許可がありません',
    'The alarm may drift from the time you set':
        'セットした時刻から少しずれることがあります',
    'Settings': '設定',
    'Permission needed for exact timing': '正確な時刻で鳴らすには許可が要ります',
    'Not now': 'いまはしない',
    'Open settings': '設定を開く',
    'Meet birds up close in your garden, and they join this list — and the chorus.':
        '庭で鳥と近くで出会うと、この一覧に加わって、朝のコーラスにも入ります。',

    // ── 図鑑(guide_page.dart) ──
    'By region': '地域順',
    'By rarity': 'レア度順',
    'Likes': '好きなもの',
    'Home': '好きな場所',
    'Fears': '苦手なもの',
    'Not yet in your garden.': 'まだ庭に来ていません。',
    'Listen closely in the garden to see it up close.':
        '庭で耳を澄ますと、近くで見られます。',
    '(from records of close relatives)': '(近縁のなかまの記録から)',
    '🖼️ See a real photo': '🖼️ 実物の画像を見る',
    '📖 Wikipedia (EN)': '📖 Wikipedia(英)',

    // ── 出会い・おかえり(popups.dart) ──
    '🪶 You met a bird': '🪶 鳥に出会えました',
    '🌿 Welcome back': '🌿 おかえりなさい',
    'Newly added to your guide': '図鑑に加わりました',
    'Close': 'とじる',
    'View the garden': '庭を見る',

    // ── 庭(garden_page.dart) ──
    'A tool for today': 'きょうの道具',
    'No tool this time. It will be here tomorrow too.':
        'きょうは道具がありませんでした。あすもここにあります。',
    'Add': '足す',
    'Feeder': '餌台',
    'No one yet.': 'まだ誰も来ていません。',
    'Listen closely': '耳を澄ます',
    'Enough': 'おしまい',
    "🌙 You've listened closely enough for today. When a new bird comes, you can go and meet it again.":
        '🌙 きょうはもう十分に耳を澄ましました。新しい鳥が来たら、また会いに行けます。',
    'Your land': 'あなたの土地',
    'Plant': '植えたもの',
    'Nothing planted yet.': 'まだ何も植えていません。',
    'The squirrel drew a hawk. Shy birds keep their distance.':
        'リスが鷹を呼びました。警戒心の強い鳥は近づきません。',
    'A squirrel is taking the seed.': 'リスが種を食べています。',

    // ── 出会い・おかえり(popups.dart) ──
    '✨ Nice to meet you! Newly added to your guide':
        '✨ はじめまして。図鑑に加わりました',

    // ── ラジオ(radio_page.dart) ──
    'Garden radio': '庭のラジオ',
    'Listen': '聴く',
    'Stop': '止める',
    'Birds': '鳥の声',
    'Ambience': '環境音',
    'Sleep': '寝落ち',

    // ── 環境音の名前(radio_engine.dart の kAmbienceLabel) ──
    '🌧 Rain': '🌧 雨',
    '🍃 Wind': '🍃 風',
    '💧 Stream': '💧 せせらぎ',
    '🌊 Waves': '🌊 波',
    '🏞 Lake': '🏞 湖',
    '🔥 Fire': '🔥 焚き火',
    '🕳 Cave': '🕳 洞窟',

    // ── つながり(network_page.dart) ──
    'Bird': '鳥',

    // ── 言語の切り替え(guide_page.dart の先頭) ──
    'Language': '言語',
    'English': 'English',
    '日本語': '日本語',
  };
}
