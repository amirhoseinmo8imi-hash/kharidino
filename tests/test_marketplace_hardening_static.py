from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_marketplace_hardening_is_wired_into_launcher():
    launcher = (ROOT / "run_kharidino.py").read_text(encoding="utf-8")
    assert "from marketplace_hardening import apply_marketplace_hardening" in launcher
    assert "apply_marketplace_ultimate(app); apply_marketplace_hardening(app)" in launcher


def test_marketplace_hardening_contains_ownership_guards_and_idempotency():
    source = (ROOT / "marketplace_hardening.py").read_text(encoding="utf-8")
    assert "_order_owned_by_current_user" in source
    assert "product_not_found" in source
    assert "reference_conflict" in source
    assert "insufficient_balance" in source
    assert "coupon_usage_exhausted" in source


def test_marketplace_hardening_is_python_source():
    source = (ROOT / "marketplace_hardening.py").read_text(encoding="utf-8")
    compile(source, "marketplace_hardening.py", "exec")
