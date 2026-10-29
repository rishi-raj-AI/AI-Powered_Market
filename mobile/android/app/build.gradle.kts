plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Private release credentials are injected only by an approved signing runner.
// QA/debug builds never need them and release must never fall back to debug.
val releaseSigning = listOf(
    "GAONONE_RELEASE_KEYSTORE_PATH", "GAONONE_RELEASE_KEY_ALIAS",
    "GAONONE_RELEASE_STORE_PASSWORD", "GAONONE_RELEASE_KEY_PASSWORD",
).associateWith { System.getenv(it).orEmpty() }
val releaseSigningReady = releaseSigning.values.all { it.isNotBlank() }

gradle.taskGraph.whenReady {
    if (allTasks.any { it.project == project && it.name in setOf(
            "assembleRelease", "bundleRelease", "packageRelease", "validateSigningRelease"
        ) }) {
        check(releaseSigningReady) {
            "Release signing is not configured. Supply the four GAONONE_RELEASE_* inputs on an approved signing runner; use debug for QA."
        }
        check(releaseSigning.getValue("GAONONE_RELEASE_KEY_ALIAS") != "androiddebugkey" &&
            file(releaseSigning.getValue("GAONONE_RELEASE_KEYSTORE_PATH")).name != "debug.keystore") {
            "Android debug signing is not permitted for a production release."
        }
    }
}

android {
    namespace = "in.gaonone.gaonone_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Flutter encodes --dart-define-from-file entries for Gradle. Reuse
        // that allowlisted public configuration; never log the decoded values.
        val defines = (project.findProperty("dart-defines") as? String).orEmpty()
            .split(",").filter { it.isNotEmpty() }.associate {
                val pair = String(java.util.Base64.getDecoder().decode(it), Charsets.UTF_8)
                    .split("=", limit = 2)
                pair[0] to pair.getOrElse(1) { "" }
            }
        val mapsKey = defines["GAONONE_GOOGLE_MAPS_ANDROID_API_KEY"].orEmpty().trim()
        check(defines["GAONONE_ANDROID_MAPS_ENABLED"] != "true" || mapsKey.isNotEmpty()) {
            "Android Maps enabled without GAONONE_GOOGLE_MAPS_ANDROID_API_KEY"
        }
        manifestPlaceholders["gaononeMapsApiKey"] = mapsKey
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "in.gaonone.gaonone_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (releaseSigningReady) {
                storeFile = file(releaseSigning.getValue("GAONONE_RELEASE_KEYSTORE_PATH"))
                keyAlias = releaseSigning.getValue("GAONONE_RELEASE_KEY_ALIAS")
                storePassword = releaseSigning.getValue("GAONONE_RELEASE_STORE_PASSWORD")
                keyPassword = releaseSigning.getValue("GAONONE_RELEASE_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
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
