# خریدینو — Kharidino Ultimate 🚀

خریدینو یک پلتفرم مقایسه قیمت و خرید چندفروشندگی است. این شاخه روی هسته تجاری، امنیت، پرداخت، حسابداری و عملیات قابل اتکا تمرکز دارد و ظاهر فعلی سایت بدون بازطراحی غیرضروری حفظ شده است.

## هسته تجاری
- خانه، محصول، فروشگاه، دسته‌بندی، سبد خرید و سفارش‌ها
- مقایسه قیمت و پیشنهادهای فروشگاه‌ها
- علاقه‌مندی و مقایسه محصولات
- Marketplace چندفروشندگی و Seller Center
- وضعیت سفارش با State Machine و جلوگیری از پرش مراحل
- رزرو اتمیک موجودی و بازگردانی موجودی هنگام لغو
- Checkout Preflight برای ورودی‌ها، سبد و موجودی

## پرداخت
- چرخه استاندارد `pending → redirect → verifying → paid/failed`
- وضعیت‌های `cancelled` و `refunded`
- Idempotency برای جلوگیری از پرداخت تکراری
- Authority و callback validation
- تأیید سفارش فقط بعد از موفقیت پرداخت
- ایجاد سفارش فروشنده فقط پس از پرداخت موفق
- Adapter مستقل برای اتصال درگاه واقعی ایران
- Test Gateway برای تست end-to-end بدون بانک واقعی

> درگاه واقعی بانکی هنوز باید با API رسمی سرویس‌دهنده موردنظر پیاده‌سازی و کلیدهای آن در محیط Production تنظیم شود؛ Test Gateway فقط برای تست است.

## حسابداری و تسویه
- دفتر روزنامه مالی Double-Entry و idempotent
- ثبت دریافت وجه مشتری
- ثبت درآمد/کمیسیون پلتفرم
- ثبت بدهی فروشنده
- ثبت استرداد وجه
- ثبت پرداخت تسویه فروشنده
- آزادسازی وجه فروشنده فقط پس از `تحویل شد` سفارش اصلی
- جلوگیری از ثبت دوباره سند با `reference` یکتا
- داشبورد حسابداری مدیر و حسابداری فروشنده
- خروجی CSV

## امنیت و عملیات
- CSRF و Same-Origin برای عملیات state-changing
- HttpOnly / SameSite session cookies و Secure در Production
- الزام SECRET_KEY قوی در Production
- محدودیت حجم درخواست و فرم
- Rate limiting پایه
- اعتبارسنجی محتوای فایل‌های تصویری/ویدیویی
- Security Headers و CSP
- کنترل Open Redirect
- Health endpoint و System Health
- لاگ خطای امن بدون نمایش جزئیات داخلی به کاربر
- CI شامل compile، security audit، dependency audit و pytest

## Kharidino AI / Site Doctor
- داشبورد Kharidino AI
- Health Score و Site Doctor
- تحلیل قیمت min/avg/max و قیمت‌های پرت
- Recommendation API
- AI Agent با Change Plan و Approval Required
- Snapshot قبل از تغییرات حساس

## اجرای نسخه Ultimate

```bash
pip install -r requirements.txt
python run_kharidino.py
```

برای Production:

```bash
set KHARIDINO_PRODUCTION=1
set FLASK_DEBUG=0
python run_kharidino.py
```

در لینوکس از `export` به‌جای `set` استفاده کن. مقادیر نمونه را در `.env.example` ببین و Secretها را خارج از Git نگه دار.

## مسیرهای مهم

```text
/healthz
/admin/system-health
/admin/accounting
/seller/accounting
/seller/orders
/payment/start/<order_id>
/payment/callback/<transaction_id>
```

## تست

```bash
python -m compileall -q .
python security_audit.py
python -m pytest -q
```

CI نیز همین کنترل‌ها را روی Python 3.12 اجرا می‌کند و dependency vulnerability audit دارد.

## معماری جریان خرید

```text
Cart
 ↓
Checkout Preflight
 ↓
Atomic Inventory Reservation
 ↓
Order: در انتظار بررسی
 ↓
Payment Transaction
 ↓
Gateway Verification
 ↓
Order: تأیید شد
 ↓
Seller Split + Seller Ledger
 ↓
Order: در حال آماده‌سازی
 ↓
ارسال شد
 ↓
تحویل شد
 ↓
Seller Funds: available
 ↓
Settlement Request
 ↓
Admin Pay
 ↓
Seller Funds: paid
```


## ابرپلتفرم: بازار، اکسپلور، سینما و اپ اندروید

- **اکسپلور:** فید تصویر/ویدئو، انتشار با تأیید مدیر، پسندیدن و گزارش محتوا، اتصال اختیاری پست به محصول.
- **سینما:** کاتالوگ عنوان‌ها، مدیریت و تأیید محتوا، پخش فایل محلی MP4/WebM تا ۹۰ مگابایت در نسخه توسعه، ذخیره ادامه تماشا، تعریف سانس و رزرو ظرفیت.
- **API نسخه ۱:** /api/v1/platform، /api/v1/market/products، /api/v1/explore/feed و /api/v1/cinema/titles.
- **نقشه:** کشف فروشگاه‌ها در /map و API فروشگاه‌های دارای مختصات.
- **Android:** پروژه native مبتنی بر Kotlin و Jetpack Compose در پوشه android/ با Retrofit برای دریافت بازار، اکسپلور و سینما.

### اجرای اپ اندروید

در زمان build مقدار KHARIDINO_API_BASE_URL را به نشانی HTTPS واقعی سرور تنظیم کن؛ مقدار پیش‌فرض صرفاً placeholder است:

~~~bash
cd android
gradle -PKHARIDINO_API_BASE_URL=https://YOUR-DOMAIN/ :app:assembleDebug
~~~

### محدودیت‌های انتشار رسانه و سینما

فایل‌های ویدئویی فعلی به‌صورت محلی و برای نسخه توسعه نگهداری می‌شوند. قبل از انتشار عمومی باید ذخیره‌سازی object storage، پردازش/transcoding، HLS یا DASH، CDN، URL امضاشده، محدودیت دسترسی و بررسی مجوز پخش محتوا اضافه شود. رزرو سانس در این نسخه ظرفیت را به‌صورت شرطی کم می‌کند و کد رزرو تولید می‌کند؛ درگاه پرداخت، تخصیص صندلی مشخص و QR واقعی هنوز متصل نشده‌اند. عنوان‌های سینما پس از ثبت در وضعیت pending می‌مانند و مدیر از صفحه /cinema آن‌ها را تأیید می‌کند.

این بخش‌ها افزوده شده‌اند اما اپ اندروید و زیرساخت استریم هنوز باید با build واقعی، دستگاه و سرویس‌های Production اعتبارسنجی شوند.

## وضعیت انتشار

این شاخه برای تکمیل هسته حرفه‌ای پروژه و عبور از CI/security review آماده‌سازی می‌شود. قبل از Merge نهایی باید اجرای واقعی CI و تست end-to-end، بررسی dependencyها و اتصال درگاه بانکی واقعی انجام شود. PR فعلی عمداً باز می‌ماند تا این بررسی‌ها کامل شوند.
