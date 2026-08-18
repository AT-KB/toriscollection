# 素材の撮り方(TikTok バッチ2 / Launch CM 共通)

`build_showcase.py`素材の置き場は (中身は git 管理外)。**ここに置くものは全部、実機の実画面。**
合成イメージは作らない(交渉不能の原則4)。

## 置く前に必ずやること

**上端(ステータスバー + DEBUG の帯)を落とす。**
- 録画(.mp4) → `build_showcase.py` が自動で落とす(`STATUS = 64`)
- 静止画(.png) → **置く前に自分で切る**。切り忘れると DEBUG が宣伝物に映る

```sh
py -3 -c "from PIL import Image; p='tools/video_build/_showcase_src/X.png'; \
im=Image.open(p); w,h=im.size; im.crop((0,96,w,h)).save(p)"
```

## 撮り方の型

```sh
export PATH=\"$PATH:/c/Users/kubok/AppData/Local/Android/Sdk/platform-tools\"
export MSYS_NO_PATHCONV=1          # Git Bash が /sdcard を変換してしまうため
P=com.toriscollection.toris_app

adb shell am force-stop $P
adb shell am start -n $P/.MainActivity >/dev/null; sleep 11   # 起動を待つ
# ↓ 録画を裏で回してから操作する
( adb shell screenrecord --size 720x1600 --bit-rate 6000000 --time-limit 14 /sdcard/x.mp4 & )
sleep 1
#   …ここで adb shell input tap を並べる…
sleep 7                                   # 録画が終わるまで待つ(切ると 0KB になる)
adb pull /sdcard/x.mp4 tools/video_build/_showcase_src/x.mp4
```

⚠️ **`screenrecord` が終わる前に `pull` すると 0KB のファイルが取れる。**
一度これで撮り直しになった。`--time-limit` ぶん待つこと。

## タブの座標(1080x2424 の実機)

| | Radio | Garden | Guide | Network | Wake |
|---|---|---|---|---|---|
| x | 108 | 322 | 540 | 754 | 968 |

y は **2230**。起動直後は間に合わないので `sleep 11` を置く。

## バッチ2で要る素材

| ファイル | 中身 | 撮り方の要点 |
|---|---|---|
| `wake.mp4` | 目覚ましが鳴る | Wake タブ → 数分後にセット → **実際に鳴らす**。静かに始まって声が増えるのが売り |
| `sleep.mp4` | スリープで沈む | Radio → Listen → Sleep 15 min。**暗くなるだけの絵は「止まって見える」**ので、環境音の点や光の動きを残す |
| `ritual.mp4` | 儀式で鳥が手前へ | Garden → Listen closely。**庭に鳥が居ないと撮れない**(到来は実時間経過後) |

## すでに撮ってあるもの

`plant.png` / `arrive.png` / `garden.mp4` / `guide.mp4` / `radio.mp4`
(この5つで `showcase.mp4` と `s04` / `s05` を作っている)

## 音

映像に音は入れない(`screenrecord` は音を録らない)。
音は `landing/media/radio_src/` の**配布可(CC0/BY/BY-SA)**の録音だけを後から重ねる。
アプリ同梱の音源には NC(非商用)が混ざっているので**使わない**。
録音者のクレジットは `all_credit.json` から自動で組まれる。
