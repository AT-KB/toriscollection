package com.toriscollection.toris_app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val alarm = AlarmChannel(this)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, AlarmChannel.CHANNEL)
            .setMethodCallHandler { call, result -> alarm.handle(call, result) }
    }
}
