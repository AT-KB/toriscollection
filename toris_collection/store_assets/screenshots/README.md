# ストア用スクリーンショット

最終更新: 2026-08-08（それ以前は 2026-07-08 の4枚）。**製品版の掲載情報にはこの6枚を使う。**
Play は最大8枚まで載せられるので、2枠は空けてある。

## 並び順（この順で載せる。1枚目がいちばん効く）

| ファイル | 中身 | 狙い |
|---|---|---|
| `01_bird_detail.png` | 図鑑の詳細ドット絵（スズメ） | **最強のアセットを最初に**。絵で足を止める |
| `02_bird_profile.png` | 好きなもの / 好きな場所 / こわいもの | **本物の生態データ**という差別化。GloBI 由来 |
| `03_radio.png` | 会った鳥でできるラジオ | 3本の柱の「声」 |
| `04_garden.png` | 庭のフィールド（ドット絵の風景） | 3本の柱の「癒し」 |
| `05_plant.png` | 植える画面 | 3本の柱の「構築SIM」 |
| `06_network.png` | 生態系ネットワーク | 「遊ぶほど生態系がわかる」 |

## 撮り直しの手順（再現可能）

実機（Pixel 9a / Android 16）を USB で接続し、アプリを起動した状態で:

```bash
ADB=C:/Users/kubok/AppData/Local/Android/Sdk/platform-tools/adb.exe

# 1. WebView の DevTools ソケットに forward
SOCK=$("$ADB" shell cat /proc/net/unix | grep -o "webview_devtools_remote_[0-9]*" | head -1)
"$ADB" forward tcp:9222 localabstract:$SOCK
# ws URL は http://localhost:9222/json から onrender のものを拾う

# 2. ステータスバーを整える(時刻9:00・電池100・通知なし)
"$ADB" shell settings put global sysui_demo_allowed 1
"$ADB" shell am broadcast -a com.android.systemui.demo -e command enter
"$ADB" shell am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0900
"$ADB" shell am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false
"$ADB" shell am broadcast -a com.android.systemui.demo -e command notifications -e visible false
"$ADB" shell am broadcast -a com.android.systemui.demo -e command network -e wifi show -e level 4

# 3. CDP でタブを切り替え(ブラインドのタップは不安定なので使わない)
#    → Runtime.evaluate で「📖 Guide」等の <p> を含む祖先を click()
# 4. "$ADB" exec-out screencap -p > out.png
# 5. 上下を切る: 上 96px(ステータスバー) / 下 56px(ジェスチャーバー)
# 6. デモモードを戻す
"$ADB" shell am broadcast -a com.android.systemui.demo -e command exit
"$ADB" shell settings put global sysui_demo_allowed 0
```

## 仕様メモ

- 現行: **1080x2272**（縦横比 1:2.104）。以前の4枚は 824x1830（1:2.221）で、
  それで審査を通っているので、この比率で問題ない。
- 表示言語は **英語**（`i18n.py` の既定 `en`）。ストアの掲載情報と揃えている。
- アプリ内の緑の「Share」ボタンは画面右下に常時出る仕様なので、どの枚にも写り込む。
