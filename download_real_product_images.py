import io
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

from app import app, db, Product


BASE_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = BASE_DIR / "static" / "uploads" / "products"
PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/139.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# منابع دقیق محصولات
# ============================================================

SOURCES = {

    "ASUS TUF Gaming F15":
        "https://www.asus.com/us/laptops/for-gaming/"
        "tuf-gaming/asus-tuf-gaming-f15/",

    "Lenovo IdeaPad Slim 3":
        "https://www.lenovo.com/us/en/p/laptops/ideapad/"
        "ideapad-300/ideapad-slim-3-gen-8-15-inch-amd/"
        "len101i0073",

    "HP Victus 15":
        "https://www.hp.com/us-en/shop/mdp/gaminglaptops/victus-15",

    "TP-Link Archer C6":
        "https://www.tp-link.com/us/home-networking/"
        "wifi-router/archer-c6/",

    "Xiaomi Redmi Note 13 Pro":
        "https://www.mi.com/global/product/redmi-note-13-pro/",

    "Sony DualSense Wireless Controller":
        "https://www.playstation.com/en-us/accessories/"
        "dualsense-wireless-controller/",

    "Xbox Series X":
        "https://www.xbox.com/en-US/consoles/xbox-series-x",

    "Galaxy S24":
        "https://www.samsung.com/az/smartphones/galaxy-s24/",

    "Samsung Galaxy S24":
        "https://www.samsung.com/az/smartphones/galaxy-s24/",

    "Samsung Galaxy A55":
        "https://www.samsung.com/az/smartphones/galaxy-a/"
        "galaxy-a55-5g-awesome-navy-128gb-sm-a556ezkacau/",

    "Apple MacBook Air M3":
        "https://www.apple.com/az/macbook-air/",

    "MacBook Air M3":
        "https://www.apple.com/az/macbook-air/",
}


# ============================================================
# کلمات کلیدی مخصوص هر محصول
# ============================================================

KEYWORDS = {

    "ASUS TUF Gaming F15":
        ["tuf", "gaming", "f15"],

    "Lenovo IdeaPad Slim 3":
        ["ideapad", "slim", "3"],

    "HP Victus 15":
        ["victus", "15"],

    "TP-Link Archer C6":
        ["archer", "c6"],

    "Xiaomi Redmi Note 13 Pro":
        ["redmi", "note", "13", "pro"],

    "Sony DualSense Wireless Controller":
        ["dualsense", "controller"],

    "Xbox Series X":
        ["xbox", "series", "x"],

    "Galaxy S24":
        ["galaxy", "s24"],

    "Samsung Galaxy S24":
        ["galaxy", "s24"],

    "Samsung Galaxy A55":
        ["galaxy", "a55"],

    "Apple MacBook Air M3":
        ["macbook", "air", "m3"],

    "MacBook Air M3":
        ["macbook", "air", "m3"],
}


# ============================================================
# تبدیل نام به filename
# ============================================================

def make_filename(product):
    safe = ""

    for char in product.name:
        if char.isalnum() or char in " _-":
            safe += char

    safe = safe.strip().replace(" ", "_")

    return f"product_{product.id}_{safe}.jpg"


# ============================================================
# اعتبارسنجی عکس
# ============================================================

def valid_image(data):

    if not data:
        return False

    if len(data) < 10000:
        return False

    try:

        image = Image.open(io.BytesIO(data))

        width, height = image.size

        if width < 250 or height < 250:
            return False

        if width * height < 100000:
            return False

        image.verify()

        return True

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        return False


# ============================================================
# تبدیل به JPG
# ============================================================

def convert_jpg(data):

    try:

        image = Image.open(
            io.BytesIO(data)
        ).convert("RGB")

        output = io.BytesIO()

        image.save(
            output,
            "JPEG",
            quality=92,
        )

        return output.getvalue()

    except Exception:

        return None


# ============================================================
# استخراج تصاویر
# ============================================================

def extract_images(html, page_url):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    images = []

    # --------------------------------------------------------
    # OG IMAGE
    # --------------------------------------------------------

    for meta in soup.find_all("meta"):

        prop = (
            meta.get("property")
            or meta.get("name")
            or ""
        ).lower()

        if prop in (
            "og:image",
            "og:image:url",
            "twitter:image",
        ):

            value = meta.get("content")

            if value:

                images.append({
                    "url": urljoin(
                        page_url,
                        value,
                    ),
                    "text": (
                        " ".join(
                            filter(
                                None,
                                [
                                    meta.get(
                                        "property"
                                    ),
                                    meta.get(
                                        "name"
                                    ),
                                    value,
                                ],
                            )
                        )
                    ),
                })

    # --------------------------------------------------------
    # IMG
    # --------------------------------------------------------

    for img in soup.find_all("img"):

        possible = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-lazy-src"),
            img.get("data-original"),
        ]

        image_url = None

        for value in possible:

            if value:

                image_url = urljoin(
                    page_url,
                    value,
                )

                break

        if not image_url:
            continue

        text = " ".join([
            img.get("alt", ""),
            img.get("title", ""),
            image_url,
        ])

        images.append({
            "url": image_url,
            "text": text,
        })

    # حذف URLهای تکراری
    unique = {}

    for item in images:
        unique[item["url"]] = item

    return list(unique.values())


