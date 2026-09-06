# ============================================================
# KHARIDINO
# Google Images + AI Product Image Finder
# RESUME / SAFE / RATE-LIMIT PROTECTED
# ============================================================

import os
import re
import json
import time
import shutil
from pathlib import Path
from datetime import datetime

from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app import app, db, Product
from ai_product_image import check_product_image


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

OUTPUT_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
    / "google_candidates"
)

RESULTS_FILE = OUTPUT_DIR / "all_products_results.json"

MIN_CONFIDENCE = 90

# حداکثر 10 عکس برای هر محصول به AI
MAX_AI_CANDIDATES = 3

# حداکثر URL از Google
MAX_GOOGLE_IMAGES = 30

GOOGLE_SCROLLS = 6

# فاصله بین درخواست‌ها
AI_DELAY = 2


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# RESULT FILE
# ============================================================

def load_results():
    """
    فایل نتایج قبلی را می‌خواند.

    نسخه قدیمی:
        list

    نسخه جدید:
        dict

    هر دو پشتیبانی می‌شوند.
    """

    if not RESULTS_FILE.exists():
        return {}

    try:

        with open(
            RESULTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        # ----------------------------------------
        # نسخه قدیمی = List
        # ----------------------------------------

        if isinstance(data, list):

            converted = {}

            for item in data:

                if not isinstance(item, dict):
                    continue

                product_id = item.get("id")

                if product_id is None:
                    continue

                converted[str(product_id)] = item

            print(
                f"📂 نتایج قدیمی پیدا شد: "
                f"{len(converted)} محصول"
            )

            return converted

        # ----------------------------------------
        # نسخه جدید = Dict
        # ----------------------------------------

        if isinstance(data, dict):
            return data

    except Exception as e:

        print(
            f"⚠️ خطا در خواندن results: {e}"
        )

    return {}


def save_results(results):

    temp_file = RESULTS_FILE.with_suffix(
        ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(
        RESULTS_FILE
    )


# ============================================================
# HELPERS
# ============================================================

def slugify(text):

    text = str(text).strip()

    text = re.sub(
        r"[^\w\s-]",
        "",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"[\s_-]+",
        "-",
        text
    )

    return text.strip("-")[:80]


def is_rate_limit_error(error):

    text = str(error).lower()

    keywords = [
        "429",
        "rate limit",
        "rate_limit",
        "requests per day",
        "rpd",
        "quota",
        "too many requests",
    ]

    return any(
        word in text
        for word in keywords
    )


def parse_ai_result(result):

    if isinstance(result, dict):
        return result

    if isinstance(result, str):

        text = result.strip()

        try:
            return json.loads(text)
        except Exception:
            pass

        try:
            import ast

            return ast.literal_eval(text)

        except Exception:
            pass

    return {}


# ============================================================
# IMAGE VALIDATION
# ============================================================

def validate_image(image_path):

    try:

        with Image.open(
            image_path
        ) as img:

            img.verify()

        return True

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):

        return False


def convert_image_to_jpeg(
    image_path
):

    try:

        with Image.open(
            image_path
        ) as img:

            img.load()

            # عکس خیلی کوچک
            if (
                img.width < 120
                or img.height < 120
            ):

                return False

            img = img.convert(
                "RGB"
            )

            temp_path = (
                image_path.with_suffix(
                    ".tmp.jpg"
                )
            )

            img.save(
                temp_path,
                "JPEG",
                quality=92,
                optimize=True
            )

        temp_path.replace(
            image_path
        )

        return True

    except Exception as e:

        print(
            f"      ⚠️ تبدیل تصویر:"
            f" {e}"
        )

        return False


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(
    page,
    url,
    output_path
):

    try:

        response = page.request.get(
            url,
            timeout=15000
        )

        if not response.ok:
            return False

        body = response.body()

        if (
            not body
            or len(body) < 1000
        ):
            return False

        with open(
            output_path,
            "wb"
        ) as f:

            f.write(body)

        # ----------------------------------------
        # Validate
        # ----------------------------------------

        if not validate_image(
            output_path
        ):

            try:
                output_path.unlink()
            except Exception:
                pass

            return False

        # ----------------------------------------
        # Convert
        # ----------------------------------------

        if not convert_image_to_jpeg(
            output_path
        ):

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


# ============================================================
# GOOGLE IMAGES
# ============================================================

def extract_google_images(
    page,
    product_name
):

    query = (
        f"{product_name} "
        f"official product"
    )

    print()
    print(
        f"🔎 Google Images: {query}"
    )

    search_url = (
        "https://www.google.com/search"
        "?tbm=isch"
        "&q="
        + query.replace(
            " ",
            "+"
        )
    )

    try:

        page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        time.sleep(3)

    except Exception as e:

        print(
            f"⚠️ Google error: {e}"
        )

        return []

    # ----------------------------------------
    # Scroll
    # ----------------------------------------

    for _ in range(
        GOOGLE_SCROLLS
    ):

        try:

            page.mouse.wheel(
                0,
                1800
            )

            time.sleep(
                0.8
            )

        except Exception:
            pass

    urls = set()

    # ----------------------------------------
    # IMG
    # ----------------------------------------

    try:

        img_urls = (
            page.locator(
                "img"
            ).evaluate_all(
                """
                imgs => imgs
                .map(img =>
                    img.src ||
                    img.getAttribute(
                        'data-src'
                    )
                )
                .filter(Boolean)
                """
            )
        )

        for url in img_urls:

            if isinstance(
                url,
                str
            ):

                urls.add(url)

    except Exception:
        pass

    # ----------------------------------------
    # HTML
    # ----------------------------------------

    try:

        html = page.content()

        found = re.findall(
            r'https?://[^"\'\\\s<>]+',
            html
        )

        for url in found:

            if (
                "gstatic.com"
                in url
            ):

                urls.add(url)

            elif (
                "googleusercontent.com"
                in url
            ):

                urls.add(url)

    except Exception:
        pass

    # ----------------------------------------
    # Filter
    # ----------------------------------------

    bad_words = [
        "favicon",
        "logo",
        "sprite",
        "googlelogo",
        "translate",
        "settings",
        "avatar",
        "recaptcha",
        "captcha",
        "xjs",
        "google.com/recaptcha",
    ]

    clean_urls = []

    for url in urls:

        if not isinstance(
            url,
            str
        ):
            continue

        if not url.startswith(
            "http"
        ):
            continue

        lower = url.lower()

        if any(
            word in lower
            for word in bad_words
        ):
            continue

        if url in clean_urls:
            continue

        clean_urls.append(
            url
        )

        if (
            len(clean_urls)
            >= MAX_GOOGLE_IMAGES
        ):
            break

    print(
        f"   📸 URLs معتبر: "
        f"{len(clean_urls)}"
    )

    return clean_urls


# ============================================================
# AI PRODUCT CHECK
# ============================================================

def find_best_image(
    page,
    product,
    product_dir
):

    product_name = product.name

    urls = extract_google_images(
        page,
        product_name
    )

    if not urls:

        return {
            "status":
                "no_google_images",
            "product_id":
                product.id,
            "product_name":
                product_name,
        }

    ai_checked = 0
    invalid_images = 0

    best = None

    for index, url in enumerate(
        urls,
        start=1
    ):

        if (
            ai_checked
            >= MAX_AI_CANDIDATES
        ):

            print(
                f"   ⏭️ سقف "
                f"{MAX_AI_CANDIDATES} "
                f"درخواست AI رسید."
            )

            break

        candidate_path = (
            product_dir
            / f"candidate_{index:03d}.jpg"
        )

        print(
            f"   [{index}/"
            f"{len(urls)}]"
            f" Download..."
        )

        # ----------------------------------------
        # Download
        # ----------------------------------------

        if not download_image(
            page,
            url,
            candidate_path
        ):

            invalid_images += 1

            print(
                "      ❌ "
                "تصویر خراب/نامعتبر"
            )

            continue

        print(
            "      ✅ تصویر معتبر"
        )

        # ----------------------------------------
        # AI request
        # ----------------------------------------

        ai_checked += 1

        print(
            f"      🤖 AI "
            f"{ai_checked}/"
            f"{MAX_AI_CANDIDATES}"
        )

        try:

            raw = check_product_image(
                product_name,
                candidate_path
            )

        except Exception as e:

            if is_rate_limit_error(
                e
            ):

                print()
                print(
                    "🛑 RATE LIMIT"
                )

                raise RuntimeError(
                    "RATE_LIMIT_STOP"
                )

            print(
                f"      ⚠️ AI ERROR: "
                f"{e}"
            )

            continue

        result = parse_ai_result(
            raw
        )

        if not result:

            print(
                "      ⚠️ خروجی AI نامعتبر"
            )

            continue

        match = bool(
            result.get(
                "match",
                False
            )
        )

        try:

            confidence = int(
                result.get(
                    "confidence",
                    0
                )
            )

        except Exception:

            confidence = 0

        reason = str(
            result.get(
                "reason",
                ""
            )
        )

        print(
            f"      "
            f"{'✅ MATCH' if match else '❌ REJECT'}"
            f" | {confidence}%"
        )

        if reason:

            print(
                f"      {reason}"
            )

        if not match:
            continue

        if (
            confidence
            < MIN_CONFIDENCE
        ):

            print(
                f"      ⚠️ کمتر از "
                f"{MIN_CONFIDENCE}%"
            )

            continue

        candidate = {
            "candidate":
                str(candidate_path),
            "google_url":
                url,
            "confidence":
                confidence,
            "reason":
                reason,
        }

        if (
            best is None
            or confidence
            > best["confidence"]
        ):

            best = candidate

        # ----------------------------------------
        # Very strong result
        # ----------------------------------------

        if confidence >= 98:

            print(
                "      ⭐ اطمینان بسیار بالا"
            )

            break

        time.sleep(
            AI_DELAY
        )

    # ----------------------------------------
    # No match
    # ----------------------------------------

    if best is None:

        return {
            "status":
                "no_match",
            "product_id":
                product.id,
            "product_name":
                product_name,
            "ai_checked":
                ai_checked,
            "invalid_images":
                invalid_images,
        }

    # ----------------------------------------
    # Success
    # ----------------------------------------

    return {
        "status":
            "success",
        "product_id":
            product.id,
        "product_name":
            product_name,
        "candidate":
            best["candidate"],
        "google_url":
            best["google_url"],
        "confidence":
            best["confidence"],
        "reason":
            best["reason"],
        "ai_checked":
            ai_checked,
        "invalid_images":
            invalid_images,
    }


# ============================================================
# SAVE TO DATABASE
# ============================================================

def save_selected_image(
    product,
    result
):

    candidate = Path(
        result["candidate"]
    )

    if not candidate.exists():

        print(
            "❌ فایل انتخاب‌شده وجود ندارد."
        )

        return False

    slug = slugify(
        product.name
    )

    filename = (
        f"product_{product.id}_"
        f"{slug}_verified.jpg"
    )

    destination = (
        BASE_DIR
        / "static"
        / "uploads"
        / "products"
        / filename
    )

    try:

        shutil.copy2(
            candidate,
            destination
        )

        db_path = (
            f"uploads/products/"
            f"{filename}"
        )

        product.image = db_path

        db.session.commit()

        print()
        print(
            "   🎯 تصویر انتخاب شد"
        )

        print(
            f"   Confidence: "
            f"{result['confidence']}%"
        )

        print(
            f"   Saved: "
            f"{destination}"
        )

        print(
            f"   Database: "
            f"{db_path}"
        )

        return True

    except Exception as e:

        db.session.rollback()

        print(
            f"❌ DB ERROR: {e}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 65)
    print(
        "KHARIDINO "
        "GOOGLE + AI"
    )
    print("=" * 65)

    results = load_results()

    print(
        f"📁 نتایج قبلی: "
        f"{len(results)}"
    )

    with app.app_context():

        products = (
            Product.query
            .order_by(Product.id)
            .all()
        )

        print(
            f"📦 محصولات: "
            f"{len(products)}"
        )

        # --------------------------------------------
        # Chrome
        # --------------------------------------------

        with sync_playwright() as p:

            print(
                "🌐 Starting Chrome..."
            )

            browser = p.chromium.launch(
                headless=True,
                executable_path=CHROME_PATH,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 900
                },
                user_agent=(
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/139.0.0.0 "
                    "Safari/537.36"
                ),
            )

            page = context.new_page()

            # ----------------------------------------
            # Products
            # ----------------------------------------

            for number, product in enumerate(
                products,
                start=1
            ):

                key = str(
                    product.id
                )

                print()
                print("=" * 65)

                print(
                    f"PRODUCT "
                    f"{number}/"
                    f"{len(products)}"
                )

                print(
                    f"ID: "
                    f"{product.id}"
                )

                print(
                    f"NAME: "
                    f"{product.name}"
                )

                print("=" * 65)

                old = results.get(
                    key
                )

                # ==================================================
                # ALREADY SUCCESSFUL
                # ==================================================

                if isinstance(
                    old,
                    dict
                ):

                    old_success = (
                        old.get(
                            "success"
                        ) is True
                        or old.get(
                            "status"
                        ) == "success"
                    )

                    if old_success:

                        print(
                            "⏭️ قبلاً موفق بوده؛ "
                            "رد شد."
                        )

                        continue

                # ==================================================
                # EXISTING VERIFIED IMAGE
                # ==================================================

                if (
                    product.image
                    and "_verified"
                    in product.image
                ):

                    print(
                        "⏭️ تصویر verified "
                        "از قبل وجود دارد."
                    )

                    results[key] = {
                        "id":
                            product.id,
                        "name":
                            product.name,
                        "success":
                            True,
                        "confidence":
                            100,
                        "new_image":
                            product.image,
                        "reason":
                            "Existing verified image",
                    }

                    save_results(
                        results
                    )

                    continue

                # ==================================================
                # PRODUCT DIRECTORY
                # ==================================================

                product_dir = (
                    OUTPUT_DIR
                    / f"product_{product.id}"
                )

                product_dir.mkdir(
                    parents=True,
                    exist_ok=True
                )

                # ==================================================
                # FIND
                # ==================================================

                try:

                    result = find_best_image(
                        page,
                        product,
                        product_dir
                    )

                except RuntimeError as e:

                    if (
                        str(e)
                        == "RATE_LIMIT_STOP"
                    ):

                        print()
                        print(
                            "=" * 65
                        )

                        print(
                            "🛑 API RATE LIMIT"
                        )

                        print(
                            "🛑 برنامه متوقف شد."
                        )

                        print(
                            "💾 وضعیت ذخیره شد."
                        )

                        results[key] = {
                            "id":
                                product.id,
                            "name":
                                product.name,
                            "success":
                                False,
                            "status":
                                "rate_limit",
                            "stopped_at":
                                datetime.now()
                                .isoformat(),
                        }

                        save_results(
                            results
                        )

                        browser.close()

                        return

                    raise

                # ==================================================
                # SUCCESS
                # ==================================================

                if (
                    result["status"]
                    == "success"
                ):

                    saved = (
                        save_selected_image(
                            product,
                            result
                        )
                    )

                    if saved:

                        results[key] = {
                            "id":
                                product.id,
                            "name":
                                product.name,
                            "success":
                                True,
                            "confidence":
                                result[
                                    "confidence"
                                ],
                            "old_image":
                                None,
                            "new_image":
                                product.image,
                            "source":
                                result[
                                    "candidate"
                                ],
                            "google_url":
                                result[
                                    "google_url"
                                ],
                            "reason":
                                result[
                                    "reason"
                                ],
                        }

                    else:

                        result["success"] = False

                        results[key] = result

                # ==================================================
                # NO MATCH
                # ==================================================

                else:

                    results[key] = {
                        "id":
                            product.id,
                        "name":
                            product.name,
                        "success":
                            False,
                        "status":
                            result[
                                "status"
                            ],
                        "ai_checked":
                            result.get(
                                "ai_checked",
                                0
                            ),
                        "invalid_images":
                            result.get(
                                "invalid_images",
                                0
                            ),
                    }

                    print(
                        "   ❌ عکس مناسب پیدا نشد."
                    )

                # ----------------------------------------
                # Save immediately
                # ----------------------------------------

                save_results(
                    results
                )

                print(
                    "   💾 وضعیت ذخیره شد."
                )

                time.sleep(
                    1
                )

            browser.close()

    print()
    print("=" * 65)
    print(
        "🎉 پردازش تمام شد"
    )
    print("=" * 65)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
