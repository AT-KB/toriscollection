package com.toriscollection.toris_app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * 再起動・アプリ更新・時刻やタイムゾーンの変更のあとに、目覚ましを登録し直す。
 *
 * Android は再起動で AlarmManager の登録を全部捨てる。アプリの更新でも消える。
 * 何もしなければ、目覚ましは**オンのまま表示されているのに鳴らない**
 * (2026-11-08 までの穴。HANDOFF_00 §7-3)。
 *
 * 設定(時刻・1羽目・出会った鳥)は `AlarmScheduler` が保存しているので、
 * ここではそれを読んで次の時刻を登録するだけ。オフなら何もしない。
 */
class AlarmRestoreReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        AlarmScheduler.scheduleNext(context)
    }
}
