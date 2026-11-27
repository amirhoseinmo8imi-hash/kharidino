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
