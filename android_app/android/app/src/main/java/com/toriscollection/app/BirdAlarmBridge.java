package com.toriscollection.app;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.webkit.JavascriptInterface;

import java.util.Calendar;

/**
 * Web(Streamlit)側から目覚ましを設定するための橋渡し。
 *
 * 既存の `AndroidWatchdog`(MainActivity 内)と同じ JavascriptInterface 方式。
 * Web 版(通常のブラウザ)では `window.AndroidAlarm` 自体が存在しないため、
 * Web 側は try/catch で素通りする(既存の設計を踏襲)。
 *
 * なぜ Capacitor プラグインにしないか: 目覚ましに必要なのは
 * 「時刻を渡す」「取り消す」「今の設定を返す」の3つだけで、
 * プラグインの仕組みを1つ増やすより、既に使っている JavascriptInterface に
 * 揃える方が読む人が追いやすいため(MVP)。
 */
public class BirdAlarmBridge {

    private static final String PREFS = "toris_alarm";
    private static final String K_ENABLED = "enabled";
    private static final String K_HOUR = "hour";
    private static final String K_MIN = "min";
    private static final String K_SOUND = "sound";
    private static final int REQUEST_CODE = 8101;

    private final Activity activity;

    public BirdAlarmBridge(Activity activity) {
        this.activity = activity;
    }

    /**
     * 目覚ましを設定する。
     *
     * @return 実際に設定できたら true。Android 12+ で「正確なアラーム」の許可が
     *         下りていない場合は false を返し、Web 側が案内を出せるようにする。
     */
    @JavascriptInterface
    public boolean setAlarm(int hour, int minute, String sound) {
        AlarmManager am = (AlarmManager) activity.getSystemService(Context.ALARM_SERVICE);
        if (am == null) {
            return false;
        }
        if (!canScheduleExact(am)) {
            return false;
        }

        Calendar next = Calendar.getInstance();
        next.set(Calendar.HOUR_OF_DAY, hour);
        next.set(Calendar.MINUTE, minute);
        next.set(Calendar.SECOND, 0);
        next.set(Calendar.MILLISECOND, 0);
        // 指定時刻が既に過ぎていれば翌日。
        if (next.getTimeInMillis() <= System.currentTimeMillis()) {
            next.add(Calendar.DAY_OF_YEAR, 1);
        }

        try {
            // Doze(省電力)に入っていても発火させる。通常の set() だと
            // 朝まで端末が眠っている間にまとめられ、時刻がずれる。
            am.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP, next.getTimeInMillis(), pendingIntent(sound));
        } catch (SecurityException e) {
            return false;
        }

        SharedPreferences.Editor ed = prefs().edit();
        ed.putBoolean(K_ENABLED, true).putInt(K_HOUR, hour)
          .putInt(K_MIN, minute).putString(K_SOUND, sound).apply();
        return true;
    }

    @JavascriptInterface
    public void cancelAlarm() {
        AlarmManager am = (AlarmManager) activity.getSystemService(Context.ALARM_SERVICE);
        if (am != null) {
            am.cancel(pendingIntent(prefs().getString(K_SOUND, null)));
        }
        prefs().edit().putBoolean(K_ENABLED, false).apply();
    }

    /** 現在の設定を JSON 文字列で返す(Web 側が画面に出すため)。 */
    @JavascriptInterface
    public String getAlarm() {
        SharedPreferences p = prefs();
        return "{\"enabled\":" + p.getBoolean(K_ENABLED, false)
                + ",\"hour\":" + p.getInt(K_HOUR, 7)
                + ",\"minute\":" + p.getInt(K_MIN, 0)
                + ",\"sound\":\"" + p.getString(K_SOUND, "northern_cardinal") + "\"}";
    }

    /** 「正確なアラーム」の許可設定画面を開く(Android 12+ で拒否されている場合)。 */
    @JavascriptInterface
    public void openExactAlarmSettings() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            Intent i = new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM);
            i.setData(Uri.parse("package:" + activity.getPackageName()));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            try {
                activity.startActivity(i);
            } catch (Exception ignored) {
            }
        }
    }

    private boolean canScheduleExact(AlarmManager am) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return am.canScheduleExactAlarms();
        }
        return true;
    }

    private PendingIntent pendingIntent(String sound) {
        Intent i = new Intent(activity, BirdAlarmReceiver.class);
        i.setAction(BirdAlarmReceiver.ACTION_FIRE);
        i.putExtra(BirdAlarmReceiver.EXTRA_SOUND, sound);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        return PendingIntent.getBroadcast(activity, REQUEST_CODE, i, flags);
    }

    private SharedPreferences prefs() {
        return activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
