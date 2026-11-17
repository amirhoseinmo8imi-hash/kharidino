from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "templates" / "base.html"
TOKENS = ROOT / "static" / "css" / "kharidino-design-tokens-2026.css"


def test_shared_design_tokens_are_loaded_after_legacy_layers():
    text = BASE.read_text(encoding="utf-8")
    token_link = "kharidino-design-tokens-2026.css"
    assert token_link in text
    assert text.rfind(token_link) > text.rfind("kharidino-special-hubs-2026.css")
    assert TOKENS.is_file()


def test_base_template_static_assets_exist():
    text = BASE.read_text(encoding="utf-8")
    paths = re.findall(r"filename='([^']+)'", text)
    for asset in paths:
        assert (ROOT / "static" / asset).is_file(), f"Missing static asset: {asset}"


def test_vehicle_unread_polling_is_visibility_aware_and_not_aggressive():
    text = BASE.read_text(encoding="utf-8")
    assert "setInterval(function(){if(!document.hidden)check();},30000)" in text
    assert "visibilitychange" in text
    assert "setInterval(check,3000)" not in text
