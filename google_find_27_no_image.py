import re
import time
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from playwright.sync_api import sync_playwright


BASE_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
    / "google_candidates"
    / "no_image_27"
)

RESULTS_FILE = (
    BASE_DIR
    / "no_image_27_results.txt"
)

CHROME_PATH = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)

MAX_IMAGES_PER_PRODUCT = 15
GOOGLE_SCROLLS = 5
WAIT_AFTER_SEARCH = 2


PRODUCTS = [
    (12, "Lenovo IdeaPad Slim 3"),
    (14, "Seagate Expansion Portable 2TB"),
    (16, "Baseus Simple Mini3 Wireless Charger"),
    (20, "Sony WH-1000XM5"),
    (21, "Sony PlayStation 5 Slim"),
    (23, "Sony DualSense Wireless Controller"),
    (24, "Samsung 55 Inch 4K Smart TV"),
    (25, "LG 55 Inch 4K Smart TV"),
    (26, "Samsung Galaxy Watch 6"),
    (27, "Apple Watch Series 9"),
    (28, "Vidhas VIR-5637 Sandwich Maker"),
    (29, "Philips Espresso Machine"),
    (30, "Bosch Vacuum Cleaner"),
    (31, "Hiska H5107 Hair Brush"),
    (32, "Nivea Sun SPF 50"),
    (33, "کتاب بیلیجی"),
    (34, "دفتر یادداشت 100 برگ"),
    (35, "Nike Running Shoes"),
    (36, "قمقمه ورزشی 750ml"),
    (37, "Bosch Cordless Drill"),
    (38, "Ronix Tool Set"),
    (39, "Bosch Car Air Filter"),
    (40, "Car Phone Holder"),
    (41, "تیشرت نخی مردانه"),
    (42, "کفش اسپرت مردانه"),
    (43, "قهوه فوری کلاسیک"),
    (44, "چای سیاه ایرانی"),
]


BAD_WORDS = [
    "favicon",
    "googlelogo",
    "google.com/recaptcha",
    "recaptcha",
    "captcha",
    "sprite",
    "avatar",
    "translate",
    "settings",
    "logo",
]


def safe_name(name):
    name = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "-", name.strip())
    return name[:80]


def valid_url(url):
    if not url:
        return False

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        return False

    lower = url.lower()

    for bad in BAD_WORDS:
        if bad in lower:
            return False

    return True


def validate_image(path):
    try:
        with Image.open(path) as img:

            width, height = img.size

            if width < 120 or height < 120:
                return False

            img.verify()

        return True

    except Exception:
        return False


def save_image(page, url, output_path):

    try:

        response = page.request.get(
            url,
            timeout=15000
        )

        if not response.ok:
            return False

        body = response.body()

        if len(body) < 1000:
            return False

        output_path.write_bytes(body)

        if not validate_image(output_path):
            try:
                output_path.unlink()
            except Exception:
                pass

            return False

        return True

    except Exception:
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception:
            pass

        return False


def extract_google_images(page):

    urls = []

    # ---------------------------------------------------------
    # IMG elements
    # ---------------------------------------------------------

    try:

        img_urls = page.locator("img").evaluate_all(
            """
            imgs => imgs.map(img => ({
                src: img.src,
                dataSrc: img.getAttribute('data-src')
            }))
            """
        )

        for item in img_urls:

            for key in ["src", "dataSrc"]:

                url = item.get(key)

                if valid_url(url):
                    urls.append(url)

    except Exception:
        pass


    # ---------------------------------------------------------
    # DOM HTML
    # ---------------------------------------------------------

    try:

        html = page.content()

        found = re.findall(
            r'https?://[^"\'<>\\ ]+',
            html
        )

        for url in found:

            url = url.replace("\\u003d", "=")
            url = url.replace("\\u0026", "&")

            if valid_url(url):
                urls.append(url)

    except Exception:
        pass


    # ---------------------------------------------------------
    # Remove duplicates
    # ---------------------------------------------------------

    unique = []

    seen = set()

    for url in urls:

        if url not in seen:

            seen.add(url)
            unique.append(url)

    return unique


