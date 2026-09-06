import json
import re
import shutil
import time
from pathlib import Path

from PIL import Image

from app import app, db, Product
from ai_product_image import check_product_image


BASE_DIR = Path(__file__).resolve().parent

CANDIDATES_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
    / "google_candidates"
    / "no_image_27"
)

RESULTS_FILE = BASE_DIR / "ai_verify_27_results.json"

MIN_CONFIDENCE = 90
MAX_AI_PER_PRODUCT = 3
AI_DELAY = 2


def safe_name(name):
    name = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "-", name.strip())
    return name


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


def load_results():
    if not RESULTS_FILE.exists():
        return {}
    try:
        data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print("Error loading results:", e)
        return {}


def save_results(results):
    temp_file = RESULTS_FILE.with_suffix(".tmp")
    temp_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_file.replace(RESULTS_FILE)


def is_rate_limit_error(error):
    text = str(error).lower()
    keywords = (
        "429",
        "rate limit",
        "rate_limit",
        "requests per day",
        "rpd",
        "quota",
        "too many requests",
    )
    return any(keyword in text for keyword in keywords)


def get_product_folder(product):
    return CANDIDATES_DIR / f"{product.id:02}_{safe_name(product.name)}"


def parse_ai_result(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def process_product(product_id, product_name, product_dir):
    print()
    print("=" * 75)
    print(f"PRODUCT ID: {product_id}")
    print(f"NAME: {product_name}")
    print(f"FOLDER: {product_dir.name}")
    print("=" * 75)

    if not product_dir.exists():
        print("Candidate folder not found:")
        print(product_dir)
        return {
            "id": product_id,
            "name": product_name,
            "success": False,
            "status": "folder_not_found",
        }

    images = sorted(product_dir.glob("candidate_*"))
    valid_images = [
        image for image in images
        if image.is_file() and validate_image(image)
    ]

    print(f"Total candidates: {len(images)}")
    print(f"Valid candidates: {len(valid_images)}")

    if not valid_images:
        return {
            "id": product_id,
            "name": product_name,
            "success": False,
            "status": "no_valid_images",
        }

    candidates = valid_images[:MAX_AI_PER_PRODUCT]
    print(f"AI candidates: {len(candidates)}")

    best = None

    for index, image_path in enumerate(candidates, start=1):
        print()
        print(f"AI CHECK {index}/{len(candidates)}")
        print(f"Image: {image_path.name}")

        try:
            result = parse_ai_result(
                check_product_image(product_name, image_path)
            )

            if result is None:
                print("Invalid AI result")
                continue

            match = result.get("match", False)
            try:
                confidence = int(result.get("confidence", 0))
            except (TypeError, ValueError):
                confidence = 0

            reason = str(result.get("reason", ""))

            print(f"Match: {match}")
            print(f"Confidence: {confidence}%")
            print(f"Reason: {reason}")

            if match is True and confidence >= MIN_CONFIDENCE:
                candidate = {
                    "image": image_path,
                    "confidence": confidence,
                    "reason": reason,
                }
                if best is None or confidence > best["confidence"]:
                    best = candidate
                if confidence >= 98:
                    print("High confidence!")
                    break

            if index < len(candidates):
                time.sleep(AI_DELAY)

        except Exception as e:
            if is_rate_limit_error(e):
                print()
                print("=" * 75)
                print("OPENAI RATE LIMIT")
                print("=" * 75)
                raise RuntimeError("RATE_LIMIT_STOP") from e
            print("AI ERROR:", e)

    if best is None:
        print("No suitable image found.")
        return {
            "id": product_id,
            "name": product_name,
            "success": False,
            "status": "no_match",
        }

    source = best["image"]
    output_name = (
        f"product_{product_id}_{safe_name(product_name)}_verified.jpg"
    )
    output_path = (
        BASE_DIR / "static" / "uploads" / "products" / output_name
    )

    shutil.copy2(source, output_path)
    print("Image saved:")
    print(output_path)

    product = Product.query.get(product_id)
    if product is None:
        print("ERROR: Product not found in database.")
        return {
            "id": product_id,
            "name": product_name,
            "success": False,
            "status": "product_not_found",
        }

    product.image = f"uploads/products/{output_name}"
    db.session.commit()

    print("DATABASE UPDATED")
    print(f"Image: {product.image}")
    print("SELECTED IMAGE")
    print(f"Candidate: {source.name}")
    print(f"Confidence: {best['confidence']}%")
    print(f"Reason: {best['reason']}")

    return {
        "id": product_id,
        "name": product_name,
        "success": True,
        "status": "success",
        "confidence": best["confidence"],
        "reason": best["reason"],
        "candidate": str(source.relative_to(BASE_DIR)),
        "new_image": f"uploads/products/{output_name}",
    }


def main():
    print()
    print("=" * 75)
    print("KHARIDINO - AI IMAGE VERIFICATION")
    print("=" * 75)
    print(f"Maximum AI requests per product: {MAX_AI_PER_PRODUCT}")
    print(f"Minimum confidence: {MIN_CONFIDENCE}%")

    if not CANDIDATES_DIR.exists():
        print("ERROR: Candidate directory does not exist:")
        print(CANDIDATES_DIR)
        return

    results = load_results()

    with app.app_context():
        products = (
            Product.query
            .filter(Product.id >= 12, Product.id <= 44)
            .order_by(Product.id)
            .all()
        )

        print(f"Products found: {len(products)}")

        for product in products:
            key = str(product.id)
            old = results.get(key, {})

            if old.get("success") is True or old.get("status") == "success":
                print(f"SKIP {product.id} | {product.name} | already verified")
                continue

            if product.image and "_verified" in product.image:
                print(f"SKIP {product.id} | {product.name} | verified image exists")
                continue

            product_dir = get_product_folder(product)
            print(f"Checking folder: {product_dir.name}")

            try:
                result = process_product(
                    product.id,
                    product.name,
                    product_dir,
                )
                results[key] = result
                save_results(results)

            except RuntimeError as e:
                if str(e) == "RATE_LIMIT_STOP":
                    results[key] = {
                        "id": product.id,
                        "name": product.name,
                        "success": False,
                        "status": "rate_limit",
                    }
                    save_results(results)
                    print("API RATE LIMIT - progress saved - script stopped")
                    return
                raise

    save_results(results)
    print()
    print("=" * 75)
    print("AI VERIFICATION FINISHED")
    print("=" * 75)
    print(f"Results file: {RESULTS_FILE}")


if __name__ == "__main__":
    main()