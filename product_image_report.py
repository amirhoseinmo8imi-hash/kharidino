import json
from pathlib import Path

from app import app, db, Product


BASE_DIR = Path(__file__).resolve().parent

RESULTS_FILE = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
    / "google_candidates"
    / "all_products_results.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "product_image_report.txt"
)


def load_results():
    if not RESULTS_FILE.exists():
        return {}

    try:
        with open(
            RESULTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return {
                str(item.get("id")): item
                for item in data
                if item.get("id") is not None
            }

        if isinstance(data, dict):
            return data

    except Exception as e:
        print("⚠️ خطا در خواندن نتایج:", e)

    return {}


def classify_product(product, results):
    key = str(product.id)
    result = results.get(key, {})

    image = product.image or ""

    success = (
        result.get("success") is True
        or result.get("status") == "success"
    )

    # عکس تأییدشده
    if "_verified" in image or success:
        return "VERIFIED"

    # بدون عکس
    if not image.strip():
        return "NO_IMAGE"

    # عکس معمولی
    return "NORMAL"


def main():

    results = load_results()

    verified = []
    normal = []
    no_image = []

    with app.app_context():

        products = (
            Product.query
            .order_by(Product.id)
            .all()
        )

        for product in products:

            status = classify_product(
                product,
                results
            )

            item = {
                "id": product.id,
                "name": product.name,
                "image": product.image or "",
            }

            if status == "VERIFIED":
                verified.append(item)

            elif status == "NORMAL":
                normal.append(item)

            else:
                no_image.append(item)

    lines = []

    lines.append("=" * 75)
    lines.append("KHARIDINO - PRODUCT IMAGE REPORT")
    lines.append("=" * 75)
    lines.append("")

    lines.append(
        f"TOTAL PRODUCTS: {len(verified) + len(normal) + len(no_image)}"
    )

    lines.append(
        f"VERIFIED: {len(verified)}"
    )

    lines.append(
        f"NORMAL: {len(normal)}"
    )

    lines.append(
        f"NO IMAGE: {len(no_image)}"
    )

    lines.append("")
    lines.append("=" * 75)
    lines.append("")

    # =========================================================
    # VERIFIED
    # =========================================================

    lines.append(
        f"🟢 VERIFIED IMAGES ({len(verified)})"
    )

    lines.append("-" * 75)

    for item in verified:

        lines.append(
            f"{item['id']:02} | {item['name']}"
        )

        lines.append(
            f"     IMAGE: {item['image']}"
        )

    lines.append("")
    lines.append("=" * 75)
    lines.append("")

    # =========================================================
    # NORMAL
    # =========================================================

    lines.append(
        f"🟡 NORMAL IMAGES ({len(normal)})"
    )

    lines.append("-" * 75)

    for item in normal:

        lines.append(
            f"{item['id']:02} | {item['name']}"
        )

        lines.append(
            f"     IMAGE: {item['image']}"
        )

    lines.append("")
    lines.append("=" * 75)
    lines.append("")

    # =========================================================
    # NO IMAGE
    # =========================================================

    lines.append(
        f"🔴 PRODUCTS WITHOUT IMAGE ({len(no_image)})"
    )

    lines.append("-" * 75)

    for item in no_image:

        lines.append(
            f"{item['id']:02} | {item['name']}"
        )

    lines.append("")
    lines.append("=" * 75)

    report = "\n".join(lines)

    print()
    print(report)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(report)

    print()
    print("=" * 75)
    print(
        f"📄 گزارش ذخیره شد:"
    )
    print(
        OUTPUT_FILE
    )
    print("=" * 75)


if __name__ == "__main__":
    main()