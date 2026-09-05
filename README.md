# خریدینو — Kharidino Ultimate 🚀

خریدینو یک پلتفرم مقایسه قیمت و خرید هوشمند است. این نسخه علاوه بر فروشگاه، یک لایه مدیریتی **Kharidino AI** و **Site Doctor** دارد.

## امکانات فعلی
- رابط کاربری Dark / Glassmorphism و Responsive
- صفحه خانه، محصول، فروشگاه، دسته‌بندی، سبد خرید و سفارش‌ها
- جست‌وجو و مقایسه قیمت فروشگاه‌ها
- علاقه‌مندی و مقایسه محصولات
- مدیریت محصولات، دسته‌بندی‌ها، فروشگاه‌ها، قیمت‌ها و کاربران
- آپلود تصویر و پس‌زمینه تصویر/ویدیو
- Kharidino AI Dashboard
- Site Doctor با Health Score
- تحلیل min/avg/max قیمت و تشخیص قیمت‌های پرت
- Recommendation API بر اساس دسته‌بندی
- AI Agent با فرمان فارسی/انگلیسی و Change Plan
- فرمان صوتی فارسی در مرورگرهای پشتیبان Speech Recognition
- Snapshot قبل از تغییرات حساس
- PWA foundation

## اجرای معمول

```bash
pip install -r requirements.txt
python app.py
```

## اجرای نسخه Ultimate
برای فعال بودن Kharidino AI از لانچر امن استفاده کن:

```bash
python run_kharidino.py
```

داشبورد مدیر:

```text
/admin/kharidino-ai/
```

Debug در لانچر Ultimate به‌صورت پیش‌فرض خاموش است و فقط با `FLASK_DEBUG=1` فعال می‌شود.

## امنیت
- `.env`، دیتابیس، cache و فایل‌های موقت در Git نادیده گرفته شده‌اند.
- `SECRET_KEY` را در محیط Production تنظیم کن.
- رمز نمونه مدیر را قبل از انتشار تغییر بده.
- AI Agent در این نسخه **Approval Required** است و خودش کد یا دیتابیس را بدون تأیید تغییر نمی‌دهد.

## معماری AI

```text
User / Voice
     ↓
Kharidino AI
     ↓
Site Doctor / Analyzer
     ↓
Change Plan
     ↓
Manager Approval
     ↓
Backup / Snapshot
     ↓
Apply
     ↓
Automated Tests
     ↓
Save or Rollback
```

> قابلیت Apply/Rollback کامل کد به‌صورت عمدی در لایه امن بعدی توسعه داده می‌شود تا هیچ فرمان اشتباهی نتواند پروژه یا دیتابیس را تخریب کند.

## تست

```bash
python -m pytest tests/test_kharidino_ai.py
```

پرداخت آنلاین واقعی در این نسخه به درگاه بانکی متصل نشده است؛ سفارش در سایت ثبت می‌شود.
