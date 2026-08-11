package com.toriscollection.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
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

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIF_ID, buildNotification());

        // 画面が消えていても鳴らし切るまで CPU を眠らせない。
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "toris:alarm");
            wakeLock.acquire(AUTO_STOP_MS + 30_000L);
        }

        String key = intent != null ? intent.getStringExtra(BirdAlarmReceiver.EXTRA_SOUND) : null;
        raiseAlarmStreamIfMuted();

        // 1羽目。ここから夜明けが始まる。
        MediaPlayer first = makePlayer(BirdAlarmSounds.resFor(key));
        if (first != null) {
            players.add(first);
        }
        // 2羽目・3羽目は後から加わる。
        final int[] later = BirdAlarmSounds.chorusAfter(key);
        handler.postDelayed(() -> join(later[0]), JOIN2_MS);
        handler.postDelayed(() -> join(later[1]), JOIN3_MS);

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

    private void join(int resId) {
        MediaPlayer mp = makePlayer(resId);
        if (mp != null) {
            players.add(mp);
        }
    }

    private MediaPlayer makePlayer(int resId) {
        try {
            MediaPlayer mp = MediaPlayer.create(this, resId);
            if (mp == null) {
                return null;
            }
            mp.setLooping(true);
            mp.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build());
            // 後から加わる層も、いまのカーブの音量で始める(唐突に大きく出さない)。
            float p = Math.min(1f, (float) elapsed / (float) RAMP_MS);
            float v = START_VOL + (1f - START_VOL) * p;
            mp.setVolume(v, v);
            mp.start();
            return mp;
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

        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, flags);

        Notification.Builder b = (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return b.setContentTitle("Good morning")
                .setContentText("The garden is waking up. Tap to stop.")
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    @Override
    public void onDestroy() {
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
