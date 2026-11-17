"""Static security contracts for the Explore module.

Do not make a request against the process-global Flask app in this module:
the legacy integration suite installs runtime extensions lazily in later tests.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "explore.py"
BASE = ROOT / "templates" / "base.html"


def test_explore_routes_use_existing_authentication_and_csrf_contracts():
    source = SOURCE.read_text(encoding="utf-8")
    assert '@app.get("/explore", endpoint="explore")' in source
    assert '@app.post("/explore/create", endpoint="explore_create")' in source
    assert '@login_required' in source
    assert '@admin_required' in source
    assert 'status="pending"' in source
    assert 'status="published"' in source


def test_explore_is_registered_in_the_unified_site_navigation():
    base = BASE.read_text(encoding="utf-8")
    assert "url_for('explore')" in base
    assert "اکسپلور" in base


def test_explore_upload_validation_rejects_unknown_and_spoofed_files():
    from explore import _validated_upload

    unknown = FileStorage(stream=BytesIO(b"hello"), filename="payload.exe")
    spoofed = FileStorage(stream=BytesIO(b"not-a-real-png"), filename="photo.png")
    for upload in (unknown, spoofed):
        try:
            _validated_upload(upload)
            assert False, "invalid upload should be rejected"
        except ValueError:
            pass
