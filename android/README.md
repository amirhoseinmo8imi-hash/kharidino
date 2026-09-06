# 📱 Kharidino Android + Offline Sync

این پروژه یک اپ native اندروید برای مدیریت خریدینو است که با backend فعلی Flask کار می‌کند.

## قابلیت‌ها
- ورود امن مدیر از طریق `/api/mobile/auth/login`
- ذخیره محلی محصولات با Room/SQLite
- افزودن محصول بدون اینترنت
- صف تغییرات با UUID و ارسال دسته‌ای
- همگام‌سازی خودکار با WorkManager وقتی اینترنت برقرار شود
- دریافت snapshot محصولات از سرور
- نگهداری توکن در SharedPreferences
- پشتیبانی از سرور محلی کامپیوتر با Wi‑Fi

## اجرا
پوشه `android/` را در Android Studio باز کنید و Gradle Sync را بزنید. سپس دستگاه Android یا Emulator را اجرا کنید.

برای Emulator آدرس پیش‌فرض backend برابر `http://10.0.2.2:5000` است. برای گوشی واقعی، آدرس `http://IP-کامپیوتر:5000` را در صفحه ورود وارد کنید و هر دو دستگاه را روی یک شبکه قرار دهید.

## جریان Offline → Online
1. محصول در Room ذخیره می‌شود.
2. یک رکورد در `sync_queue` ساخته می‌شود.
3. WorkManager منتظر اتصال شبکه می‌ماند.
4. `/api/mobile/sync/push` عملیات را روی Flask اعمال می‌کند.
5. رکوردهای صف حذف و داده‌های سرور دوباره pull می‌شوند.

> برای انتشار اینترنتی، HTTPS را فعال کنید و `usesCleartextTraffic` را به حالت امن production تغییر دهید.
