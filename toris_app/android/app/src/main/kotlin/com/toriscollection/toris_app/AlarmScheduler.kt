package com.toriscollection.toris_app

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import java.util.Calendar

/**
 * 目覚ましの登録を1か所にまとめたもの。
 *
 * ## なぜ分けたか(2026-11-08)
 * 前は `AlarmChannel`(画面から呼ぶ窓口)の中だけに登録の処理があった。
 * そのため次の2つの穴があった(HANDOFF_00 §7-3「目覚ましの穴」)。
 *  1. **一度鳴ったら終わり。** 翌日の分を誰も登録しない。
 *  2. **再起動で消える。** Android は再起動で AlarmManager の登録を全部捨てる。
 *
 * 説明戦略(2026-11-08)で、目覚ましを「毎朝アプリに触れる理由」にした。
 * 毎朝鳴らなければ、その戦略が成り立たない。
 * → **鳴ったら翌日の同じ時刻を登録し直す**(`BirdAlarmReceiver`)。
 *   **再起動・アプリ更新・時刻変更のあとも登録し直す**(`AlarmRestoreReceiver`)。
 */
object AlarmScheduler {
    const val PREFS = "toris_alarm"
    const val K_ENABLED = "enabled"
    const val K_HOUR = "hour"
    const val K_MIN = "min"
    const val K_FIRST = "first"
    const val K_MET = "met"

    /** 鳥の前に流れる音(ラジオの環境音のキー)。"none" なら前置きなし。既定は lake。 */
    const val K_PRELUDE = "prelude"
    const val PRELUDE_DEFAULT = "lake"
    private val PRELUDES = setOf("rain", "wind", "stream", "waves", "lake", "fire", "drips", "none")

    @JvmStatic
    fun prelude(ctx: Context): String {
        val v = prefs(ctx).getString(K_PRELUDE, PRELUDE_DEFAULT) ?: PRELUDE_DEFAULT
        return if (v in PRELUDES) v else PRELUDE_DEFAULT
    }

    /** 前置きの音を変える。**登録し直さなくても次の朝から効く**(鳴らすときに読む)。 */
    @JvmStatic
    fun setPrelude(ctx: Context, key: String) {
        if (key in PRELUDES) prefs(ctx).edit().putString(K_PRELUDE, key).apply()
    }
    private const val REQUEST_CODE = 8101

    private fun prefs(ctx: Context) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** 正確なアラームを登録できるか(Android 12+ は許可が要る)。 */
    @JvmStatic
    fun canScheduleExact(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
        return am?.canScheduleExactAlarms() ?: false
    }

    /** 画面から設定する。設定を保存してから登録する。登録できたら true。 */
    @JvmStatic
    fun set(ctx: Context, hour: Int, minute: Int, first: String?, met: String?): Boolean {
        if (!canScheduleExact(ctx)) return false
        prefs(ctx).edit()
            .putBoolean(K_ENABLED, true)
            .putInt(K_HOUR, hour)
            .putInt(K_MIN, minute)
            .putString(K_FIRST, first)
            .putString(K_MET, met)
            .apply()
        return scheduleNext(ctx)
    }

    /**
     * 保存してある設定で、**次に来るその時刻**を登録する。
     * 鳴ったあと・再起動のあとに呼ぶ。オフなら何もしない。
     */
    @JvmStatic
    fun scheduleNext(ctx: Context): Boolean {
        val p = prefs(ctx)
        if (!p.getBoolean(K_ENABLED, false)) return false
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
            ?: return false
        if (!canScheduleExact(ctx)) return false

        val next = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, p.getInt(K_HOUR, 7))
            set(Calendar.MINUTE, p.getInt(K_MIN, 0))
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            // 指定時刻が既に過ぎていれば翌日。鳴った直後に呼ぶと必ず翌日になる。
            if (timeInMillis <= System.currentTimeMillis()) add(Calendar.DAY_OF_YEAR, 1)
        }
        return try {
            am.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                next.timeInMillis,
                pendingIntent(ctx, p.getString(K_FIRST, null), p.getString(K_MET, null)),
            )
            true
        } catch (e: SecurityException) {
            false
        }
    }

    @JvmStatic
    fun cancel(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
        am?.cancel(pendingIntent(ctx, null, null))
        prefs(ctx).edit().putBoolean(K_ENABLED, false).apply()
    }

    /** 画面に出すための今の設定。 */
    @JvmStatic
    fun get(ctx: Context): Map<String, Any?> {
        val p = prefs(ctx)
        return mapOf(
            "enabled" to p.getBoolean(K_ENABLED, false),
            "hour" to p.getInt(K_HOUR, 7),
            "minute" to p.getInt(K_MIN, 0),
            "first" to p.getString(K_FIRST, null),
        )
    }

    /**
     * 1羽目と「出会った鳥」を積んだ PendingIntent。
     *
     * ⚠️ extras は PendingIntent の同一判定に**入らない**ので、cancel 側は
     * null で作っても同じものを指す。
     */
    private fun pendingIntent(ctx: Context, first: String?, met: String?): PendingIntent {
        val i = Intent(ctx, BirdAlarmReceiver::class.java).apply {
            action = BirdAlarmReceiver.ACTION_FIRE
            putExtra(BirdAlarmReceiver.EXTRA_FIRST, first)
            putExtra(BirdAlarmReceiver.EXTRA_MET, met)
        }
        var flags = PendingIntent.FLAG_UPDATE_CURRENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags = flags or PendingIntent.FLAG_IMMUTABLE
        }
        return PendingIntent.getBroadcast(ctx, REQUEST_CODE, i, flags)
    }
}
