plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "vn.pocketpilot"
    compileSdk = 35

    defaultConfig {
        applicationId = "vn.pocketpilot"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }
}
