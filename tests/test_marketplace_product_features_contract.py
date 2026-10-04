from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
RUNNER = ROOT / "run_kharidino.py"
MERCHANT = ROOT / "merchant_marketplace.py"
ADMIN = ROOT / "merchant_approval.py"


def read(path):
    return path.read_text(encoding="utf-8")


def test_price_intelligence_and_returns_models_exist():
    text = read(APP)
    assert "class PriceHistory(db.Model):" in text
    assert "class ReturnRequest(db.Model):" in text
    assert '"/api/products/<int:product_id>/price-history"' in text
    assert '"/returns/request/<int:order_id>"' in text


def test_seller_registration_uses_canonical_merchant_extension():
    app_text = read(APP)
    merchant_text = read(MERCHANT)
    assert 'def seller_register()' not in app_text
    assert 'def seller_register()' in merchant_text


def test_price_snapshots_are_backfilled_at_runtime_initialization():
    text = read(RUNNER)
    assert "record_price_snapshot(_offer)" in text


def test_approved_seller_gets_trust_profile():
    text = read(ADMIN)
    assert "SellerProfile" in text
    assert 'verification_status="تأیید شده"' in text
