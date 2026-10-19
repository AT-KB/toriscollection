/// 表示言語の切り替え(`lib/i18n.dart`)。
///
/// ## なぜ足したか(CEO 2026-10-19「日本語に切り替えってできない?」→「やれ」)
/// 方針は 2026-07-17 に CEO 承認済み(`HANDOFF_I18N_2026-07-17.md`):
/// **辞書 + EN/JA 切替・既定は EN**。
///
/// ⚠️ ここで押さえたいのは、切り替わることだけではない。
/// **「`t()` で包んだのに辞書に入れ忘れる」**のが、この作りでいちばん起きる
/// 壊れ方で、しかも画面は英語のまま**黙って**出る(落ちない)。
/// だから最後の試験で、**画面が使っている鍵が辞書に全部あるか**を実際に
/// ソースを読んで突き合わせる。
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:toris_app/i18n.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    L10n.lang.value = Lang.en;
  });

  test('既定は英語。英語のときは、鍵がそのまま返る', () {
    expect(L10n.lang.value, Lang.en);
    expect(t('Wake with the birds'), 'Wake with the birds');
  });

  test('日本語に切り替えると、辞書の訳が返る', () {
    L10n.lang.value = Lang.ja;
    expect(t('Wake with the birds'), '鳥の声で起きる');
    expect(t('Guide'), '図鑑');
  });

  test('辞書に無い文言は、日本語でも英語のまま出る(落ちない)', () {
    L10n.lang.value = Lang.ja;
    expect(t('This string is not in the dictionary'),
        'This string is not in the dictionary');
  });

  test('選んだ言語は覚えていて、次に開くと戻る', () async {
    await L10n.set(Lang.ja);
    final p = await SharedPreferences.getInstance();
    expect(p.getString('app_lang'), 'ja');

    L10n.lang.value = Lang.en; // アプリを開き直したつもり
    await L10n.restore();
    expect(L10n.lang.value, Lang.ja);
  });

  test('英語に戻したことも覚えている', () async {
    await L10n.set(Lang.ja);
    await L10n.set(Lang.en);
    L10n.lang.value = Lang.ja;
    await L10n.restore();
    expect(L10n.lang.value, Lang.en,
        reason: '英語に戻した人が、開き直すと日本語になってしまう');
  });

  // ── ここが本題 ────────────────────────────────────────────
  test('画面が使っている鍵は、辞書に全部ある(包んだのに訳し忘れた、を捕まえる)', () {
    final lib = Directory('lib');
    expect(lib.existsSync(), isTrue,
        reason: 'lib/ が読めないと、この試験は何も見ていないことになる');

    // t('...') / t("...") の中身を集める。変数を渡している形は見ない。
    final call = RegExp(r"""\bt\(\s*(?:'([^'\n]*)'|"([^"\n]*)")\s*\)""");
    final keys = <String, List<String>>{};
    var scanned = 0;
    for (final f in lib.listSync(recursive: true)) {
      if (f is! File || !f.path.endsWith('.dart')) continue;
      if (f.path.endsWith('i18n.dart')) continue; // 辞書そのものは除く
      scanned++;
      for (final m in call.allMatches(f.readAsStringSync())) {
        final k = m.group(1) ?? m.group(2)!;
        keys.putIfAbsent(k, () => []).add(f.path);
      }
    }

    // ⚠️ 空振り防止。読めていない / 1件も拾えていないなら、この試験は
    // 何も守っていない(2026-08-21 に緩すぎる検査で2回やらかしている)。
    expect(scanned, greaterThan(5), reason: 'lib/ の .dart をほとんど読めていない');
    expect(keys.length, greaterThan(10),
        reason: "t('...') を1件も拾えていない = 正規表現が効いていない");

    final missing = [
      for (final e in keys.entries)
        if (!L10n.dictionary.containsKey(e.key))
          '${e.key}  (${e.value.join(", ")})'
    ];
    expect(missing, isEmpty,
        reason: '画面は t() で包んでいるのに辞書に無い。'
            '日本語にしても英語のまま黙って出る:\n${missing.join("\n")}');
  });

  test('辞書の訳は、鍵と同じではない(入れ忘れの空埋めを捕まえる)', () {
    final same = [
      for (final e in L10n.dictionary.entries)
        if (e.key == e.value) e.key
    ];
    // 固有名詞はそのままでよいので、許す鍵をここに並べる。
    const allowed = {'English', '日本語'};
    expect(same.where((k) => !allowed.contains(k)), isEmpty,
        reason: '訳が英語のまま入っている(辞書に載せただけで訳していない)');
  });
}
