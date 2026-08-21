# R8(release ビルドの縮小)向けの keep ルール。
#
# ## なぜ要るか(2026-08-21 実機で発覚)
# 広告(`google_mobile_ads`)が WorkManager を連れてくる。WorkManager は Room を
# 使い、Room は生成クラスを **`Class.forName(名前 + "_Impl")` で引く**。
# 参照している場所がコード上に無いので、R8 が `WorkDatabase_Impl` を消してしまい、
# **起動と同時に落ちる**(androidx.startup.InitializationProvider →
# Failed to create an instance of androidx.work.impl.WorkDatabase)。
#
# ⚠️ **debug では再現しない**(R8 が動かないため)。release で実機に入れて初めて出る。
-keep class * extends androidx.room.RoomDatabase { <init>(); }
-keep class androidx.work.impl.WorkDatabase_Impl { *; }
