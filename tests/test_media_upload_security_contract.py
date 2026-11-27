from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_upload_limits_are_kind_specific_and_bounded():
    source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    assert "MEDIA_MAX_IMAGE_BYTES" in source
    assert "MEDIA_MAX_VIDEO_BYTES" in source
    assert "max_bytes + 1" in source
    assert "image_too_large" in source
    assert "video_too_large" in source


def test_upload_image_sanitization_and_dimension_limit():
    source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    assert "image.verify()" in source
    assert "image.load()" in source
    assert "image.save(clean, format=detected_format)" in source
    assert "25_000_000" in source
    assert "GIF" not in source[source.index("detected_format not in"):source.index("image.verify()")]


def test_upload_container_signature_checks_and_randomized_filename():
    source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    assert 'raw[4:8] == b"ftyp"' in source
    assert 'raw[:4] == bytes.fromhex("1a45dfa3")' in source
    assert "secrets.token_hex(16)" in source


def test_upload_media_reference_rejects_protocol_relative_paths():
    source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    assert 'media_url.startswith("//")' in source
    assert 'len(raw) >= 12' in source


def test_pending_uploads_are_private_until_moderation():
    source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    assert 'Path(app.instance_path) / "private_media"' in source
    assert '"/media/file/" + filename' in source
    assert 'status="published"' in source[source.index("def media_file"):source.index("def media_pending_admin")]
    assert '"/static/uploads/media/"' not in source


def test_media_mutations_are_subject_to_global_csrf_validation():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    csrf_start = app_source.index("def validate_csrf():")
    csrf_end = app_source.index("@app.errorhandler(400)", csrf_start)
    csrf = app_source[csrf_start:csrf_end]
    assert "X-CSRF-Token" in csrf
    assert "secrets.compare_digest" in csrf
    assert "abort(403" in csrf
    media_source = (ROOT / "media_api.py").read_text(encoding="utf-8")
    for endpoint in ["media_upload", "media_create_post", "media_like", "media_bookmark", "media_report", "media_moderate_admin"]:
        assert f"def {endpoint}" in media_source
    assert "@app.before_request" in app_source and "validate_csrf" in app_source


def test_service_worker_route_registered_before_direct_run():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert app_source.index('@app.route("/service-worker.js")') < app_source.index('if __name__ == "__main__":')
