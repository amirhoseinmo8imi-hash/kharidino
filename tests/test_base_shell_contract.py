from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "templates" / "base.html"


def test_modern_shell_assets_are_loaded_from_base():
    text = BASE.read_text(encoding="utf-8")
    assert "kharidino-modern-shell-2026.css" in text
    assert "kharidino-theme.js" in text
    assert 'data-theme-toggle' in text


def test_vehicle_unread_script_stays_inside_document():
    text = BASE.read_text(encoding="utf-8")
    unread = text.find("data-vehicle-unread")
    html_close = text.rfind("</html>")
    assert unread != -1 and unread < html_close


def test_csrf_fetch_only_attaches_token_to_same_origin():
    text = BASE.read_text(encoding="utf-8")
    assert "target.origin===window.location.origin" in text
