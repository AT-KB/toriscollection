/// Toris Collection — Flutter 版(移行中)。
///
/// ## なぜ Flutter に移るのか
/// 現行版は Streamlit を WebView で包んだ構成で、**通知・目覚まし・端末連携が
/// 原理的に作れない**。目覚ましは仕方なくネイティブ Java で書き、WebView から
/// JavaScript 経由で叩いていた。今後「通知」「睡眠データ」「ウィジェット」に
/// 触れるたび同じ壁が来る。判断の根拠は
/// `toris_collection/docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md`。
///
/// ## いまの段階
/// 移行の目的そのもの(目覚まし)を先に立て、続いてラジオを移した。
/// 図鑑・庭・植える・ネットワークはまだ現行版にしかない。全機能の台帳は
/// `docs/team/proposals/2026-08-13_移行計画_全機能の棚卸し.md`。
///
/// ## 守ること
/// - **表示は英語のみ。** 製品版は 2026-08-09 に日本語表示を落としている。
///   文言は i18n.py の TRANSLATIONS にある出荷済みの英語を引き写す。
/// - **セーブコードの互換。** 進行データはサーバーに無く、あの文字列としてのみ
///   ユーザーの手元にある(`toris_core` で双方向の一致を確認済み)。
///
/// ## パッケージ名について
/// いまは `com.toriscollection.toris_app`。製品版は `com.toriscollection.app`。
/// **わざと別にしてある** — 同じにすると開発中のビルドが Play 版を潰すため。
/// 切り替え(提案書 §3 ステップ3)のときに製品版の名前へ変える。
library;

import 'package:flutter/material.dart';

import 'alarm/alarm_page.dart';
import 'radio/radio_page.dart';

void main() => runApp(const TorisApp());

class TorisApp extends StatelessWidget {
  const TorisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Toris Collection',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF7BA87B)),
        useMaterial3: true,
      ),
      home: const HomeShell(),
    );
  }
}

/// タブの骨組み。現行版のタブ構成(ラジオ/庭/植える/図鑑/ネットワーク/使い方)に
/// 合わせて増やしていく。いまはラジオと目覚ましだけ。
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  // IndexedStack にしているのは、タブを移ってもラジオを鳴らし続けるため
  // (作り直すと音が途切れる)。
  final List<Widget> _pages = const [RadioPage(), AlarmPage()];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.mic), label: 'Radio'),
          NavigationDestination(icon: Icon(Icons.alarm), label: 'Wake'),
        ],
      ),
    );
  }
}
