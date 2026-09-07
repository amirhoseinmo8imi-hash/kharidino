from pathlib import Path


def test_ultimate_assets_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "static/css/kharidino-ultimate-2026.css").is_file()
    assert (root / "static/js/kharidino-ultimate-2026.js").is_file()


def test_base_loads_ultimate_assets():
    root = Path(__file__).resolve().parents[1]
    base = (root / "templates/base.html").read_text(encoding="utf-8")
    assert "kharidino-ultimate-2026.css" in base
    assert "kharidino-ultimate-2026.js" in base