def search_product(page, product_name):

    query = quote(
        product_name + " official product"
    )

    url = (
        "https://www.google.com/search"
        "?tbm=isch"
        "&q="
        + query
    )

    print()
    print("🔎 SEARCH:", product_name)

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

    except Exception as e:

        print("⚠️ PAGE ERROR:", e)

    time.sleep(WAIT_AFTER_SEARCH)

    # Scroll to load more images
    for _ in range(GOOGLE_SCROLLS):

        try:
            page.mouse.wheel(0, 1800)
        except Exception:
            pass

        time.sleep(0.7)

    urls = extract_google_images(page)

    print(
        "🌐 Google image URLs found:",
        len(urls)
    )

    return urls


def process_product(page, product_id, product_name):

    product_dir = (
        OUTPUT_DIR
        / f"{product_id:02}_{safe_name(product_name)}"
    )

    product_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    urls = search_product(
        page,
        product_name
    )

    saved = []

    for index, url in enumerate(
        urls[:MAX_IMAGES_PER_PRODUCT],
        start=1
    ):

        output_path = (
            product_dir
            / f"candidate_{index:02}.jpg"
        )

        print(
            f"   ⬇️ [{index}] downloading..."
        )

        if save_image(
            page,
            url,
            output_path
        ):

            saved.append(
                {
                    "index": index,
                    "path": str(
                        output_path.relative_to(BASE_DIR)
                    ),
                    "url": url,
                }
            )

            print(
                "      ✅ saved"
            )

        else:

            print(
                "      ❌ invalid/failed"
            )

    return saved


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    report = []

    print()
    print("=" * 75)
    print("KHARIDINO - GOOGLE IMAGE FINDER")
    print("27 PRODUCTS WITHOUT IMAGE")
    print("=" * 75)
    print()
    print("⚠️ OpenAI API will NOT be used.")
    print("⚠️ AI verification will be done later.")
    print()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        context = browser.new_context(
            viewport={
                "width": 1366,
                "height": 900,
            },
            locale="en-US",
        )

        page = context.new_page()

        for number, (
            product_id,
            product_name
        ) in enumerate(PRODUCTS, start=1):

            print()
            print("=" * 75)

            print(
                f"PRODUCT {number}/{len(PRODUCTS)}"
            )

            print(
                f"ID: {product_id}"
            )

            print(
                f"NAME: {product_name}"
            )

            print("=" * 75)

            try:

                candidates = process_product(
                    page,
                    product_id,
                    product_name
                )

                report.append(
                    {
                        "id": product_id,
                        "name": product_name,
                        "candidates": len(candidates),
                    }
                )

                print()
                print(
                    f"✅ Saved candidates: {len(candidates)}"
                )

            except Exception as e:

                print(
                    "❌ PRODUCT ERROR:",
                    e
                )

                report.append(
                    {
                        "id": product_id,
                        "name": product_name,
                        "candidates": 0,
                        "error": str(e),
                    }
                )

            time.sleep(1)

        browser.close()


    # ---------------------------------------------------------
    # Save report
    # ---------------------------------------------------------

    lines = []

    lines.append(
        "=" * 75
    )

    lines.append(
        "KHARIDINO - GOOGLE IMAGE FINDER REPORT"
    )

    lines.append(
        "=" * 75
    )

    lines.append(
        "OpenAI API: NOT USED"
    )

    lines.append(
        f"Products: {len(PRODUCTS)}"
    )

    lines.append("")


    total_candidates = 0

    for item in report:

        count = item.get(
            "candidates",
            0
        )

        total_candidates += count

        lines.append(
            f"{item['id']:02} | "
            f"{item['name']} | "
            f"{count} candidates"
        )

        if item.get("error"):

            lines.append(
                f"     ERROR: {item['error']}"
            )


    lines.append("")

    lines.append(
        f"TOTAL CANDIDATE IMAGES: "
        f"{total_candidates}"
    )

    lines.append("")

    lines.append(
        "Candidates directory:"
    )

    lines.append(
        str(OUTPUT_DIR)
    )

    report_text = "\n".join(lines)

    RESULTS_FILE.write_text(
        report_text,
        encoding="utf-8"
    )

    print()
    print("=" * 75)
    print("🎉 DONE")
    print("=" * 75)

    print(
        "📸 Total candidates:",
        total_candidates
    )

    print(
        "📄 Report:",
        RESULTS_FILE
    )

    print(
        "📁 Images:",
        OUTPUT_DIR
    )

    print("=" * 75)


if __name__ == "__main__":
    main()