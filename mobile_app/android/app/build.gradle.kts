plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("Flask==3.0.3")
            install("Flask-SQLAlchemy==3.1.1")
            install("python-dotenv==1.0.1")
            install("requests==2.32.3")
        }
    }
}

val websiteBundleDir = layout.buildDirectory.dir("generated/kharidinoAssets")
val prepareKharidinoWebsiteAssets by tasks.registering(Sync::class) {
    val repositoryRoot = projectDir.resolve("../../..").canonicalFile
    from(repositoryRoot) {
        include("app.py")
        include("*.py")
        include("templates/**")
        include("static/**")
        exclude(".env", ".env.*", "**/.env", "**/.env.*")
        exclude("**/*.db", "**/*.sqlite", "**/*.sqlite3", "**/.kharidino-secret")
    }
    into(websiteBundleDir.map { it.dir("kharidino") })
}

android {
    namespace = "com.kharidino.app"
    compileSdk = 35

    val configuredBaseUrl = (project.findProperty("kharidinoBaseUrl") as String?)
        ?.trim()
        ?.trimEnd('/')
    val baseUrl = (configuredBaseUrl ?: "http://10.0.2.2:5000") + "/"

    defaultConfig {
        applicationId = "com.kharidino.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        buildConfigField("String", "KHARIDINO_BASE_URL", "\"$baseUrl\"")
    }

    buildTypes {
        debug {
            manifestPlaceholders["allowCleartextTraffic"] = "true"
        }
        release {
            manifestPlaceholders["allowCleartextTraffic"] = "false"
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets.getByName("main").assets.srcDir(websiteBundleDir)

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

tasks.named("preBuild").configure {
    dependsOn(prepareKharidinoWebsiteAssets)
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.02.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
}
