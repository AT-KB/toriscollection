package com.toriscollection.toris_app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Build
import android.view.WindowManager
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * ラジオの「画面を消しても鳴らし続ける」まわりの窓口。
 *
 * 音そのものは Flutter 側(SoLoud)が鳴らす。ここがやるのは2つだけ:
 *   1. 鳴っている間だけフォアグラウンドサービスを立てる(背面で消されないように)
 *   2. 睡眠モードのあいだ画面を暗くする
 */
class RadioChannel(private val activity: Activity) {

    companion object {
        const val CHANNEL = "toris/radio"
    }

    fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "startForeground" -> {
                val i = Intent(activity, RadioService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    activity.startForegroundService(i)
                } else {
                    activity.startService(i)
                }
                result.success(true)
            }
            "stopForeground" -> {
                activity.stopService(Intent(activity, RadioService::class.java))
                result.success(true)
            }
            // 通知の「Stop」が押されたか。Flutter 側が拾って音を止める。
            "stopRequested" -> result.success(RadioService.STOP_REQUESTED)
            "clearStopRequest" -> {
                RadioService.STOP_REQUESTED = false
                result.success(true)
            }
            /**
             * 睡眠モード中の画面の明るさ。
             *
             * `-1` で端末の設定に戻す。0.0 にすると**消灯ではなく最小の明るさ**に
             * なる(Android の仕様)。実際に画面が消えるのは端末のスリープ時間に
             * よるので、こちらからは**画面を起こし続けない**ことが大事
             * (FLAG_KEEP_SCREEN_ON を立てない)。音は上のサービスが守る。
             */
            "setBrightness" -> {
                val v = (call.argument<Double>("value") ?: -1.0).toFloat()
                activity.runOnUiThread {
                    val lp = activity.window.attributes
                    lp.screenBrightness = v
                    activity.window.attributes = lp
                    // 念のため、画面を起こし続ける指定が残っていたら外す
                    activity.window.clearFlags(
                        WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                    )
                }
                result.success(true)
            }
            else -> result.notImplemented()
        }
    }
}
