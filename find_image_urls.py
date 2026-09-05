import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


URL = "https://api.samsungmobilepress.com/media-assets/galaxy-s24"


headers = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    )
}


print("")
print("=" * 60)
print("KHARIDINO IMAGE URL FINDER")
print("=" * 60)

print("")
print("در حال دریافت صفحه Samsung Mobile Press...")

try:

    response = requests.get(
        URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    print("✅ صفحه دریافت شد.")
    print(
        "HTTP:",
        response.status_code
    )

except Exception as e:

    print("")
    print("❌ خطا:")
    print(e)
    raise SystemExit


soup = BeautifulSoup(
    response.text,
    "html.parser"
)


images = []


for img in soup.find_all("img"):

    src = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-lazy-src")
    )

    if not src:
        continue

    full_url = urljoin(
        URL,
        src
    )

    if (
        ".jpg" in full_url.lower()
        or ".jpeg" in full_url.lower()
        or ".png" in full_url.lower()
        or ".webp" in full_url.lower()
    ):

        if full_url not in images:

            images.append(
                full_url
            )


print("")
print(
    "تعداد تصاویر پیدا شده:",
    len(images)
)

print("")
print("=" * 60)
print("IMAGE URLS")
print("=" * 60)


for index, image_url in enumerate(
    images[:20],
    start=1
):

    print("")
    print(
        f"{index}. {image_url}"
    )


print("")
print("=" * 60)
print("پایان")
print("=" * 60)