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
        include(
            "app.py",
            "run_kharidino.py",
            "kharidino_ai.py",
            "commerce_catalog.py",
            "gaming.py",
            "gaming_marketplace.py",
            "gaming_control.py",
            "merchant_marketplace.py",
            "vehicle_marketplace.py",
            "vehicle_chat.py",
            "security_hardening.py",
            "redirect_hardening.py",
            "catalog_security.py",
            "catalog_ux_api.py",
            "inventory_hardening.py",
            "checkout_preflight.py",
            "checkout_idempotency.py",
            "commerce_extensions_v2.py",
            "order_state_machine.py",
            "order_cancellation.py",
            "payment.py",
            "button_flow_hardening.py",
            "refund_settlement_hardening.py",
            "return_refund_bridge.py",
            "clawback_reconciliation.py",
            "financial_reconciliation.py",
            "marketplace_ultimate.py",
            "marketplace_hardening.py",
            "checkout_marketplace_adjustments.py",
            "seller_staff.py",
            "seller_fulfillment.py",
            "marketplace_fulfillment.py",
            "commerce_runtime.py",
            "profile_extensions.py",
            "merchant_approval.py",
            "merchant_marketplace_v2.py",
            "merchant_customer_marketplace.py",
            "seller_storefront.py",
            "seller_introduction.py",
            "terms.py",
            "password_reset.py",
            "accounting.py",
            "system_health.py",
            "inventory_atomicity.py",
            "financial_accounting.py"
        )
        include("mobile_app/api/**")
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
        versionCode = 3
        versionName = "1.0.1"
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

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
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
