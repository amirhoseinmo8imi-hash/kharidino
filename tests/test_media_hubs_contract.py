from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_hub_routes_are_registered():
    source = (ROOT / "media_hubs.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    for route in ("/explore", "/reels", "/cinema"):
        assert route in source
    assert "register_media_hubs(app)" in app_source


def test_media_hub_template_has_three_modes_and_clear_scaffold_status():
    template = (ROOT / "templates" / "media_hub.html").read_text(encoding="utf-8")
    assert "hub == 'explore'" in template
    assert "hub == 'reels'" in template
    assert "Kharidino Cinema" in template
    assert "پوسته معرفی" in template


def test_media_hubs_are_in_desktop_and_mobile_navigation():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    for endpoint in ("kharidino_explore", "kharidino_reels", "kharidino_cinema"):
        assert endpoint in base
