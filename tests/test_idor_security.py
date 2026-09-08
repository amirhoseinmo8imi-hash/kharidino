"""Regression contracts for user-to-user IDOR boundaries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_order_endpoints_use_explicit_owner_boundary():
    source = _read("commerce_extensions_v2.py")
    assert "def _owned_order(order_id):" in source
    assert "order.user_id==user.id" in source
    assert "@app.get(\"/orders/<int:order_id>\")" in source
    assert "order=_owned_order(order_id)" in source
    assert "@app.get(\"/api/orders/<int:order_id>\")" in source


def test_saved_address_and_notification_mutations_are_owner_scoped():
    source = _read("commerce_extensions_v2.py")
    assert "if not row or row.user_id!=user.id:return (\"Not Found\",404)" in source
    assert source.count("row.user_id!=user.id") >= 3


def test_seller_order_mutation_is_store_scoped():
    source = _read("merchant_marketplace_v2.py")
    assert "SellerOrder.query.filter_by(id=seller_order_id, store_id=account.store_id).first_or_404()" in source
    assert "SellerProduct.store_id == account.store_id" in source
    assert "Offer.store_id == account.store_id" in source


def test_seller_cannot_delete_global_catalog_product():
    source = _read("merchant_marketplace.py")
    start = source.index('def seller_product_delete(')
    end = source.index('\n\n@app.post("/seller/offer/toggle/', start)
    block = source[start:end]
    assert "SellerProduct.query.filter_by(store_id=account.store_id, product_id=product.id).delete()" in block
    assert "Offer.query.filter_by(store_id=account.store_id, product_id=product.id).delete()" in block
    assert "db.session.delete(product)" not in block
    assert "product.active = False" in block


def test_admin_refund_requires_admin_and_matching_order():
    source = _read("payment.py")
    start = source.index('def payment_refund(')
    end = source.index('\n\n    @app.after_request', start)
    block = source[start:end]
    assert 'if not user or user.role != "admin":' in block
    assert 'if tx.status != "paid":' in block
    assert 'if not order:' in block
    assert 'tx.status = "refunded"' in block


def test_mobile_catalog_is_read_only_and_public_catalog_is_active_only():
    source = _read("mobile_app/api/mobile_api.py")
    assert "@bp.get(\"/products/<int:product_id>\")" in source
    assert "Product.query.filter_by(id=product_id, active=True).first_or_404()" in source
    assert "@bp.post" not in source
    assert "@bp.put" not in source
    assert "@bp.delete" not in source
