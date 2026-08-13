# 音のスパイク(ステップ0)

Flutter へ移るかどうかを**耳で**決めるための、使い捨て前提の小さなアプリ。
根拠と位置づけは
`toris_collection/docs/team/proposals/2026-08-11_技術方針_Flutter移行の判断.md` §3。
他は一切触らず、いちばん危ない場所(音)だけを先に確かめる。

## 何を確かめるか

提案書は「移行の成否は**ラジオの音響エンジン**で決まる」と書いた。中身は:

| 現行(radio.py の WebAudio) | このスパイクでの扱い |
|---|---|
| 鳴く/休むの状態機械、休符で同時発声を ~1.2 羽に保つ | Dart に写した(定数もそのまま) |
| 立ち上がり/収まりのフェード、奥行きによる音量差 | SoLoud の fadeVolume で写した |
| リバーブ(奥行き=近さ) | SoLoud の freeverb。b1/b2/b3 で深さを変える |
| **ノイズゲート**(無音時の暗騒音を絞る) | **持ち込まない**。録音を鳴らす前に消しておく |
| **AGC**(録音ごとの音量差を吸収) | **持ち込まない**。録音を鳴らす前に揃えておく |

最後の2つが移植の最大の壁だったが、**実時間でやる必要が無かった**。
`tools/bird_audio_prep.py` が事前に済ませる:

- ゲート → `afftdn` で暗騒音そのものを消す(実測: 暗騒音 -42.4 → -63.7 dB)
- AGC → `loudnorm` で音量を揃える(実測: 4録音が -17.6〜-21.4 → 全部 -19.4 LUFS)

事前処理なら実時間の制約が無いぶん、ゲートより良い方法が使える。
`assets/birds/` はこの処理を通した後の録音である。

## 動かし方

```sh
flutter run                       # 実機を繋いで
flutter build apk --release --target-platform android-arm64
```

## ⚠ OneDrive の下でビルドするときの注意

このリポジトリは OneDrive 配下にある。同期がビルド中のファイルを掴むため、
Gradle が中間ディレクトリを消せず、こう落ちる:

```
Unable to delete directory '...\build\app\intermediates\assets\debug\mergeDebugAssets'
```

`build` の場所を Gradle 側で変えると、今度は Flutter 本体が APK を見つけられない。
そこで **`build` を OneDrive の外へのジャンクションにする**(管理者権限は不要):

```sh
rmdir /s /q build
mklink /J build "%LOCALAPPDATA%\toris_flutter_build"
```

## まだ確かめていないこと

- **群れ**(同一種を複数ずらして重ねる)と**呼応**(共起度で鳴きを誘発)
- 鳥の音源を xeno-canto から取ってくる経路。ここでは目覚まし用に選んだ
  「さえずり(song)のみ」の録音を流用している
