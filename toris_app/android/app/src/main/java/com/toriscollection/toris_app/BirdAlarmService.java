package com.toriscollection.toris_app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;

import java.util.ArrayList;
import java.util.List;

/**
 * 鳥のさえずりで起こすフォアグラウンドサービス。
 *
 * ## 設計の根拠(要約)
 * 詳細は `docs/team/proposals/2026-08-11_目覚まし設計_研究に基づく仕様.md`。
 *
 * 1. **耳障りな音は使わない**(McFarlane ら 2020)。鳴らすのはさえずりのみ。
 *    音量が上がっても**音の質は変えない**。上げるのは音量と密度だけ。
 * 2. **ゆっくり立ち上げる**(dawn simulation の臨床知見)。当初 45 秒だったが、
 *    研究の時間感覚に合わせて **5分** かけて最大に達するようにした。
 *    開始音量は「聞こえるか聞こえないか」(8%)。
 * 3. **1羽 → 2羽 → 3羽 と加わる**(Ratcliffe ら 2013: 回復効果が高い鳥の声は
 *    「活動的な情景」と結びついていた)。本物の dawn chorus と同じ立ち上がり方。
 *
 * ## 寝過ごし対策
 * 競合(Dawn Chorus)は「1分で勝手にスヌーズして止まる」と評価を落としている。
 * 本実装は**最大音量に達したあと、止めるまで鳴り続ける**。ただし耳障りな音へは
 * 切り替えない(研究1に反するため)。電池のため AUTO_STOP_MS で最終的に止める。
 */
public class BirdAlarmService extends Service {

    private static final String CHANNEL_ID = "toris_alarm";
    private static final int NOTIF_ID = 4711;

    /** 最大音量に達するまで。dawn simulation の時間感覚に合わせる。 */
    private static final long RAMP_MS = 5 * 60_000L;
    private static final long STEP_MS = 1_000L;
    /** 2羽目・3羽目が加わる時刻(ランプ全体の 1/3, 2/3)。 */
    private static final long JOIN2_MS = RAMP_MS / 3;
    private static final long JOIN3_MS = RAMP_MS * 2 / 3;
    /** 開始音量。覚醒閾値の下から始める。 */
    private static final float START_VOL = 0.08f;
    /** 鳴らしっぱなしで電池を焼かないための上限。 */
    private static final long AUTO_STOP_MS = 15 * 60_000L;

    private final List<MediaPlayer> players = new ArrayList<>();
    private PowerManager.WakeLock wakeLock;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long elapsed = 0L;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    /** 「止める」を受け取るための action。通知のボタンと本文タップの両方から来る。 */
    public static final String ACTION_STOP = "com.toriscollection.toris_app.ALARM_STOP";

    /** いま鳴っているか。画面に「止める」を出すために Flutter 側から見る。 */
    public static volatile boolean RINGING = false;

