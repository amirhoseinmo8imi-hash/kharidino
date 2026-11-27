from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_pwa_assets_and_manifest_shortcuts():
    for path in ['static/manifest.webmanifest','static/offline.html','static/pwa-sw.js','static/js/kharidino-pwa.js','static/css/kharidino-pwa.css','static/icons/icon-512.svg']:
        assert (ROOT/path).exists()
    manifest=(ROOT/'static/manifest.webmanifest').read_text(encoding='utf-8')
    assert 'standalone' in manifest and 'shortcuts' in manifest

def test_worker_only_caches_public_get_static_and_navigation_fallback():
    worker=(ROOT/'static/pwa-sw.js').read_text(encoding='utf-8')
    assert "request.method!=='GET'" in worker
    assert 'PRIVATE.test(url.pathname)' in worker
    for route in ['api','admin','login','logout','register','account','cart','checkout','payment','orders','profile','seller','messages']:
        assert route in worker
    assert "cache.put(request,response.clone())" in worker
    assert "cache.match(OFFLINE)" in worker

def test_pwa_install_and_local_cart_favorites():
    js=(ROOT/'static/js/kharidino-pwa.js').read_text(encoding='utf-8')
    assert 'beforeinstallprompt' in js
    assert 'kh-pwa-cart-draft-v1' in js
    assert 'kh-pwa-favorites-v1' in js
    assert "if(!navigator.onLine){e.preventDefault();save();" in js


def test_app_output_mobile_dock_and_responsive_css_are_wired():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    css = (ROOT / "static/css/kharidino-app-output.css").read_text(encoding="utf-8")
    for endpoint in ["catalog_products", "compare", "cart", "profile", "home"]:
        assert f"url_for('{endpoint}')" in base
    assert "kharidino-mobile-dock" in base
    assert "@media(max-width:760px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "env(safe-area-inset-bottom)" in css
