plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android { namespace="com.notsip.mobile"; compileSdk=36; defaultConfig { applicationId="com.notsip.mobile"; minSdk=29; targetSdk=36; versionCode=9; versionName="0.9.0" } }
dependencies {
 implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
 implementation("com.squareup.okhttp3:okhttp:4.12.0")
 implementation("org.json:json:20250517")
}
