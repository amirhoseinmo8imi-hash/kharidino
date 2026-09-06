import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

from app import app, db, Product


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "products"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# =========================================================
# منابع دقیق محصولات 14 تا 20
# =========================================================

SOURCES = {

    # Seagate فعلاً عمداً خالی است چون چند مدل 2TB دارد
    "Seagate Expansion Portable 2TB": None,

    # مدل دقیق:
    # SP032GBUF3B10V1B
    "Silicon Power Blaze B10 32GB":
        "https://www.newegg.com/silicon-power-blaze-b10-32gb-usb-3-0-black/p/N82E16820301044",

    # مدل دقیق:
    # CCJJ040001
    "Baseus Simple Mini3 Wireless Charger":
        "https://www.baseus.com/products/simple-mini3-magnetic-wireless-charger-15w",

    # محصول قبلاً تصویر دارد، پس دست نمی‌زنیم
    "TP-Link Archer C6": None,

    "Apple AirPods Pro 2":
        "https://www.apple.com/shop/buy-airpods/airpods-pro-2",

    # مدل:
    # A3949
    "Anker Soundcore R50i":
        "https://irananker.com/shop/video-and-audio/buds/headphone-a3949/",

    "Sony WH-1000XM5":
        "https://electronics.sony.com/audio/headphones/headband/p/wh1000xm5-b",
}


KEYWORDS = {
    "Silicon Power Blaze B10 32GB": [
        "blaze",
        "b10",
        "sp032gbuf3b10v1b",
        "silicon-power",
        "siliconpower",
    ],

    "Baseus Simple Mini3 Wireless Charger": [
        "simple-mini3",
        "simple mini3",
        "ccjj040001",
        "baseus",
        "magnetic",
        "wireless",
        "charger",
    ],

    "Apple AirPods Pro 2": [
        "airpods-pro",
        "airpods pro",
        "airpods",
        "pro-2",
        "pro2",
        "apple",
    ],

    "Anker Soundcore R50i": [
        "r50i",
        "a3949",
        "soundcore",
        "anker",
    ],

    "Sony WH-1000XM5": [
        "wh1000xm5",
        "wh-1000xm5",
        "1000xm5",
        "sony",
        "headphone",
    ],
}


def clean_url(url):
    if not url:
        return None

    url = url.strip()

    # حذف query های اضافی مخصوص CDN
    if "?" in url:
        url = url.split("?")[0]

    return url


def score_image(product_name, image_url, alt=""):
    text = f"{image_url} {alt}".lower()

    score = 0

    for keyword in KEYWORDS.get(product_name, []):
        if keyword.lower() in text:
            score += 10

    # تصاویر کوچک / آیکون / لوگو معمولاً مناسب محصول نیستند
    bad_words = [
        "logo",
        "icon",
        "sprite",
        "avatar",
        "banner",
        "background",
        "review",
        "thumbnail",
    ]

    for bad in bad_words:
        if bad in text:
            score -= 8

    return score


def get_image_candidates(page_url, product_name):
    print(f"🌐 {page_url}")

    response = requests.get(
        page_url,
        headers=HEADERS,
        timeout=30,
        allow_redirects=True,
    )

    print(f"   HTTP: {response.status_code}")

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    candidates = []

    # -----------------------------------------------------
    # OG IMAGE
    # -----------------------------------------------------

    for tag in soup.find_all(
        "meta",
        attrs={"property": "og:image"}
    ):
        url = tag.get("content")

        if url:
            url = urljoin(response.url, url)

            candidates.append(
                (
                    score_image(product_name, url, "og-image"),
                    url,
                    "og-image",
                )
            )

    # -----------------------------------------------------
    # تصاویر IMG
    # -----------------------------------------------------

    for img in soup.find_all("img"):

        attrs = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-lazy-src"),
            img.get("data-original"),
        ]

        srcset = img.get("srcset")

        if srcset:
            parts = [
                x.strip().split(" ")[0]
                for x in srcset.split(",")
            ]

            attrs.extend(parts)

        alt = img.get("alt", "")

        for url in attrs:

            if not url:
                continue

            url = urljoin(response.url, url)

            if not url.startswith("http"):
                continue

            score = score_image(
                product_name,
                url,
                alt,
            )

            candidates.append(
                (
                    score,
                    url,
                    alt,
                )
            )

    # حذف تکراری‌ها
    unique = {}

    for score, url, alt in candidates:

        if url not in unique:
            unique[url] = (
                score,
                url,
                alt,
            )

    candidates = list(unique.values())

    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return candidates


