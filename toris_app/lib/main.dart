/// Toris Collection — Flutter 版(移行中)。
///
/// ## なぜ Flutter に移るのか
/// 現行版は Streamlit を WebView で包んだ構成で、**通知・目覚まし・端末連携が
/// 原理的に作れない**。判断の根拠は
/// `toris_collection/docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md`。
///
/// ## 守ること
/// - **表示は英語のみ。** 製品版は 2026-08-09 に日本語表示を落としている。
///   文言は i18n.py の TRANSLATIONS にある出荷済みの英語を引き写す。
/// - **文字は少なく、ボタンは大きく**(CEO 2026-08-14)。決めごとは `ui/theme.dart`。
/// - **セーブコードの互換。** 進行データはサーバーに無く、あの文字列としてのみ
///   ユーザーの手元にある(`toris_core` で双方向の一致を確認済み)。
///
/// ## この版で「やめた」機能(CEO 2026-08-14)
/// 季節による絞り込み / 時間帯によるさえずり・地鳴きの出し分け / BGMモード。
/// 簡素化のため移植しない。
///
/// ## パッケージ名について
/// いまは `com.toriscollection.toris_app`。製品版は `com.toriscollection.app`。
/// **わざと別にしてある** — 同じにすると開発中のビルドが Play 版を潰すため。
library;

import 'package:flutter/material.dart';

import 'alarm/alarm_page.dart';
import 'garden/garden_page.dart';
import 'garden/garden_state.dart';
import 'garden/guide_page.dart';
import 'garden/network_page.dart';
import 'radio/radio_page.dart';
import 'ui/theme.dart';

void main() => runApp(const TorisApp());

class TorisApp extends StatelessWidget {
  const TorisApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Toris Collection',
    theme: buildTheme(),
    home: const HomeShell(),
  );
}

/// 5つのタブ。現行版(Streamlit)のタブ構成に合わせてある。
/// 「使い方」は現行にはあるが、**説明が要らない作りにする**方針なので置かない。
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  /// 庭の状態は全画面で共有する。**会った回数**がラジオ(近さ・群れ)と
  /// 図鑑に効くので、ここを唯一の持ち主にする。
  Garden? _garden;

  @override
  Widget build(BuildContext context) {
    // IndexedStack にしているのは、タブを移ってもラジオを鳴らし続けるため。
    final pages = [
      RadioPage(
        observed: _garden?.observed ?? const {},
        biomeId: _garden?.biomeId ?? 'charlotte',
      ),
      GardenPage(onChanged: (g) => setState(() => _garden = g)),
      GuidePage(garden: _garden),
      NetworkPage(garden: _garden),
      const AlarmPage(),
    ];
    // ── チュートリアル中は、庭だけ ──
    // 他のタブは押しても反応しない(CEO 2026-08-16「ほか押せない」)。
    // やることが1つに定まるまで、選択肢を出さない。
    final tutorial = _garden?.tutorialRunning ?? false;
    if (tutorial && _index != 1) _index = 1;

    return Scaffold(
      body: IndexedStack(index: tutorial ? 1 : _index, children: pages),
      bottomNavigationBar: IgnorePointer(
        ignoring: tutorial,
        child: Opacity(
          opacity: tutorial ? 0.35 : 1.0,
          child: NavigationBar(
            selectedIndex: tutorial ? 1 : _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.graphic_eq),
                label: 'Radio',
              ),
              NavigationDestination(
                icon: Icon(Icons.park_outlined),
                label: 'Garden',
              ),
              NavigationDestination(
                icon: Icon(Icons.menu_book_outlined),
                label: 'Guide',
              ),
              NavigationDestination(
                icon: Icon(Icons.hub_outlined),
                label: 'Network',
              ),
              NavigationDestination(icon: Icon(Icons.alarm), label: 'Wake'),
            ],
          ),
        ),
      ),
    );
  }
}
