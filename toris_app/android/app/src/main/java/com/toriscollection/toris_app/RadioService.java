package com.toriscollection.toris_app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.os.IBinder;

/**
 * ラジオを鳴らしている間だけ立てる、音を持たないフォアグラウンドサービス。
 *
 * ## なぜ要るか
 * 睡眠に使うには**画面を消したまま鳴り続ける**必要がある。ところが画面が消えて
 * アプリが背面に回ると、OS は「バックグラウンド再生」とみなして音を止める/絞る
 * (2026-08-13 に目覚ましで実際に `AudioHardening ... would be muted` を見た)。
 * フォアグラウンドサービスを立てておけば、再生は前面扱いのまま続く。
 *
 * ## 音は鳴らさない
 * 実際に音を出すのは Flutter 側(SoLoud)。このサービスは**居るだけ**で、
 * プロセスを生かし、再生を前面扱いにし、止めるための通知を出す。
 * 音を二重に持つと止め忘れの温床になるので、鳴らす役はひとつに保つ。
 */
public class RadioService extends Service {

    public static final String ACTION_STOP = "com.toriscollection.toris_app.RADIO_STOP";

    /** 通知から「止める」が押されたか。Flutter 側が見て音を止める。 */
    public static volatile boolean STOP_REQUESTED = false;
    /** サービスが立っているか。 */
    public static volatile boolean RUNNING = false;

    private static final String CHANNEL_ID = "toris_radio";
    private static final int NOTIF_ID = 4712;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            // 音を止めるのは Flutter 側。ここは合図を置いて自分を畳むだけ。
            STOP_REQUESTED = true;
            stopSelf();
            return START_NOT_STICKY;
        }
        STOP_REQUESTED = false;
        RUNNING = true;
        startForeground(NOTIF_ID, buildNotification());
        return START_STICKY;
    }

    private Notification buildNotification() {
        NotificationManager nm =
                (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && nm != null) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, "Garden radio", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Keeps the garden playing while the screen is off.");
            ch.setSound(null, null);
            nm.createNotificationChannel(ch);
        }

        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        Intent stop = new Intent(this, RadioService.class).setAction(ACTION_STOP);
        PendingIntent piStop = PendingIntent.getService(this, 1, stop, flags);
        Intent open = new Intent(this, MainActivity.class)
                .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent piOpen = PendingIntent.getActivity(this, 2, open, flags);

        Notification.Builder b = (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        b.setContentTitle("The garden is playing")
                .setContentText("Tap to open. The birds keep singing with the screen off.")
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(piOpen)
                .setOngoing(true);
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
        RUNNING = false;
        super.onDestroy();
    }
}
