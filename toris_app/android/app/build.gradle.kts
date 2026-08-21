import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// 署名鍵。android/key.properties に置く(git には入れない)。
// 鍵の実体は C:/Users/kubok/TorisCollection-ReleaseKeys/ にあり、
// **Play に上がっている com.toriscollection.app と同じ鍵**でなければ
// 更新として受け付けられない。
val keystoreProperties = Properties().apply {
    val f = rootProject.file("key.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val hasKeystore = keystoreProperties.getProperty("storeFile") != null

android {
    namespace = "com.toriscollection.toris_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // ⚠️ Play に公開済みの Capacitor 版と**同じ applicationId**。
        // これを変えると別アプリ扱いになり、既存の掲載を更新できない。
        // クラス名は namespace(com.toriscollection.toris_app)側のままでよい。
        applicationId = "com.toriscollection.app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasKeystore) {
            create("release") {
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
            }
        }
    }

    buildTypes {
        debug {
            // **開発中のビルドで Play 版を潰さない。**
            // release は公開済みと同じ com.toriscollection.app なので、
            // debug だけ別パッケージにして端末に並べられるようにする。
            applicationIdSuffix = ".dev"
        }
        release {
            // R8 が Room の生成クラスを消して起動即クラッシュするのを防ぐ。
            // 中身の理由は proguard-rules.pro に書いてある。
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // key.properties が無い環境では debug 鍵に落ちる(`flutter run --release`用)。
            // Play に出すビルドでは必ず release 鍵が使われていることを確かめること。
            signingConfig = if (hasKeystore) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
