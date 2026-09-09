"""Release contracts for installable and safe PWA behavior."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pwa_manifest_has_install_icons_and_root_scope():
    manifest = (ROOT / "static/manifest.webmanifest").read_text(encoding="utf-8")
    assert '"start_url": "/"' in manifest
    assert '"scope": "/"' in manifest
    assert '"display": "standalone"' in manifest
    assert '"sizes": "192x192"' in manifest
    assert '"sizes": "512x512"' in manifest
    assert '/static/icons/icon-192.svg' in manifest
    assert '/static/icons/icon-512.svg' in manifest


def test_base_template_wires_manifest_and_service_worker():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    assert "manifest.webmanifest" in base
    assert "navigator.serviceWorker.register" in base
    assert "filename='sw.js'" in base


def test_service_worker_is_static_only_and_get_only():
    sw = (ROOT / "static/sw.js").read_text(encoding="utf-8")
    assert "request.method !== 'GET'" in sw
    assert "url.origin !== self.location.origin" in sw
    assert "!url.pathname.startsWith('/static/')" in sw
