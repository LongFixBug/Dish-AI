import java.util.Properties

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
val releaseTaskRequested = gradle.startParameter.taskNames.any {
    it.contains("release", ignoreCase = true)
}
val signingPropertyNames = listOf("keyAlias", "keyPassword", "storeFile", "storePassword")

if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use(keystoreProperties::load)
}

val hasCompleteReleaseSigning = keystorePropertiesFile.exists() &&
    signingPropertyNames.all { name ->
        val value = keystoreProperties.getProperty(name)
        !value.isNullOrBlank() && !value.startsWith("replace-")
    }
val releaseStoreFile = if (hasCompleteReleaseSigning) {
    project.file(keystoreProperties.getProperty("storeFile"))
} else {
    null
}

if (releaseTaskRequested && !hasCompleteReleaseSigning) {
    throw GradleException(
        "Missing release signing values. Copy key.properties.example and provide real credentials."
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
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = releaseStoreFile
                storePassword = keystoreProperties.getProperty("storePassword")
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
