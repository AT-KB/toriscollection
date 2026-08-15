/// セーブコードの受け渡し。現行(Streamlit)の「セーブコード」欄に当たる。
///
/// **端末を替えたときに進行を失わせないための唯一の道。**
///
/// 現行は WebView の制約で手段が4つ並んでいた(コピー・書き出し・直接表示・共有)。
/// CEO から「コピーと書き込むの違いが分からない」と指摘があった箇所で、
/// ネイティブでは全部要らない。**コピーする / 貼り付ける の2つだけ**にする
/// (CEO 2026-08-15「スタイリッシュにして」)。
///
/// いつかアカウント登録に移すつもりの場所(CEO 談)。それまではこのコードが控え。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:toris_core/toris_core.dart' as core;

import '../ui/theme.dart';
import 'garden_state.dart';

Future<void> showTransferSheet(BuildContext context, Garden g,
    {required Future<void> Function() onRestored}) {
  return showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => _TransferSheet(garden: g, onRestored: onRestored),
  );
}

class _TransferSheet extends StatefulWidget {
  final Garden garden;
  final Future<void> Function() onRestored;
  const _TransferSheet({required this.garden, required this.onRestored});

  @override
  State<_TransferSheet> createState() => _TransferSheetState();
}

class _TransferSheetState extends State<_TransferSheet> {
  final TextEditingController _input = TextEditingController();
  String? _error;
  bool _pasting = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  Future<void> _copy() async {
    final code = core.encodeCurrentState(widget.garden.toState());
    await Clipboard.setData(ClipboardData(text: code));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Code copied.')),
    );
  }

  /// 貼り付けて戻す。**いまの庭は上書きされる**ので、必ず一度たずねる。
  Future<void> _restore() async {
    final code = _input.text.trim();
    final state = core.decodeSave(code);
    if (state == null) {
      setState(() => _error = "That code doesn't look right.");
      return;
    }
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Replace this garden?'),
        content: const Text(
            'The garden on this phone will be replaced by the one in the code.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Replace')),
        ],
      ),
    );
    if (ok != true) return;

    widget.garden.applyState(state);
    await widget.garden.save();
    await widget.onRestored();
    if (!mounted) return;
    Navigator.pop(context);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Garden restored.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(24, 0, 24, 24 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Move your garden',
              style: TextStyle(
                  fontSize: 20, fontWeight: FontWeight.w600, color: kInk)),
          const SizedBox(height: 8),
          const Text(
            'Your garden is saved on this phone. '
            'You only need a code to move it to another one.',
            style: TextStyle(fontSize: 14, color: kSub, height: 1.5),
          ),
          const SizedBox(height: 24),

          // ── 出す ──
          FilledButton.icon(
            onPressed: _copy,
            icon: const Icon(Icons.copy_rounded, size: 24),
            label: const Text('Copy my code'),
          ),
          const SizedBox(height: 28),

          // ── 入れる ──
          // ふだんは見せない。持ってきた人だけ開く。
          if (!_pasting)
            TextButton(
              onPressed: () => setState(() => _pasting = true),
              child: const Text('I have a code'),
            )
          else ...[
            TextField(
              controller: _input,
              maxLines: 3,
              minLines: 2,
              style: const TextStyle(fontSize: 13),
              decoration: InputDecoration(
                hintText: 'Paste the code here',
                errorText: _error,
                border: const OutlineInputBorder(),
              ),
              onChanged: (_) {
                if (_error != null) setState(() => _error = null);
              },
            ),
            const SizedBox(height: 14),
            FilledButton(
                onPressed: _restore, child: const Text('Bring it back')),
          ],
        ],
      ),
    );
  }
}
