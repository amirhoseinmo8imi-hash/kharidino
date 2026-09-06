import os
import base64
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# CONFIG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

PRODUCT_UPLOAD_DIR = (
    BASE_DIR
    / "static"
    / "uploads"
    / "products"
)

PRODUCT_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# ENV
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6-luna"
)


if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY در فایل .env پیدا نشد."
    )


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# DOWNLOAD IMAGE
# =========================================================

def download_image(
    image_url,
    output_path
):

    try:

        response = requests.get(
            image_url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            }
        )

        response.raise_for_status()

        content_type = (
            response.headers
            .get("Content-Type", "")
            .lower()
        )

        if not content_type.startswith(
            "image/"
        ):
            return False

        data = response.content

        if len(data) < 5000:
            return False

        output_path.write_bytes(
            data
        )

        return True

    except Exception as e:

        print(
            "IMAGE DOWNLOAD ERROR:",
            e
        )

        return False


# =========================================================
# IMAGE TO DATA URL
# =========================================================

def image_to_data_url(
    image_path
):

    data = image_path.read_bytes()

    encoded = base64.b64encode(
        data
    ).decode("ascii")

    extension = (
        image_path.suffix
        .lower()
        .replace(".", "")
    )

    if extension == "jpg":
        extension = "jpeg"

    return (
        f"data:image/{extension};base64,"
        f"{encoded}"
    )


# =========================================================
# AI IMAGE CHECK
# =========================================================

def check_product_image(
    product_name,
    image_path
):

    image_data = image_to_data_url(
        image_path
    )

    prompt = f"""
You are a product image verification system.

Target product:
{product_name}

Analyze the provided image.

Determine whether the image clearly shows
the exact target product.

Return ONLY valid JSON in this format:

{{
  "match": true,
  "confidence": 0,
  "reason": "short explanation"
}}

Rules:

- match must be true or false.
- confidence must be an integer from 0 to 100.
- Reject unrelated products.
- Reject accessories when the target is the main product.
- Reject screenshots, advertisements, banners and logos.
- Reject images showing a different model.
- Prefer a clean product photo.
"""

    try:

        response = client.responses.create(

            model=OPENAI_MODEL,

            input=[

                {
                    "role": "user",

                    "content": [

                        {
                            "type": "input_text",
                            "text": prompt
                        },

                        {
                            "type": "input_image",
                            "image_url": image_data
                        }

                    ]
                }

            ]
        )

        result = (
            response.output_text
            .strip()
        )

        print(
            "AI RESULT:",
            result
        )

        return result

    except Exception as e:

        print(
            "OPENAI IMAGE CHECK ERROR:",
            e
        )

        error_text = str(e).lower()

        if (
            "429" in error_text
            or "rate limit" in error_text
            or "rate_limit" in error_text
            or "requests per day" in error_text
            or "rpd" in error_text
            or "quota" in error_text
        ):
            raise

        return None


# =========================================================
# SIMPLE AI TEST
# =========================================================

def test_ai():

    print("")
    print(
        "=============================================="
    )
    print(
        "KHARIDINO AI IMAGE SYSTEM"
    )
    print(
        "=============================================="
    )
    print(
        "MODEL:",
        OPENAI_MODEL
    )
    print(
        "API KEY:",
        "FOUND"
        if OPENAI_API_KEY
        else "MISSING"
    )
    print(
        "UPLOAD DIR:",
        PRODUCT_UPLOAD_DIR
    )
    print(
        "=============================================="
    )
    print("")


if __name__ == "__main__":

    test_ai()