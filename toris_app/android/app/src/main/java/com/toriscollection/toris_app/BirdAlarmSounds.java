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
     * 目覚ましに使える種。**さえずり(song)で、かつドット絵がある種**だけ。
     *
     * ## なぜ増やせるようになったか(2026-08-19 CEO「なんでmp3は3個しかないの」)
     * 前は `res/raw` に置いた3本しか鳴らせなかった。いまは AssetManager で
     * Flutter の assets を直に読むので、**同梱の鳴き声をそのまま使える**。
     * 音を複製しないので APK も太らない。
     *
     * ## ここに入る条件
     * (1) **さえずり(song)であること。** 地鳴き・警戒声(call)は入れない。
     *     McFarlane ら(2020)— 耳障りな音で起きると睡眠慣性が強まり、
     *     メロディのある音だけが注意の脱落を有意に減らした。
     * (2) **ドット絵があること。** 選択肢に顔が並ばないと選べない
     *     (CEO 2026-08-18「アイコンもほしい」)。
     *
     * ⚠️ 商用ライセンスは**条件から外した**(CEO 2026-08-19「商用にしないから
     * 増やせ」)。23種のうち商用可は3種だけなので、収益化する段になったら
     * ここを見直すこと。`_credits.json` の license_class に入っている。
     *
     * ⚠️ Song Sparrow は**ドット絵が無いので入っていない**。絵ができたら入る。
     *
     * 先頭2種の並びは変えないこと(既定の1羽目・2羽目)。
     */
    private static final String[] KEYS = {
            "northern_cardinal",       // Northern Cardinal
            "american_robin",          // American Robin
            "american_goldfinch",      // American Goldfinch
            "blue_jay",                // Blue Jay
            "carolina_wren",           // Carolina Wren
            "downy_woodpecker",        // Downy Woodpecker
            "eastern_bluebird",        // Eastern Bluebird
            "enaga",                   // Long-tailed Tit
            "hiyodori",                // Brown-eared Bulbul
            "kakesu",                  // Eurasian Jay
            "kawarahiwa",              // Oriental Greenfinch
            "kawasemi",                // Common Kingfisher
            "kibitaki",                // Narcissus Flycatcher
            "kogera",                  // Japanese Pygmy Woodpecker
            "mejiro",                  // Japanese White-eye
            "mourning_dove",           // Mourning Dove
            "pileated_woodpecker",     // Pileated Woodpecker
            "shijukara",               // Japanese Tit
            "suzume",                  // Eurasian Tree Sparrow
            "tsubame",                 // Barn Swallow
            "tufted_titmouse",         // Tufted Titmouse
            "uguisu",                  // Japanese Bush Warbler
            "yamagara",                // Varied Tit
    };

    /** Flutter の assets に置かれた鳴き声の場所。 */
    public static String assetFor(String key) {
        return "flutter_assets/assets/birds/" + keyOrDefault(key) + ".mp3";
    }

    /** 知らない鍵は既定の1羽目に寄せる。 */
    public static String keyOrDefault(String key) {
        for (String k : KEYS) {
            if (k.equals(key)) {
                return k;
            }
        }
        return KEYS[0];
    }

    public static String[] keys() {
        return KEYS.clone();
    }

    /**
     * 夜明けのコーラスの並びを組む。
     *
     * CEO 2026-08-19「最初の1羽とあとはランダムで3羽まで加わる。ただし
     * その加わる残り2羽は、出会った鳥であってほしい」。
     *
     * @param first   選ばれた1羽目
     * @param metCsv  **近くで出会った鳥**(儀式が成立した種)をカンマ区切りで
     * @return 鳴き始める順に3羽
     *
     * ⚠️ 出会った鳥が足りないときは、既定の並びから埋める。
     * **目覚ましは起きるための道具**なので、始めたばかりの人の朝が
     * 1羽だけの薄い音になるのは避ける(層が増えることに研究上の根拠がある)。
     */
    public static String[] chorusFor(String first, String metCsv, java.util.Random rng) {
        String head = keyOrDefault(first);
        java.util.List<String> pool = new java.util.ArrayList<>();
        if (metCsv != null) {
            for (String raw : metCsv.split(",")) {
                String k = raw.trim();
                if (k.isEmpty() || k.equals(head)) {
                    continue;
                }
                for (String known : KEYS) {   // 鳴らせる種だけ
                    if (known.equals(k) && !pool.contains(k)) {
                        pool.add(k);
                    }
                }
            }
        }
        java.util.Collections.shuffle(pool, rng);

        java.util.List<String> out = new java.util.ArrayList<>();
        out.add(head);
        for (String k : pool) {
            if (out.size() >= 3) {
                break;
            }
            out.add(k);
        }
        // 足りないぶんは既定の並びから。
        for (String k : KEYS) {
            if (out.size() >= 3) {
                break;
            }
            if (!out.contains(k)) {
                out.add(k);
            }
        }
        return out.toArray(new String[0]);
    }
}
