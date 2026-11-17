"""Security and integration contracts for the moderated Explore feed."""
from __future__ import annotations

import os
os.environ.setdefault("PAYMENT_PROVIDER", "disabled")
os.environ.setdefault("PAYMENT_TEST_MODE", "1")

from app import app


def test_explore_feed_renders():
    app.config.update(TESTING=True)
    response = app.test_client().get("/explore")
    assert response.status_code == 200
    assert "اکسپلور خریدینو" in response.get_data(as_text=True)


def test_explore_mutations_require_csrf():
    app.config.update(TESTING=True)
    client = app.test_client()
    for path in ("/explore/create", "/explore/1/like", "/explore/1/report", "/admin/explore/1/publish"):
        response = client.post(path, data={}, headers={"Origin": "http://localhost"})
        assert response.status_code == 403, (path, response.status_code)


def test_explore_upload_validation_rejects_unknown_and_spoofed_files():
    from io import BytesIO
    from werkzeug.datastructures import FileStorage
    from explore import _validated_upload

    unknown = FileStorage(stream=BytesIO(b"hello"), filename="payload.exe")
    spoofed = FileStorage(stream=BytesIO(b"not-a-real-png"), filename="photo.png")
    try:
        _validated_upload(unknown)
        assert False, "unknown extension should be rejected"
    except ValueError:
        pass
    try:
        _validated_upload(spoofed)
        assert False, "spoofed image should be rejected"
    except ValueError:
        pass
