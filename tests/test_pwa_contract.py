from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_pwa_assets_and_manifest_shortcuts():
 for p in ['static/manifest.webmanifest','static/offline.html','static/pwa-sw.js','static/js/kharidino-pwa.js','static/css/kharidino-pwa.css','static/icons/icon-512.svg']:
  assert (ROOT/p).exists()
 manifest=(ROOT/'static/manifest.webmanifest').read_text(encoding='utf-8')
 assert 'standalone' in manifest and 'shortcuts' in manifest

def test_pwa_worker_never_handles_sensitive_routes_or_posts():
 worker=(ROOT/'static/pwa-sw.js').read_text(encoding='utf-8')
 assert "r.method!=='GET'" in worker
 assert 'payment' in worker and 'checkout' in worker and 'account' in worker
 assert "caches.match(OFFLINE)" in worker

def test_pwa_install_and_local_cart_favorites():
 js=(ROOT/'static/js/kharidino-pwa.js').read_text(encoding='utf-8')
 assert 'beforeinstallprompt' in js and 'kh-pwa-cart-draft-v1' in js and 'kh-pwa-favorites-v1' in js
