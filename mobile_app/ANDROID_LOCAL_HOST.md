# Android: Embedded Kharidino Website

The Android app packages the full Flask runtime and starts it on the device. A public domain or hosting plan is not required for local pages.

## Runtime and included modules

- Chaquopy embeds Python 3.11.
- The app launches the project's production entry point, `run_kharidino.py`, not only `app.py`. This registers the catalog, mobile API, security, checkout, payment, order lifecycle, seller marketplace, fulfillment, accounting, profile, gaming and vehicle modules.
- Gradle bundles the exact runtime Python modules, `mobile_app/api`, all templates, and all static assets.
- First launch copies the bundle into app-private `filesDir/kharidino`.
- Flask/SQLAlchemy listens on `127.0.0.1:8765` only.
- WebView renders the actual Flask pages. External HTTP(S) links are opened outside the local WebView.
- SQLite, generated session secret, and uploaded files live in app-private storage. App updates refresh the bundled source while preserving the local database and existing uploads.

## Initial data

The existing `run_kharidino.py` seed routine creates baseline settings, categories, demo catalog entries and the initial local data needed by the app. Seed prices are examples, not live offers. On a standalone Android install only, the first account registered on that device is granted the local admin role; hosted-site registration behavior is unchanged. No `kharidino.db` file is present in the GitHub repository or the user's accessible ChatGPT Library, so the production website's existing users, orders, products, store records and settings have not been migrated into this APK.

## Offline boundaries

Local pages and SQLite-backed records can work offline. Payment settlement/callbacks, SMS/email, remote password recovery, live price refresh, cloud AI/chat, external checkout, sending orders to merchants and cloud synchronization still need their external providers or a future hosted API. Orders entered offline remain local to that device until a sync service is implemented.

The PDF invoice endpoint may require ReportLab and Persian shaping packages not currently installed in the Android Python environment; HTML invoice views remain the supported local fallback.

## Build and validation

Open `mobile_app/android` in Android Studio with JDK 17 and Gradle 8.9, or run `gradle assembleDebug` from that directory. The first build needs internet to download Gradle, Android SDK and Chaquopy dependencies. The installed app does not need a public host to load the embedded website.

The GitHub Actions workflow publishes a debug APK artifact only after a successful build. A successful CI build still needs installation and runtime testing on a physical Android device before release.

## Security and future hosting

The server binds to loopback only; WebView file/content access is disabled, mixed content is blocked, and third-party cookies are disabled. There is no hard-coded admin password. Local accounts are device-local, not central accounts. A future sync/API layer can connect the app to a hosted backend without making the local shell depend on a website.
