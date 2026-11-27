"""Release contracts for installable and safe PWA behavior."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_manifest_has_install_icons_and_root_scope():
    manifest=(ROOT / "static/manifest.webmanifest").read_text(encoding="utf-8")
    assert '"start_url":"/"' in manifest and '"scope":"/"' in manifest
    assert '"display":"standalone"' in manifest
    assert '"sizes":"192x192"' in manifest and '"sizes":"512x512"' in manifest
    assert '/static/icons/icon-192.svg' in manifest and '/static/icons/icon-512.svg' in manifest
def test_base_template_wires_manifest_and_worker():
    base=(ROOT / "templates/base.html").read_text(encoding="utf-8")
    assert "manifest.webmanifest" in base
    assert "service-worker.js" in base or "navigator.serviceWorker.register" in base
def test_worker_limits_cache_to_public_static_resources():
    sw=(ROOT / "static/pwa-sw.js").read_text(encoding="utf-8")
    assert "request.method!=='GET'" in sw
    assert "url.origin!==self.location.origin" in sw
    assert "PRIVATE.test(url.pathname)" in sw
    assert "cache.put(request,response.clone())" in sw
    assert "cache.match(OFFLINE)" in sw
