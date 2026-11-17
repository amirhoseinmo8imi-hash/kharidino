from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cinema_backend_registers_catalog_playback_and_booking_routes():
    source = (ROOT / "cinema.py").read_text(encoding="utf-8")
    for contract in (
        '"/cinema"', '"/cinema/title/<int:title_id>"',
        '"/cinema/title/<int:title_id>/progress"',
        '"/cinema/showtime/<int:showtime_id>/book"',
        '"/admin/cinema/title"', '"/admin/cinema/showtime"',
        "CinemaTitle", "CinemaProgress", "CinemaShowtime", "CinemaBooking",
        "available_seats >= count",
    ):
        assert contract in source


def test_cinema_is_registered_and_available_in_primary_navigation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "from cinema import register_cinema" in app
    assert "register_cinema(app, db, User, login_required, admin_required)" in app
    assert "url_for('cinema_home')" in base
    assert "سینما" in base
    assert (ROOT / "templates" / "cinema" / "index.html").exists()
    assert (ROOT / "templates" / "cinema" / "title.html").exists()


def test_cinema_video_upload_validates_signature_and_file_size():
    source = (ROOT / "cinema.py").read_text(encoding="utf-8")
    assert '"mp4": lambda data: len(data) >= 12 and data[4:8] == b"ftyp"' in source
    assert 'bytes.fromhex("1a45dfa3")' in source
    assert "MAX_VIDEO_BYTES = 90 * 1024 * 1024" in source
