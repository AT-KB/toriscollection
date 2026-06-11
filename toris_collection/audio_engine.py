"""
audio_engine.py - ritual.py と radio.py が共有する Web Audio JS 部品

両ファイルは Web Audio API で鳥の声を鳴らす。そのうち「純粋なJS関数」で
かつ Python の値を埋め込まない共通部分(リバーブIR合成・ノイズ生成・
HRTFパンナー・鳴き方バリエーション選択・AGC/呼応/ゲートの定数)を
ここに集約し、2ファイル間のコピー&ペースト重複と数値ドリフトを防ぐ。

【使い方】
  各定数は「Python f-string にそのまま埋め込める生のJS文字列」。
  呼び出し側は波括弧のエスケープ不要で、次のように差し込むだけ:

      import audio_engine as ae
      html = f'''
        <script>(function() {{
          {ae.AUDIO_CONSTANTS_JS}
          {ae.MAKE_PANNER_JS}
          {ae.MAKE_REVERB_IR_JS}
          {ae.MAKE_NOISE_BUFFER_JS}
          {ae.PICK_VARIANT_JS}
          ...呼び出し側固有のコード...
        }})();</script>
      '''

【前提となるスコープ変数】
  - ctx        : AudioContext(各関数が参照)
  - BIRDS      : 鳥メタ配列(pickVariant が vt を参照)
  - preferredType() : 時間帯に応じた鳴き方の好みを返す関数
                      (ritual は new Date()、radio は SIM_HOUR で実装が異なるため
                       共有せず各ファイルで定義する)
"""
from __future__ import annotations

# ── 音響パラメータ定数 ──────────────────────────────────────────────
# AGC(自動音量正規化)・ノイズゲート・呼応(かけあい)・HRTF奥行きの共通値。
# 片方のファイルだけ数値を変えてしまう事故を防ぐため一元管理する。
AUDIO_CONSTANTS_JS = """
        // ── 音響パラメータ(audio_engine.py で一元管理) ──
        // AGC: 録音ごとの音量差を吸収する自動音量正規化の目標値とクランプ範囲
        const AGC_TARGET = 0.065, AGC_MIN = 0.5, AGC_MAX = 3.5;
        // 呼応: バックグラウンド鳥の最小ゲイン / 休符判定フレーム数 / 最低ソロ時間
        const CALL_FLOOR = 0.12;
        const SILENT_NEED = 12;
        const MIN_SOLO_MS = 5000;
        // ノイズゲート: 休符中のヒスを絞る閾値と床値
        const GATE_THRESH = 0.020, GATE_FLOOR = 0.12;
        // HRTF: 枝の奥行き(z座標)。手前ほど 0 に近い。
        const DEPTH_Z = { b3: -7, b2: -3.5, b1: -1.2 };
"""

# ── HRTF パンナー ──────────────────────────────────────────────────
# 鳥の左右(x)・奥行き(z)を頭部伝達関数で定位する。
# 構築に失敗する古い環境では左右だけの StereoPanner にフォールバックする。
# 距離減衰は呼び出し側の D[branch].gain に任せるため rolloffFactor は 0。
MAKE_PANNER_JS = """
        function makePanner() {
            try {
                const p = new PannerNode(ctx, {
                    panningModel: 'HRTF', distanceModel: 'linear',
                    refDistance: 1, maxDistance: 30, rolloffFactor: 0
                });
                return { node: p, hrtf: true };
            } catch (e) {
                return { node: ctx.createStereoPanner(), hrtf: false };
            }
        }
"""

# ── 森の残響インパルス応答 ──────────────────────────────────────────
# 減衰ノイズに初期反射を数発混ぜた短め(1.6秒)の IR。
# 鳴き声を濁らせず奥行きだけを足す。全鳥で1つの ConvolverNode を共有する。
MAKE_REVERB_IR_JS = """
        function makeReverbIR() {
            const dur = 1.6, len = Math.floor(ctx.sampleRate * dur);
            const ir = ctx.createBuffer(2, len, ctx.sampleRate);
            for (let ch = 0; ch < 2; ch++) {
                const d = ir.getChannelData(ch);
                for (let k = 0; k < len; k++) {
                    // 指数減衰する乱反射(後半ほど静かに)
                    const decay = Math.pow(1 - k / len, 2.6);
                    d[k] = (Math.random() * 2 - 1) * decay;
                }
                // 葉や枝による初期反射を数発足す(森らしい粒立ち)
                [0.013, 0.029, 0.051, 0.078].forEach(function(tt, idx) {
                    const p = Math.floor(tt * ctx.sampleRate);
                    if (p < len) d[p] += (0.5 - idx * 0.1) * (ch === 0 ? 1 : 0.8);
                });
            }
            return ir;
        }
"""

# ── 環境音フォールバック用ノイズバッファ ────────────────────────────
# Freesound の実録音が無いときの合成環境音に使う。
# brown=true でブラウンノイズ(低い風)、false でホワイトノイズ(空気のざわめき)。
MAKE_NOISE_BUFFER_JS = """
        function makeNoiseBuffer(brown) {
            const dur = 4, len = ctx.sampleRate * dur;
            const buffer = ctx.createBuffer(1, len, ctx.sampleRate);
            const data = buffer.getChannelData(0);
            let last = 0;
            for (let i = 0; i < len; i++) {
                const white = Math.random() * 2 - 1;
                if (brown) { last = (last + 0.02 * white) / 1.02; data[i] = last * 3.2; }
                else { data[i] = white; }
            }
            return buffer;
        }
"""

# ── 鳴き方バリエーションの選択 ──────────────────────────────────────
# 同一種の複数録音(さえずり/地鳴き)から1本を選ぶ。
# preferredType() が返す時間帯の好みに一致する録音を重み3倍で引きやすくする。
# 注: preferredType() は呼び出し側で定義する(ritual=実時刻 / radio=SIM_HOUR)。
PICK_VARIANT_JS = """
        function pickVariant(i, exclude) {
            const vt = BIRDS[i].vt || [];
            const pref = preferredType();
            const pool = [];
            for (let v = 0; v < vt.length; v++) {
                if (v === exclude) continue;
                const w = (pref && vt[v] === pref) ? 3 : 1;  // 好みは重み3倍
                for (let k = 0; k < w; k++) pool.push(v);
            }
            if (!pool.length) return exclude >= 0 ? exclude : 0;
            return pool[Math.floor(Math.random() * pool.length)];
        }
"""
