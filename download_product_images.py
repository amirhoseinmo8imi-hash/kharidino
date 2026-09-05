# -*- coding: utf-8 -*-

import re
import time
from pathlib import Path

import requests
from PIL import Image
from io import BytesIO
from ddgs import DDGS

from app import app, db, Product


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = BASE_DIR / "static" / "uploads" / "products"

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# SETTINGS
# =========================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
}

TIMEOUT = 20


# =========================================================
# PRODUCT SEARCH QUERIES
# =========================================================

IMAGE_QUERIES = {
    "Samsung Galaxy S24": "Samsung Galaxy S24 official product image",
    "Apple iPhone 16 Pro": "Apple iPhone 16 Pro official product image",
    "Xiaomi Redmi Note 13 Pro": "Xiaomi Redmi Note 13 Pro official product image",
    "Samsung Galaxy A55": "Samsung Galaxy A55 official product image",

    "Apple MacBook Air M3": "MacBook Air M3 official product image",
    "ASUS TUF Gaming F15": "ASUS TUF Gaming F15 official product image",
    "Lenovo IdeaPad Slim 3": "Lenovo IdeaPad Slim 3 official product image",
    "HP Victus 15": "HP Victus 15 official product image",

    "Seagate Expansion Portable 2TB": "Seagate Expansion Portable 2TB official product image",
    "Silicon Power Blaze B10 32GB": "Silicon Power Blaze B10 32GB official product image",
    "Baseus Simple Mini3 Wireless Charger": "Baseus Simple Mini3 Wireless Charger official product image",
    "TP-Link Archer C6": "TP-Link Archer C6 official product image",

    "Apple AirPods Pro 2": "Apple AirPods Pro 2 official product image",
    "Anker Soundcore R50i": "Anker Soundcore R50i official product image",
    "Sony WH-1000XM5": "Sony WH-1000XM5 official product image",

    "Sony PlayStation 5 Slim": "Sony PlayStation 5 Slim official product image",
    "Xbox Series X": "Xbox Series X official product image",
    "Sony DualSense Wireless Controller": "Sony DualSense Wireless Controller official product image",

    "Samsung 55 Inch 4K Smart TV": "Samsung 55 inch 4K Smart TV official product image",
    "LG 55 Inch 4K Smart TV": "LG 55 inch 4K Smart TV official product image",

    "Samsung Galaxy Watch 6": "Samsung Galaxy Watch 6 official product image",
    "Apple Watch Series 9": "Apple Watch Series 9 official product image",

    "Vidhas VIR-5637 Sandwich Maker": "Vidhas VIR-5637 sandwich maker product image",
    "Philips Espresso Machine": "Philips espresso machine official product image",
    "Bosch Vacuum Cleaner": "Bosch vacuum cleaner official product image",
    "Hiska H5107 Hair Brush": "Hiska H5107 hair brush product image",

    "Nivea Sun SPF 50": "Nivea Sun SPF 50 official product image",

    "کتاب بیلیجی": "کتاب بیلیجی تصویر جلد",
    "دفتر یادداشت 100 برگ": "دفتر یادداشت 100 برگ محصول",

    "Nike Running Shoes": "Nike running shoes official product image",
    "قمقمه ورزشی 750ml": "750ml sports water bottle product image",

    "Bosch Cordless Drill": "Bosch cordless drill official product image",
    "Ronix Tool Set": "Ronix tool set official product image",

    "Bosch Car Air Filter": "Bosch car air filter official product image",
    "Car Phone Holder": "car phone holder product image",

    "تیشرت نخی مردانه": "تیشرت نخی مردانه محصول",
    "کفش اسپرت مردانه": "کفش اسپرت مردانه محصول",

    "قهوه فوری کلاسیک": "قهوه فوری کلاسیک محصول",
    "چای سیاه ایرانی": "چای سیاه ایرانی محصول",
}


# =========================================================
# HELPERS
# =========================================================

def make_slug(text):
    """
    تبدیل نام محصول به نام فایل مناسب
    """
    text = str(text).strip().lower()

    text = re.sub(r"[^\w\u0600-\u06FF]+", "-", text)

    text = text.strip("-")

    return text


