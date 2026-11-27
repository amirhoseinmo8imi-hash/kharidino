from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pwa_manifest_and_offline_assets_exist():
    assert (ROOT / "static" / "manifest.webmanifest").exists()
    assert (ROOT / "static" / "offline.html").exists()
    assert (ROOT / "static" / "pwa-sw.js").exists()


def test_worker_avoids_sensitive_api_caching():
    worker = (ROOT / "static" / "pwa-sw.js").read_text(encoding="utf-8")
    assert "startsWith('/api/')" in worker
    assert "startsWith('/admin')" in worker
    assert "req.method!=='GET'" in worker
    assert "OFFLINE_URL" in worker


def test_worker_registration_uses_root_scope_endpoint():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "register('/service-worker.js'" in base
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Service-Worker-Allowed" in app