    /**
     * **いま鳴っている鳥**(鳴き始めた順)。画面がこれを読んで名前を光らせる。
     *
     * 実際に `MediaPlayer` を足したところでしか書かない。予定を先に書くと、
     * まだ鳴いていない鳥の名前が光ってしまう(原則4「生態に誠実」)。
     */
    public static volatile java.util.List<String> SINGING =
            java.util.Collections.emptyList();

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        // 2026-08-13 実機で発覚: 止める手段が実質無く、CEO が端末を再起動する羽目に
        // なった。通知には "Tap to stop" と書いてあるのに、タップしてもアプリが
        // 開くだけで**鳴り止まなかった**(contentIntent が MainActivity を指していた)。
        // 目覚ましで「止められない」は最悪の壊れ方なので、止める道を3つ用意する:
        //   1. 通知の「Stop」ボタン   2. 通知の本文タップ   3. アプリ内のボタン
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }

        RINGING = true;
        startForeground(NOTIF_ID, buildNotification());

        // 画面が消えていても鳴らし切るまで CPU を眠らせない。
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "toris:alarm");
            wakeLock.acquire(AUTO_STOP_MS + 30_000L);
        }

        raiseAlarmStreamIfMuted();

        // 1羽目は選んだ鳥。2羽目・3羽目は**出会った鳥から**その朝ごとに選ぶ
        // (CEO 2026-08-19)。出会いが足りなければ既定の並びから埋める。
        String firstKey = intent != null
                ? intent.getStringExtra(BirdAlarmReceiver.EXTRA_FIRST) : null;
        String met = intent != null
                ? intent.getStringExtra(BirdAlarmReceiver.EXTRA_MET) : null;
        final String[] chorus =
                BirdAlarmSounds.chorusFor(firstKey, met, new java.util.Random());

        // 1羽目。ここから夜明けが始まる。
        MediaPlayer first = makePlayer(chorus[0]);
        if (first != null) {
            players.add(first);
        }
        SINGING = first == null
                ? java.util.Collections.emptyList()
                : java.util.Collections.singletonList(chorus[0]);
        // 2羽目・3羽目は後から加わる。
        handler.postDelayed(() -> join(chorus[1]), JOIN2_MS);
        handler.postDelayed(() -> join(chorus[2]), JOIN3_MS);

        tick();
        handler.postDelayed(this::stopSelf, AUTO_STOP_MS);
        return START_NOT_STICKY;
    }

    /** 音量カーブ: START_VOL から 1.0 へ。上げ切ったらそのまま鳴らし続ける。 */
    private void tick() {
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                elapsed += STEP_MS;
                float p = Math.min(1f, (float) elapsed / (float) RAMP_MS);
                float v = START_VOL + (1f - START_VOL) * p;
                for (MediaPlayer mp : players) {
                    try {
                        mp.setVolume(v, v);
                    } catch (Exception ignored) {
                    }
                }
                handler.postDelayed(this, STEP_MS);
            }
        }, STEP_MS);
    }

    private void join(String key) {
        MediaPlayer mp = makePlayer(key);
        if (mp != null) {
            // **鳴り出したときだけ**名簿に足す。
            java.util.List<String> next = new java.util.ArrayList<>(SINGING);
            next.add(key);
            SINGING = java.util.Collections.unmodifiableList(next);
            players.add(mp);
        }
    }

    /**
     * 鳴らす。**Flutter の assets から直に読む。**
     *
     * ## なぜ res/raw をやめたか(2026-08-19 CEO「なんでmp3は3個しかないの」)
     * ネイティブが `res/raw` しか見ていなかったので、そこに置いた3本しか
     * 鳴らせなかった。鳴き声そのものは `assets/birds/` に36種あるのに、
     * **同じ音をもう一度 res/raw にコピーしないと使えない**作りだった。
     * AssetManager なら Flutter の assets をそのまま開けるので、複製も要らず
     * (APKが数MB太らない)、種を増やすのに手作業も要らない。
     *
     * ⚠️ **音の用途(USAGE_ALARM)は prepare より前に渡す。**
     * 2026-08-13 実機(Android 16)で、後から属性を変えても効かず、アラームが
     * 「メディア」扱いで**全ミュート**された。`MediaPlayer.create()` は生成と
     * 同時に prepare まで済ませるのが原因だったので、ここでは自分で組み立てて
     * setAudioAttributes → setDataSource → prepare の順を守る。
     *
     * ⚠️ **読めなかったら既定の音に落ちる。** 目覚ましが無音で鳴るのが
     * いちばん悪い壊れ方なので、res/raw の1本だけは残してある。
     */
    private MediaPlayer makePlayer(String key) {
        MediaPlayer mp = fromAsset(BirdAlarmSounds.assetFor(key));
        if (mp == null) {
            mp = fromRawFallback();
        }
        if (mp == null) {
            return null;
        }
        mp.setLooping(true);
        // 後から加わる層も、いまのカーブの音量で始める(唐突に大きく出さない)。
        float p = Math.min(1f, (float) elapsed / (float) RAMP_MS);
        float v = START_VOL + (1f - START_VOL) * p;
        mp.setVolume(v, v);
        mp.start();
        return mp;
    }

    private AudioAttributes alarmAttrs() {
        return new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build();
    }

    private MediaPlayer fromAsset(String path) {
        android.content.res.AssetFileDescriptor afd = null;
        try {
            afd = getAssets().openFd(path);
            MediaPlayer mp = new MediaPlayer();
            mp.setAudioAttributes(alarmAttrs());   // prepare より前
            mp.setDataSource(afd.getFileDescriptor(), afd.getStartOffset(),
                    afd.getLength());
            mp.prepare();
            return mp;
        } catch (Exception e) {
            return null;
        } finally {
            if (afd != null) {
                try {
                    afd.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    /** 最後の砦。assets が読めなくても、何かは鳴らす。 */
    private MediaPlayer fromRawFallback() {
        try {
            AudioManager am = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
            int session = am != null ? am.generateAudioSessionId() : 0;
            return MediaPlayer.create(this, R.raw.alarm_northern_cardinal,
                    alarmAttrs(), session);
        } catch (Exception e) {
            return null;
        }
    }

    /** 端末のアラーム音量が絞られていると何も聞こえないので、低すぎる時だけ持ち上げる。 */
    private void raiseAlarmStreamIfMuted() {
        try {
            AudioManager am = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
            if (am == null) {
                return;
            }
            int max = am.getStreamMaxVolume(AudioManager.STREAM_ALARM);
            int cur = am.getStreamVolume(AudioManager.STREAM_ALARM);
            if (cur < max / 3) {
                am.setStreamVolume(AudioManager.STREAM_ALARM, max / 2, 0);
            }
        } catch (Exception ignored) {
        }
    }

    private Notification buildNotification() {
        NotificationManager nm =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && nm != null) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "Morning birds", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("Wakes you with the birds you have met.");
            ch.setSound(null, null);   // 音はサービス側で鳴らすので通知音は鳴らさない
            nm.createNotificationChannel(ch);
        }

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        // 本文をタップしても**止まる**ようにする。文言どおりに動くのが最優先。
        Intent stop = new Intent(this, BirdAlarmService.class).setAction(ACTION_STOP);
        PendingIntent piStop = PendingIntent.getService(this, 1, stop, flags);

        Notification.Builder b = (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        b.setContentTitle("Good morning")
                .setContentText("The garden is waking up. Tap to stop.")
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(piStop)
                .setOngoing(true);
        // ロック画面からでも押せるボタン。朝いちばんに探させない。
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            b.addAction(new Notification.Action.Builder(
                    Icon.createWithResource(this,
                            android.R.drawable.ic_menu_close_clear_cancel),
                    "Stop", piStop).build());
        }
        return b.build();
    }

    @Override
    public void onDestroy() {
        RINGING = false;
        SINGING = java.util.Collections.emptyList();
        handler.removeCallbacksAndMessages(null);
        for (MediaPlayer mp : players) {
            try {
                mp.stop();
                mp.release();
            } catch (Exception ignored) {
            }
        }
        players.clear();
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        wakeLock = null;
        super.onDestroy();
    }
}
