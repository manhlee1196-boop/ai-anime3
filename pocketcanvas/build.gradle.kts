plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "vn.pocketcanvas"
    compileSdk = 35

    defaultConfig {
        applicationId = "vn.pocketcanvas"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }
}

dependencies {
    // MediaPipe's on-device Stable Diffusion v1.5 Image Generator API.
    implementation("com.google.mediapipe:tasks-vision:0.10.14")
}