def search_image(query):
    """
    جستجوی تصویر در DuckDuckGo
    """

    print(f"  🔎 جستجو: {query}")

    try:
        with DDGS() as ddgs:
            results = ddgs.images(
                query,
                safesearch="off",
                max_results=10,
            )

            for result in results:
                image_url = result.get("image")

                if image_url:
                    yield image_url

    except Exception as e:
        print(f"  ❌ خطا در جستجوی تصویر: {e}")


def download_image(url):
    """
    دانلود و بررسی تصویر
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code != 200:
            return None

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if "image" not in content_type:
            return None

        image = Image.open(
            BytesIO(response.content)
        )

        image = image.convert("RGB")

        width, height = image.size

        # تصویر خیلی کوچک نباشد
        if width < 200 or height < 200:
            return None

        # نسبت تصویر خیلی عجیب نباشد
        ratio = width / height

        if ratio < 0.35 or ratio > 3.0:
            return None

        return image

    except Exception:
        return None


def save_product_image(product_name, image):
    """
    ذخیره تصویر محصول
    """

    slug = make_slug(product_name)

    if not slug:
        slug = "product"

    filename = f"{slug}.jpg"

    target = PRODUCT_DIR / filename

    image.save(
        target,
        format="JPEG",
        quality=90,
        optimize=True,
    )

    return filename


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 60)
    print("       KHARIDINO PRODUCT IMAGE DOWNLOADER")
    print("=" * 60)

    print()
    print(f"📁 پوشه تصاویر:")
    print(PRODUCT_DIR)
    print()

    success = 0
    failed = 0
    skipped = 0

    with app.app_context():

        products = Product.query.order_by(
            Product.id
        ).all()

        print(f"📦 تعداد محصولات دیتابیس: {len(products)}")
        print()

        for index, product in enumerate(products, start=1):

            print("-" * 60)

            print(
                f"[{index}/{len(products)}] "
                f"{product.name}"
            )

            slug = make_slug(product.name)

            filename = f"{slug}.jpg"

            target = PRODUCT_DIR / filename

            # -------------------------------------------------
            # اگر فایل قبلاً وجود دارد
            # -------------------------------------------------

            if target.exists():

                print("  ✅ تصویر قبلاً وجود دارد.")

                product.image = (
                    f"uploads/products/{filename}"
                )

                db.session.commit()

                skipped += 1

                continue

            # -------------------------------------------------
            # Query
            # -------------------------------------------------

            query = IMAGE_QUERIES.get(
                product.name,
                f"{product.name} product image"
            )

            image_saved = False

            # -------------------------------------------------
            # Search
            # -------------------------------------------------

            for image_url in search_image(query):

                print(
                    f"  ⬇️ دانلود: {image_url[:100]}"
                )

                image = download_image(
                    image_url
                )

                if image is None:
                    continue

                try:

                    saved_filename = save_product_image(
                        product.name,
                        image
                    )

                    product.image = (
                        f"uploads/products/"
                        f"{saved_filename}"
                    )

                    db.session.commit()

                    print(
                        f"  ✅ ذخیره شد: "
                        f"{saved_filename}"
                    )

                    success += 1
                    image_saved = True

                    break

                except Exception as e:

                    print(
                        f"  ❌ خطا در ذخیره: {e}"
                    )

            # -------------------------------------------------
            # Failed
            # -------------------------------------------------

            if not image_saved:

                print(
                    "  ❌ برای این محصول تصویر پیدا نشد."
                )

                failed += 1

            # کمی مکث برای جلوگیری از محدودیت جستجو
            time.sleep(1)

    print()
    print("=" * 60)
    print("                 FINISHED")
    print("=" * 60)

    print(f"✅ دانلود موفق: {success}")
    print(f"⏭️ قبلاً موجود: {skipped}")
    print(f"❌ ناموفق: {failed}")

    print()
    print("📁 تصاویر در این مسیر ذخیره شدند:")
    print(PRODUCT_DIR)
    print()


if __name__ == "__main__":
    main()