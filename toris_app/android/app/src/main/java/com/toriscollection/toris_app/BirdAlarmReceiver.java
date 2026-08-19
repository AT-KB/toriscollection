package com.toriscollection.toris_app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * 目覚ましの発火を受け取り、鳴らすサービスを起動する。
 *
 * 2026-08-13: Capacitor 版(android_app)からそのまま移した。Capacitor にも
 * WebView にも依存していないので、パッケージ名以外は手を入れていない。
 *
 * 設計の要点(2026-08-11・MVP):
 *  - **サーバーに一切依存しない**。本アプリの本体は Render 上の Streamlit を
 *    WebView で表示しているだけだが、そこに依存すると
 *    コールドスタート(実測22.7秒)のせいで朝いちばんに間に合わない。
 *    鳴らす音は APK に同梱した音源だけを使い、通信も WebView も介さない。
 *  - 端末が Doze(省電力)に入っていても鳴らす必要があるため、
 *    AlarmManager 側は setExactAndAllowWhileIdle() で登録する
 *    (登録は BirdAlarmBridge が行う)。
 *  - 受信後の再生は BroadcastReceiver の中で完結させず、
 *    フォアグラウンドサービスへ渡す。Receiver は数秒で殺されるため、
 *    長く鳴らす処理をここに書くと途中で止まる。
 */
public class BirdAlarmReceiver extends BroadcastReceiver {

    public static final String ACTION_FIRE = "com.toriscollection.toris_app.ALARM_FIRE";

    @Override
    public void onReceive(Context context, Intent intent) {
        // 鳥は選ばせない。鳴く並びは BirdAlarmSounds.chorusKeys() が持つ。
        Intent svc = new Intent(context, BirdAlarmService.class);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(svc);
        } else {
            context.startService(svc);
        }
    }
}
