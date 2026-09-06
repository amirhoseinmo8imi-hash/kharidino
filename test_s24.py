import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


BASE_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = BASE_DIR / "static" / "uploads" / "products"

PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://www.samsung.com/az/smartphones/galaxy-s24/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    )
}


print("=" * 60)
print("KHARIDINO - S24 IMAGE TEST")
print("=" * 60)

print("🌐 دریافت صفحه Samsung...")

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

print("HTTP:", response.status_code)
print("Page size:", len(response.content))

if response.status_code != 200:
    raise SystemExit("❌ دریافت صفحه ناموفق بود.")


soup = BeautifulSoup(
    response.text,
    "html.parser"
)


image_urls = []


# ---------------------------------------------------------
# پیدا کردن تصاویر از img
# ---------------------------------------------------------

for img in soup.find_all("img"):

    for attr in ["src", "data-src", "data-lazy-src"]:

        value = img.get(attr)

        if value and value.startswith("http"):

            image_urls.append(value)


# ---------------------------------------------------------
# پیدا کردن URL های تصویر داخل HTML
# ---------------------------------------------------------

for match in re.findall(
    r'https?://[^"\']+\.(?:jpg|jpeg|png|webp)',
    response.text,
    re.IGNORECASE
):

    image_urls.append(match)


# حذف تکراری‌ها
image_urls = list(dict.fromkeys(image_urls))

print("🖼️ تصاویر پیدا شده:", len(image_urls))


# ---------------------------------------------------------
# دانلود و بررسی تصاویر
# ---------------------------------------------------------

saved = False

for index, image_url in enumerate(image_urls, start=1):

    print()
    print(f"[{index}] {image_url[:120]}")

    try:

        r = requests.get(
            image_url,
            headers=HEADERS,
            timeout=30
        )

        if r.status_code != 200:
            print("  ❌ HTTP:", r.status_code)
            continue

        image = Image.open(
            BytesIO(r.content)
        )

        image = image.convert("RGB")

        width, height = image.size

        print(
            f"  📐 اندازه: {width} x {height}"
        )

        if width < 500 or height < 500:
            print("  ⏭️ تصویر خیلی کوچک است.")
            continue

        output = PRODUCT_DIR / "galaxy-s24.jpg"

        image.save(
            output,
            "JPEG",
            quality=92,
            optimize=True
        )

        print()
        print("✅ تصویر ذخیره شد:")
        print(output)

        saved = True
        break

    except Exception as e:

        print(
            "  ❌ خطا:",
            str(e)[:200]
        )


print()
print("=" * 60)

if saved:
    print("🎉 تست موفق بود!")
    print("Galaxy S24 image آماده است.")
else:
    print("❌ هیچ تصویر مناسبی پیدا نشد.")

print("=" * 60)