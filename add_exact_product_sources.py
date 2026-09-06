from app import app, db, Product

EXACT_SOURCES = {

    "ASUS TUF Gaming F15": [
        "https://www.asus.com/us/laptops/for-gaming/"
        "tuf-gaming/asus-tuf-gaming-f15/"
    ],

    "Lenovo IdeaPad Slim 3": [
        "https://www.lenovo.com/us/en/p/laptops/ideapad/"
        "ideapad-300/ideapad-slim-3-gen-8-15-inch-amd/"
        "len101i0073"
    ],

    "HP Victus 15": [
        "https://www.hp.com/us-en/shop/mdp/gaminglaptops/victus-15"
    ],

    "TP-Link Archer C6": [
        "https://www.tp-link.com/us/home-networking/"
        "wifi-router/archer-c6/"
    ],

    "Xiaomi Redmi Note 13 Pro": [
        "https://www.mi.com/global/product/redmi-note-13-pro/"
    ],

    "Sony DualSense Wireless Controller": [
        "https://www.playstation.com/en-us/accessories/"
        "dualsense-wireless-controller/"
    ],

    "Xbox Series X": [
        "https://www.xbox.com/en-US/consoles/xbox-series-x"
    ],

    "Galaxy S24": [
        "https://www.samsung.com/az/smartphones/galaxy-s24/"
    ],

    "Samsung Galaxy S24": [
        "https://www.samsung.com/az/smartphones/galaxy-s24/"
    ],

    "Samsung Galaxy A55": [
        "https://www.samsung.com/az/smartphones/galaxy-a/"
        "galaxy-a55-5g-awesome-navy-128gb-sm-a556ezkacau/"
    ],

    "Apple MacBook Air M3": [
        "https://www.apple.com/az/macbook-air/"
    ],

    "MacBook Air M3": [
        "https://www.apple.com/az/macbook-air/"
    ],
}


with app.app_context():

    print()
    print("=" * 65)
    print("🛒 KHARIDINO")
    print("🔗 ثبت منابع دقیق محصولات")
    print("=" * 65)
    print()

    for product_name, urls in EXACT_SOURCES.items():

        product = Product.query.filter_by(
            name=product_name
        ).first()

        if not product:
            print(f"❌ پیدا نشد: {product_name}")
            continue

        print(f"✅ {product_name}")
        print(f"   ID: {product.id}")

        # منابع در این مرحله فقط نمایش داده می‌شوند.
        # دیتابیس تصویر قبلی را تغییر نمی‌دهیم.
        print(f"   🌐 {urls[0]}")
        print()

    print("=" * 65)
    print("✅ بررسی منابع تمام شد")
    print("=" * 65)