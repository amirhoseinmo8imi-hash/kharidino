# Kharidino Android App

این پوشه پایه معماری نسخه موبایل خریدینو است.

## هدف
نسخه Android باید ظاهر و تجربه کاربری مستقل از سایت داشته باشد و از همان Backend/API خریدینو استفاده کند.

## ساختار پیشنهادی

- `app/` — اپ Android
- `docs/` — مستندات UI و API
- `design/` — مشخصات طراحی موبایل

## UI اصلی

1. Splash اختصاصی اپ
2. Home با جستجوی هوشمند
3. دسته‌بندی‌ها
4. لیست محصولات
5. صفحه جزئیات محصول با گالری تصاویر
6. مقایسه قیمت
7. علاقه‌مندی‌ها
8. اعلان کاهش قیمت
9. پروفایل کاربر
10. Kharidino AI

## ناوبری موبایل

نوار پایین پنج بخش دارد:

- خانه
- دسته‌بندی
- جستجو
- علاقه‌مندی
- حساب کاربری

دکمه Kharidino AI به صورت Floating Action Button در صفحات اصلی قرار می‌گیرد.

## اصل مهم

اپ Android نباید صرفاً WebView سایت باشد. رابط کاربری Native و مستقل طراحی می‌شود و برای داده‌ها از API خریدینو استفاده می‌کند.


## Android Studio build scaffold

Project Gradle files and Android launcher wrapper now exist under `app/`. The wrapper uses a secure HTTPS WebView, launcher icon, startup screen, progress indicator, state restoration and back navigation.

To build APK: open `mobile_app` in Android Studio, change `APP_URL` in `app/src/main/java/com/kharidino/app/MainActivity.java` to the verified production HTTPS URL, sync Gradle and use Build > Build APK(s). The current URL is a placeholder; this is a WebView wrapper, not a fully native API-based app. Device testing remains required.
