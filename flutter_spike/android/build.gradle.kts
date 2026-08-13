allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// 注意(2026-08-12): このリポジトリは OneDrive 配下にあるため、同期がビルド中の
// ファイルを掴んで `Unable to delete directory ... mergeDebugAssets` で落ちる。
// ここで出力先を変えると Flutter 本体が APK を見つけられなくなるので変えない。
// 代わりに `flutter_spike/build` を OneDrive の外へのジャンクションにしている
// (作り方は flutter_spike/README.md を参照)。
val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
