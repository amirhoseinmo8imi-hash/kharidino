# Android: Embedded Local Website

The Android app packages the existing Flask website and runs it on the device. It does not require a public domain or hosting to open local pages.

## Runtime

- Chaquopy embeds Python 3.11.
- The Android Gradle build copies the website's root Python modules, all templates, and static assets into APK assets.
- At first launch, assets are copied to app-private `filesDir/kharidino`.
- Flask/SQLAlchemy runs on `127.0.0.1:8765` only; it is not exposed to the Wi-Fi/LAN.
- The existing SQLite database and generated Flask secret are stored in the app-private website folder.
- WebView renders the actual Flask website pages. External links are handed to the Android browser.
- On app updates, bundled code/templates refresh while the SQLite DB, secret and existing user uploads are preserved.

## Build

Open `mobile_app/android` in Android Studio or run `.gradlew.bat :app:assembleDebug` from that directory. The first build needs internet to download Gradle/Chaquopy/Python dependencies. The installed app can open bundled local pages without a public host.

## Offline boundaries

Local pages, local SQLite records, and bundled assets can work offline. These features still need internet/provider connectivity: online payment settlement and callbacks, SMS/email delivery, password recovery, remote chat/AI, live prices, external store checkout, and cloud account synchronization. Product images not bundled in `static/uploads` may not appear offline.

Orders stored locally are device-local records; they are not delivered to a merchant or centrally processed until a sync service is added. The PDF invoice route still depends on ReportLab and Persian text-shaping libraries which are not included in the Android Python dependency set; HTML invoices are the current fallback.

## Security

The embedded server binds only to loopback. WebView file/content access is disabled, mixed content is blocked, third-party cookies are disabled, and non-local links leave the WebView. Do not ship production admin credentials or treat a device-local admin session as centrally authenticated.

## Future hosting

The existing Flask codebase remains the basis for future hosting. A later sync/API layer can add remote authentication and data synchronization without making the app depend on a public website for its local shell.
