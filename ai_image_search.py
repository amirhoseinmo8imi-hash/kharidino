from pathlib import Path

from ai_product_image import (
    download_image,
    check_product_image
)


BASE_DIR = Path(__file__).resolve().parent

TEST_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
    / "ai_test"
)

TEST_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def main():

    print("")
    print("=" * 60)
    print("KHARIDINO AI IMAGE SEARCH TEST")
    print("=" * 60)

    product_name = "Galaxy S24"

    # تصویر مستقیم رسمی Samsung Mobile Press
    image_url = (
        "https://api.samsungmobilepress.com/"
        "media-assets/galaxy-s24/"
        "Galaxy-S24-MAThumb-1440x960.jpg"
    )

    output_path = (
        TEST_DIR
        / "galaxy_s24_candidate.jpg"
    )

    print("")
    print("محصول:", product_name)
    print("")
    print("تصویر کاندید:")
    print(image_url)

    print("")
    print("در حال دانلود تصویر...")

    success = download_image(
        image_url,
        output_path
    )

    if not success:
        print("")
        print("❌ دانلود تصویر ناموفق بود.")
        return

    print("")
    print("✅ تصویر دانلود شد.")
    print("📁 فایل:")
    print(output_path)

    print("")
    print("🤖 در حال بررسی تصویر با AI...")

    result = check_product_image(
        product_name,
        output_path
    )

    print("")
    print("=" * 60)
    print("نتیجه AI")
    print("=" * 60)

    print(result)

    print("")
    print("=" * 60)


if __name__ == "__main__":
    main()