# toris_core

Toris Collection の**中身**(UI を持たない部分)。Streamlit(Python)から Flutter へ
移すにあたり、判断のロジックをここに集める。Flutter に依存しないので
`dart test` だけで速く回せる。

## 移植の正しさを、どう担保するか

「移しました」という申告ではなく、**Python 版と同じ答えを返すこと**を機械で見る。

| 対象 | 確かめ方 |
|---|---|
| セーブコード | Python が書いた実物を Dart が読め、**Dart が書いたものを Python が読める**ことを両方向で確認 |
| 群れ・バッジ | Python に入力を総当たりで食わせた答えの表を作り、Dart が再現できるかを比較(391通り+13通り) |

手で書き写したテストには、書き写した人の思い込みも一緒に写る。だから答えは
Python 側から取る。

## 使い方

```sh
py -3 tools/save_code_fixtures.py          # Python が書いたセーブコードを用意
py -3 tools/logic_fixtures.py              # Python の答えの表を用意
dart test                                   # Dart が再現できるか
py -3 tools/save_code_fixtures.py --verify # Dart が書いたコードを Python が読み返す
```

## いま入っているもの

- `save_code.dart` — セーブコードの読み書き。**互換を絶対に壊せない**(進行データは
  サーバーに無く、この文字列としてのみユーザーの手元にある)
- `flock.dart` — 群れのサイズ
- `badges.dart` — 「会った日数」の節目
- `py_coerce.dart` — Python の `int()` / `float()` と同じ型変換
  (種データは Sheets 由来で型が揃わず、変換の失敗が分岐に意味を持つため)

## まだ移していないもの

`engine.py`(到来確率)・`ecology.py`・`disturbance.py`・`daily.py`・`absence_loop.py`。
