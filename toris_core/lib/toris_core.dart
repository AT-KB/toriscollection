/// Toris Collection の**中身**(UI を持たない部分)。
///
/// Streamlit(Python)から Flutter へ移すにあたり、判断のロジックはここに集める。
/// Flutter に依存しないので `dart test` だけで速く回せる。移植の正しさは
/// Python 版のテストと同じ性質のテストで機械的に確かめる
/// (提案書 §3「テストを先に Dart へ写せば、移植の正しさを機械で確認できる」)。
library;

export 'src/badges.dart';
export 'src/ecology.dart';
export 'src/flock.dart';
export 'src/py_coerce.dart';
export 'src/save_code.dart';
