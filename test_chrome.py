from playwright.sync_api import sync_playwright


CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


with sync_playwright() as p:

    print("")
    print("=" * 60)
    print("KHARIDINO CHROME TEST")
    print("=" * 60)

    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=False
    )

    page = browser.new_page()

    print("")
    print("✅ Chrome با موفقیت اجرا شد.")

    page.goto(
        "https://www.google.com/search?tbm=isch&q=Galaxy+S24",
        wait_until="domcontentloaded",
        timeout=60000
    )

    print("")
    print("✅ Google Images باز شد.")
    print("")
    print("عنوان صفحه:")
    print(page.title())

    page.wait_for_timeout(10000)

    browser.close()

    print("")
    print("✅ تست تمام شد.")