def download_image(url, product_name, product_id):
    print(f"⬇️ دانلود: {url}")

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        if response.status_code != 200:
            print(
                f"   ❌ HTTP تصویر: "
                f"{response.status_code}"
            )
            return None

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        # باید تصویر باشد
        if "image" not in content_type:

            # بعضی CDN ها Content-Type درست نمی‌دهند
            try:
                image = Image.open(
                    BytesIO(response.content)
                )
                image.verify()
            except Exception:
                print("   ❌ فایل تصویر معتبر نیست")
                return None

        image = Image.open(
            BytesIO(response.content)
        )

        # بررسی ابعاد
        width, height = image.size

        if width < 250 or height < 250:
            print(
                f"   ❌ تصویر خیلی کوچک است: "
                f"{width}x{height}"
            )
            return None

        # تبدیل RGB
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        filename = (
            f"product_{product_id}_"
            f"{re.sub(r'[^a-zA-Z0-9_-]+', '-', product_name)}"
            ".jpg"
        )

        output = UPLOAD_DIR / filename

        image.save(
            output,
            "JPEG",
            quality=94,
            optimize=True,
        )

        print(
            f"   ✅ ذخیره شد: "
            f"{output.relative_to(BASE_DIR)}"
        )

        return f"uploads/products/{filename}"

    except Exception as e:

        print(
            f"   ❌ خطا: {type(e).__name__}: {e}"
        )

        return None


def process_product(product):
    name = product.name

    print()
    print("=" * 70)
    print(f"📦 #{product.id} - {name}")
    print("=" * 70)

    source = SOURCES.get(name)

    if not source:
        print("⏭️ این محصول فعلاً نیاز به تغییر ندارد")
        return "skip"

    # اگر تصویر موجود است، دست نزن
    if product.image:

        file_path = BASE_DIR / "static" / product.image

        if file_path.exists():

            print(
                "📷 تصویر قبلی موجود است:"
            )

            print(
                f"    {product.image}"
            )

            print("⏭️ بدون تغییر")

            return "existing"

    try:

        candidates = get_image_candidates(
            source,
            name,
        )

    except Exception as e:

        print(
            f"❌ خطا در دریافت صفحه: "
            f"{type(e).__name__}: {e}"
        )

        return "failed"

    if not candidates:

        print("❌ هیچ تصویر پیدا نشد")
        return "failed"

    print(
        f"🔎 {len(candidates)} تصویر پیدا شد"
    )

    # فقط 8 کاندیدای برتر
    for score, url, alt in candidates[:8]:

        print(
            f"   ⭐ {score:3d} "
            f"{url[:150]}"
        )

    # فقط تصاویر با امتیاز مناسب
    for score, url, alt in candidates:

        if score < 10:
            continue

        saved = download_image(
            url,
            name,
            product.id,
        )

        if saved:

            product.image = saved

            db.session.commit()

            return "new"

    print("❌ تصویر قابل اعتماد پیدا نشد")

    return "failed"


def main():

    print()
    print("=" * 70)
    print("🛒 KHARIDINO")
    print("🖼️ BATCH IMAGE DOWNLOADER 14-20")
    print("=" * 70)

    stats = {
        "new": 0,
        "existing": 0,
        "skip": 0,
        "failed": 0,
    }

    with app.app_context():

        target_names = list(SOURCES.keys())

        products = (
            Product.query
            .filter(
                Product.name.in_(target_names)
            )
            .order_by(Product.id)
            .all()
        )

        for product in products:

            result = process_product(product)

            stats[result] += 1

    print()
    print("=" * 70)
    print("📊 نتیجه")
    print("=" * 70)

    print(f"✅ جدید: {stats['new']}")
    print(f"📷 قبلی: {stats['existing']}")
    print(f"⏭️ رد شده: {stats['skip']}")
    print(f"❌ ناموفق: {stats['failed']}")

    print("=" * 70)


if __name__ == "__main__":
    main()