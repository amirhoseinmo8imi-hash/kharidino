from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "merchant_marketplace.py"


def _route_block(source, start_marker, end_marker):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_seller_product_save_rejects_invalid_prices_and_inactive_categories():
    source = SOURCE.read_text(encoding="utf-8")
    block = _route_block(
        source,
        'def seller_product_save():',
        '\n\n@app.post("/seller/product/delete/',
    )
    assert "price <= 0 or price > 10**15" in block
    assert "not category or not category.active" in block
    assert 'parsed_url.scheme not in {"http", "https"}' in block
    assert "parsed_url.netloc" in block


def test_seller_offer_price_and_stock_changes_are_snapshotted():
    source = SOURCE.read_text(encoding="utf-8")
    save_block = _route_block(
        source,
        'def seller_product_save():',
        '\n\n@app.post("/seller/product/delete/',
    )
    toggle_block = _route_block(
        source,
        'def seller_offer_toggle(product_id):',
        '\n\n@app.route("/admin/merchants")',
    )
    assert "record_price_snapshot(offer)" in save_block
    assert "record_price_snapshot(offer)" in toggle_block
    assert "db.session.flush()" in save_block


def test_seller_product_mutations_remain_store_scoped():
    source = SOURCE.read_text(encoding="utf-8")
    assert "_owned_product(account.store_id, pid_value)" in source
    assert "_owned_product(account.store_id, product_id)" in source
    assert "SellerProduct.store_id == account.store_id" in source
