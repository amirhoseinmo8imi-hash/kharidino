import ast
import json
import time
from pathlib import Path

import requests

from ai_product_image import check_product_image


# =========================================================
# KHARIDINO
# GOOGLE IMAGES + AI PRODUCT VERIFICATION
# =========================================================

PRODUCT_NAME = "Galaxy S24"

URLS_FILE = Path("google_image_urls.txt")

DOWNLOAD_DIR = Path(
    "static/uploads/products/google_candidates"
)

MAX_IMAGES = 30

MIN_CONFIDENCE = 85


# =========================================================
# ساخت پوشه
# =========================================================

DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# خواندن URLهای Google
# =========================================================

if not URLS_FILE.exists():

    raise FileNotFoundError(
        "فایل google_image_urls.txt پیدا نشد."
    )


with open(
    URLS_FILE,
    "r",
    encoding="utf-8"
) as f:

    urls = [
        line.strip()
        for line in f
        if line.strip()
    ]


print("")
print("=" * 70)
print("KHARIDINO GOOGLE + AI PRODUCT FINDER")
print("=" * 70)

print("")
print("محصول:")
print(PRODUCT_NAME)

print("")
print("تعداد URLهای Google:")
print(len(urls))

print("")
print("تعداد تصاویر برای بررسی:")
print(MAX_IMAGES)

print("")
print("=" * 70)


# =========================================================
# Session
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "image/avif,image/webp,image/apng,"
        "image/svg+xml,image/*,*/*;q=0.8"
    ),
    "Referer": "https://www.google.com/",
})


# =========================================================
# دانلود تصویر
# =========================================================

def download_image(url, output_path):

    try:

        response = session.get(
            url,
            timeout=20
        )

        if response.status_code != 200:

            print(
                f"   ❌ HTTP {response.status_code}"
            )

            return False

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if "image" not in content_type:

            print(
                "   ❌ فایل تصویر نیست:"
            )

            print(
                f"   {content_type}"
            )

            return False

        if len(response.content) < 1000:

            print(
                "   ❌ تصویر خیلی کوچک است."
            )

            return False

        output_path.write_bytes(
            response.content
        )

        return True

    except Exception as e:

        print(
            "   ❌ خطای دانلود:",
            e
        )

        return False


# =========================================================
# نتایج AI
# =========================================================

results = []


# =========================================================
# پردازش تصاویر
# =========================================================

for index, url in enumerate(
    urls[:MAX_IMAGES],
    start=1
):

    print("")
    print("-" * 70)

    print(
        f"[{index}/{MAX_IMAGES}]"
    )

    print(
        "دانلود تصویر..."
    )

    filename = (
        f"candidate_{index:03d}.jpg"
    )

    image_path = (
        DOWNLOAD_DIR / filename
    )

    success = download_image(
        url,
        image_path
    )

    if not success:

        continue

    print(
        "   ✅ دانلود شد"
    )

    # =====================================================
    # بررسی با AI
    # =====================================================

    print(
        "   🤖 در حال بررسی با AI..."
    )

    try:

        ai_result = check_product_image(
            PRODUCT_NAME,
            image_path
        )

        # =================================================
        # تبدیل نتیجه AI از String به Dictionary
        # =================================================

        if isinstance(
            ai_result,
            str
        ):

            raw_result = ai_result.strip()

            try:

                ai_result = json.loads(
                    raw_result
                )

            except json.JSONDecodeError:

                try:

                    ai_result = ast.literal_eval(
                        raw_result
                    )

                except Exception:

                    print("")
                    print(
                        "   ❌ نتیجه AI قابل تبدیل نیست:"
                    )

                    print(
                        raw_result
                    )

                    continue

        # =================================================
        # اطمینان از Dictionary بودن
        # =================================================

        if not isinstance(
            ai_result,
            dict
        ):

            print("")
            print(
                "   ❌ فرمت نتیجه AI نامعتبر است."
            )

            print(
                "   نوع:",
                type(ai_result).__name__
            )

            continue

        print("")
        print(
            "   AI RESULT:"
        )

        print(
            json.dumps(
                ai_result,
                ensure_ascii=False,
                indent=2
            )
        )

    except Exception as e:

        print(
            "   ❌ خطای AI:"
        )

        print(e)

        continue

    # =====================================================
    # استخراج نتیجه
    # =====================================================

    match = bool(
        ai_result.get(
            "match",
            False
        )
    )

    try:

        confidence = int(
            ai_result.get(
                "confidence",
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):

        confidence = 0

    reason = str(
        ai_result.get(
            "reason",
            ""
        )
    )

    result = {
        "index": index,
        "url": url,
        "image": str(image_path),
        "match": match,
        "confidence": confidence,
        "reason": reason,
    }

    results.append(
        result
    )

    # =====================================================
    # نتیجه قابل قبول
    # =====================================================

    if (
        match
        and
        confidence >= MIN_CONFIDENCE
    ):

        print("")
        print(
            "   🟢 MATCH"
        )

        print(
            f"   Confidence: {confidence}%"
        )

    else:

        print("")
        print(
            "   🔴 REJECT"
        )

        print(
            f"   Confidence: {confidence}%"
        )

    time.sleep(0.5)


# =========================================================
# مرتب‌سازی
# =========================================================

results.sort(
    key=lambda x: (
        x["match"],
        x["confidence"]
    ),
    reverse=True
)


# =========================================================
# ذخیره نتایج
# =========================================================

results_file = (
    DOWNLOAD_DIR /
    "ai_results.json"
)

with open(
    results_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        results,
        f,
        ensure_ascii=False,
        indent=2
    )


# =========================================================
# پیدا کردن بهترین تصویر
# =========================================================

valid_results = [
    item
    for item in results
    if (
        item["match"]
        and
        item["confidence"] >= MIN_CONFIDENCE
    )
]


print("")
print("")
print("=" * 70)
print("FINAL RESULT")
print("=" * 70)


if not valid_results:

    print("")
    print(
        "❌ هیچ تصویر قابل اعتمادی پیدا نشد."
    )

else:

    best = valid_results[0]

    print("")
    print(
        "🏆 بهترین تصویر پیدا شد."
    )

    print("")
    print(
        "Product:"
    )

    print(
        PRODUCT_NAME
    )

    print("")
    print(
        "Confidence:"
    )

    print(
        f"{best['confidence']}%"
    )

    print("")
    print(
        "Reason:"
    )

    print(
        best["reason"]
    )

    print("")
    print(
        "Image:"
    )

    print(
        best["image"]
    )

    print("")
    print(
        "Google URL:"
    )

    print(
        best["url"]
    )


# =========================================================
# آمار
# =========================================================

matched = [
    x
    for x in results
    if x["match"]
]

rejected = [
    x
    for x in results
    if not x["match"]
]


print("")
print("=" * 70)
print("STATISTICS")
print("=" * 70)

print("")
print(
    "تصاویر دانلود و بررسی‌شده:",
    len(results)
)

print(
    "تصاویر تأییدشده:",
    len(matched)
)

print(
    "تصاویر ردشده:",
    len(rejected)
)

print("")
print(
    "حداقل Confidence:",
    f"{MIN_CONFIDENCE}%"
)

print("")
print(
    "نتایج ذخیره شدند در:"
)

print(
    results_file
)

print("")
print("=" * 70)
print("✅ عملیات تمام شد.")
print("=" * 70)