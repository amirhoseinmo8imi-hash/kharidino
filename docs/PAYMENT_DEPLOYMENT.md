# راه‌اندازی پرداخت واقعی خریدینو

## وضعیت فعلی

خریدینو یک لایه‌ی Provider-neutral برای پرداخت دارد و درگاه واقعی از طریق `PAYMENT_PROVIDER` انتخاب می‌شود.
مقدار پیش‌فرض `disabled` است؛ بنابراین محیط Production بدون تنظیم صریح Provider، fail-closed می‌ماند.

در این نسخه Adapter رسمی **NextPay** بر اساس مستندات منتشرشده‌ی خود Provider اضافه شده است.

## تنظیمات Production

مقادیر زیر را فقط در Environment/Secret Manager سرور قرار دهید و هرگز commit نکنید:

```text
SECRET_KEY=<long-random-secret>
KHARIDINO_PRODUCTION=1
FLASK_DEBUG=0
PAYMENT_PROVIDER=nextpay
PAYMENT_TEST_MODE=0
NEXTPAY_API_KEY=<real-provider-api-key>
PAYMENT_HTTP_TIMEOUT=10
```

`PAYMENT_CALLBACK_SECRET` همچنان برای Providerهایی که callback امضاشده ارائه می‌کنند نگه داشته می‌شود؛ NextPay صحت callback را با استعلام سمت سرور (`verify`) و تطبیق `trans_id`، شماره سفارش و مبلغ کنترل می‌کند.

## جریان NextPay

1. خریدینو برای تراکنش یک `public_id` یکتا تولید می‌کند.
2. Adapter با `POST` به endpoint صدور token در NextPay می‌رود.
3. `trans_id` Provider در ستون `authority` ذخیره می‌شود.
4. کاربر به صفحه پرداخت Provider هدایت می‌شود.
5. Callback فقط در صورت تطبیق `trans_id` با تراکنش داخلی پذیرفته می‌شود.
6. قبل از تغییر وضعیت به `paid`، خریدینو endpoint `verify` را از سمت سرور فراخوانی می‌کند.
7. کد موفقیت، مبلغ و `order_id` پاسخ Provider بررسی می‌شوند.
8. فقط پس از موفقیت همه‌ی کنترل‌ها، تراکنش و سفارش commit می‌شوند.

## Timeout و خطای شبکه

`PAYMENT_HTTP_TIMEOUT` بین ۲ تا ۳۰ ثانیه محدود می‌شود و مقدار پیش‌فرض ۱۰ ثانیه است. خطای شبکه هرگز به‌عنوان پرداخت موفق تفسیر نمی‌شود.

## جلوگیری از پرداخت تکراری

- `idempotency_key` در دیتابیس unique است.
- `authority` و `gateway_reference` نیز unique هستند.
- callback با transition اتمیک به `verifying` claim می‌شود.
- callback تکراری بعد از `paid` دوباره مبلغ را ثبت نمی‌کند.
- تطبیق مالک سفارش و مبلغ قبل از `paid` انجام می‌شود.

## لاگ امن

Adapter فقط نوع خطا، کد Provider و یک prefix کوتاه از شناسه تراکنش را log می‌کند. API key، authority کامل، اطلاعات کارت و Secretها log نمی‌شوند.

## تست قبل از فعال‌سازی

CI فقط از fake HTTP response استفاده می‌کند و هیچ درخواست بانکی ارسال نمی‌کند. قبل از Production باید با حساب و محیط مجاز Provider، یک پرداخت واقعی کم‌مبلغ انجام شود و موارد زیر ثبت و تأیید شوند:

- redirect به صفحه پرداخت
- callback واقعی
- verify واقعی
- تطبیق مبلغ
- تطبیق شناسه سفارش
- ثبت reference
- callback تکراری
- timeout / قطعی شبکه

تا تکمیل این Smoke Test، `PAYMENT_PROVIDER=disabled` باقی بماند.

## Refund

مسیر فعلی استرداد داخلی وضعیت تراکنش و حسابداری خریدینو را تغییر می‌دهد، اما **refund واقعی بانکی Provider هنوز به Adapter عمومی متصل نشده است**. بنابراین نباید به مشتری گفته شود که این مسیر بدون اتصال API استرداد، وجه بانکی را واقعاً برگردانده است.
