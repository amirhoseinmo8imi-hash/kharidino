from playwright.sync_api import sync_playwright
from urllib.parse import quote
import json
import re


# =========================================================
# KHARIDINO GOOGLE IMAGES EXTRACTOR
# =========================================================

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

SEARCH_QUERY = "Galaxy S24"

SEARCH_URL = (
    "https://www.google.com/search"
    "?tbm=isch"
    "&q=" + quote(SEARCH_QUERY)
)


def clean_url(url):
    """تمیز کردن URL"""

    if not url:
        return None

    url = url.strip()

    # حذف URLهای غیرقابل استفاده
    if url.startswith("data:"):
        return None

    if url.startswith("blob:"):
        return None

    if not url.startswith("http"):
        return None

    return url


def add_result(results, url):
    """اضافه کردن URL بدون تکرار"""

    url = clean_url(url)

    if not url:
        return

    if url not in results:
        results.append(url)


with sync_playwright() as p:

    print("")
    print("=" * 70)
    print("KHARIDINO GOOGLE IMAGES EXTRACTOR")
    print("=" * 70)

    print("")
    print("مسیر Chrome:")
    print(CHROME_PATH)

    print("")
    print("در حال اجرای Chrome...")

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
            "width": 1400,
            "height": 900,
        },
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        ),
    )

    page = context.new_page()

    print("")
    print("در حال باز کردن Google Images...")

    try:

        page.goto(
            SEARCH_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

    except Exception as e:

        print("")
        print("⚠️ خطا هنگام باز کردن Google:")
        print(e)

    page.wait_for_timeout(7000)

    print("")
    print("✅ Google Images باز شد.")

    print("")
    print("URL فعلی:")
    print(page.url)

    print("")
    print("عنوان صفحه:")
    print(page.title())

    # =====================================================
    # اسکرول برای بارگذاری تصاویر بیشتر
    # =====================================================

    print("")
    print("در حال اسکرول صفحه برای بارگذاری تصاویر...")

    for i in range(8):

        print(
            f"اسکرول {i + 1}/8 ..."
        )

        page.mouse.wheel(
            0,
            1800
        )

        page.wait_for_timeout(1800)

    # کمی برگشت به بالا
    page.mouse.wheel(
        0,
        -1000
    )

    page.wait_for_timeout(2000)

    # =====================================================
    # استخراج URLها
    # =====================================================

    print("")
    print("=" * 70)
    print("شروع استخراج تصاویر")
    print("=" * 70)

    results = []

    # =====================================================
    # METHOD 1
    # استخراج img
    # =====================================================

    print("")
    print("روش 1: استخراج تگ‌های IMG...")

    try:

        images = page.locator("img")

        count = images.count()

        print(
            "تعداد تگ‌های IMG:",
            count
        )

        for i in range(count):

            try:

                img = images.nth(i)

                src = img.get_attribute("src")

                add_result(
                    results,
                    src
                )

                srcset = img.get_attribute(
                    "srcset"
                )

                if srcset:

                    parts = srcset.split(",")

                    for part in parts:

                        url = part.strip().split(" ")[0]

                        add_result(
                            results,
                            url
                        )

            except Exception:
                continue

    except Exception as e:

        print(
            "خطا در روش IMG:",
            e
        )

    # =====================================================
    # METHOD 2
    # استخراج با JavaScript
    # =====================================================

    print("")
    print("روش 2: بررسی DOM با JavaScript...")

    try:

        js_results = page.evaluate(
            """
            () => {

                const found = [];

                function add(value) {

                    if (!value) return;

                    if (
                        typeof value !== "string"
                    ) {
                        return;
                    }

                    value = value.trim();

                    if (
                        value.startsWith("http")
                    ) {
                        found.push(value);
                    }
                }

                // IMG
                document.querySelectorAll("img").forEach(
                    img => {

                        add(img.src);

                        add(
                            img.getAttribute("data-src")
                        );

                        add(
                            img.getAttribute("data-iurl")
                        );

                        add(
                            img.getAttribute("data-original")
                        );

                        const srcset =
                            img.getAttribute("srcset");

                        if (srcset) {

                            srcset
                                .split(",")
                                .forEach(
                                    item => {

                                        add(
                                            item
                                                .trim()
                                                .split(" ")[0]
                                        );

                                    }
                                );

                        }

                    }
                );

                // همه عناصر دارای background-image
                document.querySelectorAll("*").forEach(
                    element => {

                        const style =
                            window.getComputedStyle(
                                element
                            );

                        const bg =
                            style.backgroundImage;

                        if (
                            bg &&
                            bg !== "none"
                        ) {

                            const matches =
                                bg.match(
                                    /url\\(["']?(.*?)["']?\\)/g
                                );

                            if (matches) {

                                matches.forEach(
                                    item => {

                                        let value =
                                            item
                                                .replace(
                                                    /^url\\(["']?/,
                                                    ""
                                                )
                                                .replace(
                                                    /["']?\\)$/,
                                                    ""
                                                );

                                        add(value);

                                    }
                                );

                            }

                        }

                    }
                );

                return found;

            }
            """
        )

        print(
            "تعداد URLهای JavaScript:",
            len(js_results)
        )

        for url in js_results:

            add_result(
                results,
                url
            )

    except Exception as e:

        print(
            "خطا در JavaScript:",
            e
        )

    # =====================================================
    # METHOD 3
    # Performance Resource Timing
    # =====================================================

    print("")
    print(
        "روش 3: بررسی منابعی که Chrome لود کرده..."
    )

    try:

        performance_entries = page.evaluate(
            """
            () => {

                return performance
                    .getEntriesByType("resource")
                    .map(
                        item => item.name
                    );

            }
            """
        )

        print(
            "تعداد منابع:",
            len(performance_entries)
        )

        for url in performance_entries:

            url_lower = url.lower()

            if any(
                x in url_lower
                for x in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                    ".gif",
                    ".avif",
                    "gstatic.com",
                    "googleusercontent.com",
                    "encrypted-tbn"
                ]
            ):

                add_result(
                    results,
                    url
                )

    except Exception as e:

        print(
            "خطا در Performance:",
            e
        )

    # =====================================================
    # حذف URLهای واضحاً غیرتصویری
    # =====================================================

    filtered_results = []

    bad_words = [
        "logo",
        "icon",
        "favicon",
        "sprite",
        "googlelogo",
        "searchbox",
        "avatar",
    ]

    for url in results:

        low = url.lower()

        if any(
            word in low
            for word in bad_words
        ):
            continue

        if url not in filtered_results:

            filtered_results.append(
                url
            )

    results = filtered_results

    # =====================================================
    # نمایش نتایج
    # =====================================================

    print("")
    print("=" * 70)
    print("IMAGE URLS")
    print("=" * 70)

    if not results:

        print("")
        print("❌ هیچ URL تصویری پیدا نشد.")

        print("")
        print("برای بررسی بیشتر:")
        print("صفحه باز است و باید Google Images را ببینی.")

    else:

        for i, url in enumerate(
            results[:50],
            start=1
        ):

            print("")
            print(
                f"{i}. {url}"
            )

    print("")
    print("=" * 70)

    print(
        "تعداد URLهای استخراج‌شده:",
        len(results)
    )

    print("=" * 70)

    # =====================================================
    # ذخیره در فایل
    # =====================================================

    output_file = "google_image_urls.txt"

    try:

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            for url in results:

                f.write(
                    url + "\n"
                )

        print("")
        print(
            f"✅ URLها در فایل {output_file} ذخیره شدند."
        )

    except Exception as e:

        print("")
        print(
            "⚠️ خطا در ذخیره فایل:",
            e
        )

    # =====================================================
    # نگه داشتن Chrome
    # =====================================================

    print("")
    print("Chrome تا 5 ثانیه باز می‌ماند...")

    page.wait_for_timeout(
        5000
    )

    browser.close()

    print("")
    print("✅ عملیات تمام شد.")