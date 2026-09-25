from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_checkout_adjustments_are_wired():
    launcher = (ROOT / "run_kharidino.py").read_text(encoding="utf-8")
    source = (ROOT / "checkout_marketplace_adjustments.py").read_text(encoding="utf-8")
    assert "apply_checkout_marketplace_adjustments(app)" in launcher
    assert "CouponRedemption" in source
    assert "insufficient_wallet_balance" in source
    assert "order.total = max(0, subtotal_after_coupon - wallet_used)" in source


def test_fulfillment_routes_enforce_ownership():
    source = (ROOT / "seller_fulfillment.py").read_text(encoding="utf-8")
    customer = (ROOT / "marketplace_fulfillment.py").read_text(encoding="utf-8")
    assert "SellerOrder.query.filter_by(id=seller_order_id, store_id=account.store_id)" in source
    assert "_owned_order(order_id)" in customer
    assert "status not in RETURN_FLOW.get(row.status, set())" in customer


def test_new_modules_compile():
    for name in (
        "checkout_marketplace_adjustments.py",
        "marketplace_fulfillment.py",
        "seller_fulfillment.py",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        compile(source, name, "exec")
