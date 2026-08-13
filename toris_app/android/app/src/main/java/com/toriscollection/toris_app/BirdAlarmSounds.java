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

    /** さえずりのみ。順序はそのまま「夜明けのコーラス」で加わる順になる。 */
    private static final String[] KEYS = {
            "northern_cardinal",   // 澄んだ口笛。開幕に向く
            "american_robin",      // 朝の代表。ゆるやかな節回し
            "song_sparrow",        // 短く明るいフレーズ
            "carolina_wren",       // よく通る。最後に加わる層向き
    };

    public static int resFor(String key) {
        if (key == null) {
            return R.raw.alarm_northern_cardinal;
        }
        switch (key) {
            case "american_robin":
                return R.raw.alarm_american_robin;
            case "song_sparrow":
                return R.raw.alarm_song_sparrow;
            case "carolina_wren":
                return R.raw.alarm_carolina_wren;
            case "northern_cardinal":
            default:
                return R.raw.alarm_northern_cardinal;
        }
    }

    public static String[] keys() {
        return KEYS.clone();
    }

    /**
     * 夜明けのコーラスで、指定の鳥に「後から加わる」2種を返す。
     *
     * 本物の dawn chorus と同じく、1種から始まって少しずつ増える。
     * Ratcliffe ら(2013)は、回復効果が高いと評価された鳥の声は
     * 「活動的な情景」と結びついていたと報告しており、単独で鳴らし続けるより
     * 複数種が加わる方がその情景に近い。
     */
    public static int[] chorusAfter(String firstKey) {
        String first = firstKey == null ? "northern_cardinal" : firstKey;
        int[] out = new int[2];
        int n = 0;
        for (String k : KEYS) {
            if (!k.equals(first) && n < 2) {
                out[n++] = resFor(k);
            }
        }
        return out;
    }
}
