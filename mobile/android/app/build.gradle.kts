import java.util.Properties

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
val releaseTaskRequested = gradle.startParameter.taskNames.any {
    it.contains("release", ignoreCase = true)
}

if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use(keystoreProperties::load)
}

fun releaseSigningValue(environmentName: String, propertyName: String): String? {
    val environmentValue = System.getenv(environmentName)?.trim()
    if (!environmentValue.isNullOrBlank()) return environmentValue

    val propertyValue = keystoreProperties.getProperty(propertyName)?.trim()
    return propertyValue?.takeIf { it.isNotBlank() && !it.startsWith("replace-") }
}

val releaseKeyAlias = releaseSigningValue("FOODAI_ANDROID_KEY_ALIAS", "keyAlias")
val releaseKeyPassword = releaseSigningValue("FOODAI_ANDROID_KEY_PASSWORD", "keyPassword")
val releaseStorePath = releaseSigningValue("FOODAI_ANDROID_STORE_FILE", "storeFile")
val releaseStorePassword = releaseSigningValue("FOODAI_ANDROID_STORE_PASSWORD", "storePassword")
val hasCompleteReleaseSigning = listOf(
    releaseKeyAlias,
    releaseKeyPassword,
    releaseStorePath,
    releaseStorePassword,
).all { it != null }
val releaseStoreFile = releaseStorePath?.let(project::file)

if (releaseTaskRequested && !hasCompleteReleaseSigning) {
    throw GradleException(
        "Missing release signing values. Use FOODAI_ANDROID_* environment variables or key.properties."
    )
}
if (releaseTaskRequested && releaseStoreFile?.exists() != true) {
    throw GradleException("Release keystore does not exist: $releaseStoreFile")
}

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.longfixbug.balance"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.longfixbug.balance"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (hasCompleteReleaseSigning) {
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
                storeFile = releaseStoreFile
                storePassword = releaseStorePassword
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
