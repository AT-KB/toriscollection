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

  // IndexedStack にしているのは、タブを移ってもラジオを鳴らし続けるため。
  final List<Widget> _pages = const [
    RadioPage(),
    ComingSoon(
      title: 'Garden',
      icon: Icons.park_outlined,
      note: 'Your garden is still in the old app.\nComing here next.',
    ),
    ComingSoon(
      title: 'Guide',
      icon: Icons.menu_book_outlined,
      note: 'The birds you have met.\nComing here next.',
    ),
    ComingSoon(
      title: 'Network',
      icon: Icons.hub_outlined,
      note: 'Who eats what, and who comes because of it.',
    ),
    AlarmPage(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.graphic_eq), label: 'Radio'),
          NavigationDestination(icon: Icon(Icons.park_outlined), label: 'Garden'),
          NavigationDestination(
              icon: Icon(Icons.menu_book_outlined), label: 'Guide'),
          NavigationDestination(icon: Icon(Icons.hub_outlined), label: 'Network'),
          NavigationDestination(icon: Icon(Icons.alarm), label: 'Wake'),
        ],
      ),
    );
  }
}
