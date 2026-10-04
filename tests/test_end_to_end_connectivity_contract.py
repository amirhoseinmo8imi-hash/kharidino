"""Regression contracts for return approval and seller-order status propagation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_return_refund_is_connected_to_payment_bridge():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'status == "بازپرداخت شد"' in source
    assert 'kharidino_execute_return_refund' in source
    assert "execute_refund(item)" in source


def test_seller_status_updates_master_order():
    source = (ROOT / "merchant_marketplace_v2.py").read_text(encoding="utf-8")
    assert "def sync_master_order_status(order):" in source
    assert 'order.status = "تحویل شد"' in source
    assert 'order.status = "ارسال شد"' in source
    assert "sync_master_order_status(order.order)" in source
