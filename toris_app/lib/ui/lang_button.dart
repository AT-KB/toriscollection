/// 言語の切り替えボタン。**全タブの右上**に置く(CEO 2026-11-03「目立つ場所にしていいよ」)。
///
/// 以前は図鑑の先頭にしか無く、日本語の人が気づけなかった。
/// 押すと**もう一方の言語**に替わる。ラベルは「替わった先の言語」をその言語で書く
/// (言語名はその言語で書くのが世界共通のやり方。英語の人が「English」を探せるように)。
library;

import 'package:flutter/material.dart';

import '../i18n.dart';
import 'theme.dart';

class LangButton extends StatelessWidget {
  const LangButton({super.key});

  // ⚠️ **言語を自分で聞く。** AppBar の actions は `const [LangButton()]` で
  // 置かれるので、親が建て直してもこの widget は飛ばされる(const の罠)。
  // 実機で「英語にしてもボタンが English のまま」になった(2026-11-03)。
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<Lang>(
        valueListenable: L10n.lang,
        builder: (context, lang, _) {
          final toJa = lang == Lang.en;
          return Padding(
            padding: const EdgeInsets.only(right: 4),
            child: TextButton.icon(
              style: TextButton.styleFrom(foregroundColor: kInk),
              icon: const Icon(Icons.translate_rounded, size: 18),
              label: Text(toJa ? '日本語' : 'English'),
              onPressed: () => L10n.set(toJa ? Lang.ja : Lang.en),
            ),
          );
        },
      );
}
