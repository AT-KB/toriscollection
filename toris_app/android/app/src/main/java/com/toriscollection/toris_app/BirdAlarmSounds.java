package com.toriscollection.toris_app;

/**
 * 目覚ましに使える鳴き声(APK 同梱)の対応表。
 *
 * ## ここに入れてよい音の条件は2つある
 *
 * **(1) 商用利用できること（CC0 / CC BY / CC BY-SA）。**
 * アプリ内のラジオが使っている xeno-canto のキャッシュは NC(非商用)が大半で、
 * 広告つきアプリには載せられない。ここに置く音源は
 * `landing/media/radio_src/`(= 配布可プール)から取り、録音者のクレジットは
 * `all_credit.json` にある。
 *
 * **(2) 「さえずり(song)」であること。「地鳴き・警戒声(call)」は入れない。**
 * McFarlane ら(2020, PLoS One / Clocks & Sleep)は、耳障りな音で起きると
 * 睡眠慣性(朝のぼんやり)が強まり、**メロディのある音だけ**が注意の脱落を
 * 有意に減らしたと報告している。
 * 例えばアオカケス(Blue Jay)の call は「ジェー！」という叫びで、研究が名指しで
 * 避けるべきとしている harsh な音そのもの。**当初同梱したが外した。**
 * ラジオ側では引き続き使う(あちらは目覚ましではないため)。
 *
 * 詳細は `docs/team/proposals/2026-08-11_目覚まし設計_研究に基づく仕様.md`。
 */
public final class BirdAlarmSounds {

    private BirdAlarmSounds() {
    }

    /**
     * **夜明けのコーラス。加わる順そのもの。**
     *
     * 2026-08-18、CEO「そもそも最初に起こす鳥を選ぶ必要はない」により
     * **選択をやめた**。ここが唯一の並びで、1羽目→2羽目→3羽目に対応する。
     * 3羽なのは設計書の決定(研究3「活動的な情景ほど回復効果が高い」)。
     *
     * ⚠️ **順序を入れ替えない。** 音の役割で並んでいる
     * (澄んだ口笛で開幕 → 朝の代表 → 短く明るいフレーズ)。
     *
     * ⚠️ Carolina Wren は CC BY-NC-ND のため**外した**。選択をやめたことで
     * 誰も鳴らせなくなり、同梱する理由も無くなった(mp3 も削除)。
     */
    private static final String[] KEYS = {
            "northern_cardinal",   // 澄んだ口笛。開幕に向く
            "american_robin",      // 朝の代表。ゆるやかな節回し
            "song_sparrow",        // 短く明るいフレーズ
    };

    /** 鳴く順に並んだ3羽。画面はこれを並べて、鳴いた鳥から光らせる。 */
    public static String[] chorusKeys() {
        return KEYS.clone();
    }

    public static int resFor(String key) {
        if (key == null) {
            return R.raw.alarm_northern_cardinal;
        }
        switch (key) {
            case "american_robin":
                return R.raw.alarm_american_robin;
            case "song_sparrow":
                return R.raw.alarm_song_sparrow;
            case "northern_cardinal":
            default:
                return R.raw.alarm_northern_cardinal;
        }
    }
}
