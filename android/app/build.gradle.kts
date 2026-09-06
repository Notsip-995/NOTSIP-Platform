plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
import java.util.Base64

android {
 namespace="com.notsip.mobile"
 compileSdk=36
 defaultConfig {
  applicationId="com.notsip.mobile"
  minSdk=29
  targetSdk=36
  versionCode=9
  versionName="0.9.0"
 }
 compileOptions { sourceCompatibility=JavaVersion.VERSION_17; targetCompatibility=JavaVersion.VERSION_17 }
 kotlinOptions { jvmTarget = "17" }
 val ks = System.getenv("ANDROID_KEYSTORE_BASE64")
 if (!ks.isNullOrBlank()) {
  val keystoreFile = layout.buildDirectory.file("release.keystore").get().asFile
  keystoreFile.parentFile.mkdirs()
  if (!keystoreFile.exists()) keystoreFile.writeBytes(Base64.getDecoder().decode(ks))
  signingConfigs.create("release") {
   storeFile = keystoreFile
   storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
   keyAlias = System.getenv("ANDROID_KEY_ALIAS")
   keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
  }
  buildTypes.getByName("release") { isMinifyEnabled=false; signingConfig=signingConfigs.getByName("release") }
 }
}
dependencies {
 implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
 implementation("com.squareup.okhttp3:okhttp:4.12.0")
 implementation("org.json:json:20250517")
}
