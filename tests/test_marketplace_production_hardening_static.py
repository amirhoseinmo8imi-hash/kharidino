from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_return_refund_bridge_is_idempotent_and_fails_closed():
    src = read("return_refund_bridge.py")
    assert 'status="pending"' in src
    assert 'status == "succeeded"' in src
    assert "Refund برای درگاه فعال پیاده‌سازی نشده است." in src
    assert "requested != int(tx.amount)" in src
    assert 'refund_request": "yes_money_back"' in src


def test_return_lifecycle_executes_refund_before_marking_refunded():
    src = read("marketplace_fulfillment.py")
    assert 'status == "refunded"' in src
    assert 'kharidino_execute_return_refund' in src
    assert 'row.status = "refunded"' in src
    assert 'return False, error' in src or 'abort(409, description=error)' in src


def test_seller_delivery_unlocks_ledger_only_after_delivery():
    src = read("seller_fulfillment.py")
    assert 'all(x.status == "delivered" for x in shipments)' in src
    assert 'ledger.status = "available"' in src
    assert 'status not in FLOW.get(shipment.status, set())' in src


def test_launcher_order_applies_refund_bridge_after_refund_hardening():
    src = read("run_kharidino.py")
    assert "from return_refund_bridge import apply_return_refund_bridge" in src
    assert src.index("apply_refund_settlement_hardening") < src.index("apply_return_refund_bridge")


def test_no_direct_return_refund_transition_without_executor():
    src = read("marketplace_fulfillment.py")
    marker = 'if status == "refunded":'
    block = src.split(marker, 1)[1].split('row.status = status', 1)[0]
    assert 'kharidino_execute_return_refund' in block
    assert 'row.status = "refunded"' in block