# ============================================================
# امتیازدهی
# ============================================================

def score_image(item, product_name):

    text = (
        item["url"] + " " +
        item["text"]
    ).lower()

    score = 0

    for keyword in KEYWORDS.get(
        product_name,
        product_name.lower().split(),
    ):

        if keyword.lower() in text:
            score += 5

    # عکس‌هایی که واضحاً لوگو یا آیکون هستند حذف شوند

    bad_words = [
        "logo",
        "icon",
        "favicon",
        "arrow",
        "menu",
        "close",
        "loader",
        "spinner",
        "background",
        "banner",
    ]

    for word in bad_words:

        if word in text:
            score -= 10

    # فرمت تصویر

    if any(
        x in item["url"].lower()
        for x in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ]
    ):
        score += 1

    return score


# ============================================================
# دانلود یک تصویر
# ============================================================

def download(url):

    try:

        response = session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return None

        data = response.content

        if not valid_image(data):
            return None

        return convert_jpg(data)

    except Exception:

        return None


# ============================================================
# پردازش محصول
# ============================================================

def process_product(product):

    name = product.name

    print()
    print("=" * 70)
    print(
        f"📦 #{product.id} - {name}"
    )
    print("=" * 70)

    # اگر تصویر معتبر قبلی وجود دارد، دست نزن
    if product.image:

        existing = (
            BASE_DIR
            / "static"
            / product.image
        )

        if existing.exists():

            print(
                "📷 تصویر قبلی موجود است:"
            )

            print(
                "   ",
                product.image,
            )

            print(
                "⏭️ بدون تغییر"
            )

            return "existing"

    source = SOURCES.get(name)

    if not source:

        print(
            "⚠️ منبع دقیق ندارد"
        )

        return "skipped"

    print(
        "🌐",
        source,
    )

    try:

        response = session.get(
            source,
            timeout=TIMEOUT,
        )

        if response.status_code != 200:

            print(
                "❌ HTTP:",
                response.status_code,
            )

            return "failed"

    except Exception as error:

        print(
            "❌ اتصال:",
            error,
        )

        return "failed"

    candidates = extract_images(
        response.text,
        source,
    )

    print(
        f"🔎 {len(candidates)} تصویر پیدا شد"
    )

    # امتیازدهی
    for item in candidates:

        item["score"] = score_image(
            item,
            name,
        )

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    # فقط چند کاندیدای برتر
    for item in candidates[:10]:

        print(
            f"   ⭐ {item['score']:>3} "
            f"{item['url'][:120]}"
        )

    # --------------------------------------------------------
    # دانلود
    # --------------------------------------------------------

    for item in candidates:

        # حداقل امتیاز
        if item["score"] < 8:
            continue

        print(
            "⬇️ دانلود:",
            item["url"][:120],
        )

        data = download(
            item["url"]
        )

        if not data:
            continue

        filename = make_filename(
            product
        )

        output = (
            PRODUCT_DIR
            / filename
        )

        with open(
            output,
            "wb",
        ) as file:

            file.write(data)

        relative = (
            f"uploads/products/{filename}"
        )

        product.image = relative

        db.session.commit()

        print()
        print(
            "✅ تصویر ثبت شد"
        )

        print(
            "📁",
            relative,
        )

        return "success"

    print(
        "❌ تصویر قابل اعتماد پیدا نشد"
    )

    return "failed"


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("🛒 KHARIDINO")
    print("🖼️ EXACT PRODUCT IMAGE DOWNLOADER")
    print("=" * 70)

    with app.app_context():

        products = (
            Product.query
            .order_by(Product.id)
            .all()
        )

        success = 0
        existing = 0
        skipped = 0
        failed = 0

        for product in products:

            result = process_product(
                product
            )

            if result == "success":
                success += 1

            elif result == "existing":
                existing += 1

            elif result == "skipped":
                skipped += 1

            else:
                failed += 1

            time.sleep(1)

        print()
        print("=" * 70)
        print("📊 نتیجه")
        print("=" * 70)

        print(
            "✅ جدید:",
            success,
        )

        print(
            "📷 قبلی:",
            existing,
        )

        print(
            "⏭️ بدون منبع:",
            skipped,
        )

        print(
            "❌ ناموفق:",
            failed,
        )

        print("=" * 70)


if __name__ == "__main__":
    main()