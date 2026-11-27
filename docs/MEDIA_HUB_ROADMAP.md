# رسانه و کشف خریدینو — برنامه توسعه

## فاز M0: مسیرها و پوسته قابل پیمایش
- [x] ایجاد مسیرهای /explore، /reels و /cinema
- [x] صفحات معرفی هماهنگ با قالب موجود
- [ ] اتصال لینک‌های ناوبری و صفحه اصلی
- [ ] CI و تست رندر سه مسیر

## فاز M1: Explore
- مدل پست رسانه‌ای، caption، tags، محصول/فروشگاه مرتبط و وضعیت moderation
- feed API صفحه‌بندی‌شده، فیلتر و رتبه‌بندی ساده
- لایک، bookmark، گزارش، شمارنده‌ها و سیاست ضد spam
- تست مالکیت، مجوز، صفحه‌بندی و فیلتر محتوای منتشرنشده

## فاز M2: Reels
- upload امن با محدودیت حجم، MIME و بررسی واقعی محتوا؛ پردازش در worker
- thumbnails، transcode، نسخه‌های adaptive و storage abstraction
- فید عمودی، تعاملات، لینک خرید و مدیریت محتوا
- تست‌های upload abuse، playback access و moderation

## فاز M3: Cinema
- catalog: title, season, episode, genre, age rating
- ثبت حقوق: territory، dates، platform و license evidence
- اشتراک و entitlements؛ کنترل دسترسی پخش و concurrency
- pipeline ویدئو، subtitles، resume playback، favorites
- آزمون دسترسی خارج از حقوق/اشتراک و منقضی‌شده

## نکات
- این پوسته اولیه، فید و پخش واقعی نیست.
- محتوای فیلم/سریال فقط با حقوق انتشار مناسب.
- upload، پخش، اشتراک و پرداخت تا زمان تست مستقل و اتصال زیرساخت نباید در تولید فعال شوند.
