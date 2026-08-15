/// 画面まわりの共通の決めごと。
///
/// CEO 指摘(2026-08-14)「文字の量を少なくしよう」「タブとかボタンを大きくして、
/// 操作性をよくしてほしい、シンプルに」。
///
/// そこで次を全画面の約束にする:
///  - **説明文は1行まで。** 説明が要る画面は、そもそも作りが複雑すぎる。
///  - **主なボタンは高さ 64。** 親指で狙わずに押せる大きさ。
///  - **1画面に1つの主役。** 副次的な操作は下に小さく置く。
library;

import 'package:flutter/material.dart';

const Color kGreen = Color(0xFF7BA87B);
const Color kBg = Color(0xFFF7FAF2);
const Color kBar = Color(0xFFCFD9B8);
const Color kInk = Color(0xFF2F4A2A);
const Color kSub = Color(0xFF6B7B66);

/// 主なボタンの高さ。押し間違えない大きさを全画面で揃える。
const double kBigButton = 64;

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: kGreen);
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    scaffoldBackgroundColor: kBg,
    appBarTheme: const AppBarTheme(
      backgroundColor: kBar,
      centerTitle: false,
      titleTextStyle: TextStyle(
          color: kInk, fontSize: 22, fontWeight: FontWeight.w600),
    ),
    // タブも大きく。ラベルは常に出す(アイコンだけだと意味が伝わらない)。
    navigationBarTheme: NavigationBarThemeData(
      height: 76,
      backgroundColor: kBar,
      indicatorColor: Colors.white.withValues(alpha: 0.55),
      labelTextStyle: WidgetStateProperty.all(
        const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: kInk),
      ),
      iconTheme: WidgetStateProperty.all(const IconThemeData(size: 26)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(kBigButton),
        textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
    ),
    chipTheme: const ChipThemeData(
      labelStyle: TextStyle(fontSize: 15),
      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 10),
    ),
  );
}

/// 画面の見出し。説明を足したくなったら、まず作りを疑うこと。
class PageTitle extends StatelessWidget {
  final String text;
  const PageTitle(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: Text(text,
            style: const TextStyle(
                fontSize: 15, color: kSub, height: 1.4)),
      );
}

/// まだ移していない画面の置き場。
///
/// 現行版(Streamlit)にはあるが Flutter 版には無い、と正直に出す。
/// 空の画面を黙って出すより、何が来るのかが分かるほうがよい。
class ComingSoon extends StatelessWidget {
  final String title;
  final String note;
  final IconData icon;
  const ComingSoon(
      {super.key, required this.title, required this.note, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 56, color: kBar),
              const SizedBox(height: 16),
              Text(note,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: kSub, height: 1.5)),
            ],
          ),
        ),
      ),
    );
  }
}
