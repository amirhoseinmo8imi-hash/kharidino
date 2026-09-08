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

## وضعیت انتشار

این شاخه برای تکمیل هسته حرفه‌ای پروژه و عبور از CI/security review آماده‌سازی می‌شود. قبل از Merge نهایی باید اجرای واقعی CI و تست end-to-end، بررسی dependencyها و اتصال درگاه بانکی واقعی انجام شود. PR فعلی عمداً باز می‌ماند تا این بررسی‌ها کامل شوند.
