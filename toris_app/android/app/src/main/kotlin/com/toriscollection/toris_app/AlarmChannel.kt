package com.toriscollection.toris_app

import android.app.Activity
import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.util.Calendar

/**
 * 目覚ましの設定を Flutter 側から呼ぶための窓口。
 *
 * Capacitor 版の `BirdAlarmBridge`(@JavascriptInterface)を置き換えたもの。
 * **やることは同じ**で、入口が WebView の JavaScript から MethodChannel に
 * 変わっただけ。鳴らす本体(BirdAlarmService / BirdAlarmSounds /
 * BirdAlarmReceiver)は Capacitor に依存していなかったので、そのまま移してある。
 *
 * 設計上の要点(Capacitor 版から引き継ぐ):
 *  - **サーバーに一切依存しない。** 音は APK 同梱。朝いちばんに Render の
 *    コールドスタート(実測22.7秒)を待つわけにはいかない。
 *  - Doze(省電力)に入っていても鳴らすため `setExactAndAllowWhileIdle` を使う。
 *    通常の `set()` だと端末が眠っている間にまとめられ、時刻がずれる。
 *  - Android 12+ で「正確なアラーム」が未許可なら `false` を返し、
 *    呼び出し側が設定画面へ案内できるようにする。
 */
class AlarmChannel(private val activity: Activity) {

    companion object {
        const val CHANNEL = "toris/alarm"
        private const val PREFS = "toris_alarm"
        private const val K_ENABLED = "enabled"
        private const val K_HOUR = "hour"
        private const val K_MIN = "min"
        private const val K_SOUND = "sound"
        private const val REQUEST_CODE = 8101
    }

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "set" -> {
                val hour = call.argument<Int>("hour") ?: 7
                val minute = call.argument<Int>("minute") ?: 0
                val sound = call.argument<String>("sound")
                result.success(setAlarm(hour, minute, sound))
            }
            "cancel" -> {
                cancelAlarm()
                result.success(true)
            }
            "get" -> result.success(getAlarm())
            "canScheduleExact" -> result.success(canScheduleExact())
            "openExactAlarmSettings" -> {
                openExactAlarmSettings()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    /** @return 実際に設定できたら true。正確なアラームが未許可なら false。 */
    private fun setAlarm(hour: Int, minute: Int, sound: String?): Boolean {
        val am = activity.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
            ?: return false
        if (!canScheduleExact()) return false

        val next = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            // 指定時刻が既に過ぎていれば翌日。
            if (timeInMillis <= System.currentTimeMillis()) add(Calendar.DAY_OF_YEAR, 1)
        }

        try {
            am.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP, next.timeInMillis, pendingIntent(sound)
            )
        } catch (e: SecurityException) {
            return false
        }

        prefs().edit()
            .putBoolean(K_ENABLED, true)
            .putInt(K_HOUR, hour)
            .putInt(K_MIN, minute)
            .putString(K_SOUND, sound)
            .apply()
        return true
    }

    private fun cancelAlarm() {
        val am = activity.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
        am?.cancel(pendingIntent(prefs().getString(K_SOUND, null)))
        prefs().edit().putBoolean(K_ENABLED, false).apply()
    }

    /** 現在の設定。画面に出すために返す。 */
    private fun getAlarm(): Map<String, Any?> {
        val p = prefs()
        return mapOf(
            "enabled" to p.getBoolean(K_ENABLED, false),
            "hour" to p.getInt(K_HOUR, 7),
            "minute" to p.getInt(K_MIN, 0),
            "sound" to p.getString(K_SOUND, "northern_cardinal"),
        )
    }

    private fun canScheduleExact(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        val am = activity.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
        return am?.canScheduleExactAlarms() ?: false
    }

    /** 「正確なアラーム」の許可設定画面を開く(Android 12+ で拒否されている場合)。 */
    private fun openExactAlarmSettings() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return
        val i = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
            data = Uri.parse("package:${activity.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            activity.startActivity(i)
        } catch (_: Exception) {
        }
    }

    private fun pendingIntent(sound: String?): PendingIntent {
        val i = Intent(activity, BirdAlarmReceiver::class.java).apply {
            action = BirdAlarmReceiver.ACTION_FIRE
            putExtra(BirdAlarmReceiver.EXTRA_SOUND, sound)
        }
        var flags = PendingIntent.FLAG_UPDATE_CURRENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags = flags or PendingIntent.FLAG_IMMUTABLE
        }
        return PendingIntent.getBroadcast(activity, REQUEST_CODE, i, flags)
    }

    private fun prefs() = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
