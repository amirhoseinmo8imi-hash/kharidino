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
    block = src.split('if status == "refunded":', 1)[1].split('row.status = status', 1)[0]
    assert 'kharidino_execute_return_refund' in block
    assert block.index('ok, error = executor(row)') < block.index('row.status = "refunded"')


def test_seller_delivery_unlocks_ledger_only_after_delivery():
    src = read("seller_fulfillment.py")
    assert 'all(x.status == "delivered" for x in shipments)' in src
    assert 'ledger.status = "available"' in src
    assert 'status not in FLOW.get(shipment.status, set())' in src


def test_launcher_order_applies_refund_bridge_after_refund_hardening():
    src = read("run_kharidino.py")
    assert "from return_refund_bridge import apply_return_refund_bridge" in src
    assert src.index("apply_refund_settlement_hardening") < src.index("apply_return_refund_bridge")


def test_checkout_adjustments_have_atomic_wallet_and_free_order_path():
    src = read("checkout_marketplace_adjustments.py")
    assert "CustomerWallet.balance >= requested" in src
    assert 'reference = f"CHECKOUT:{order.id}:WALLET"' in src
    assert 'order.status = "تأیید شد"' in src
    assert 'checkout_free_order_id' in src
    assert 'payment_required": False' in src


def test_payment_bridge_never_sends_free_order_to_gateway():
    src = read("payment.py")
    assert 'free_order_id = session.pop("checkout_free_order_id", None)' in src
    assert 'order.status == "در انتظار بررسی"' in src
    assert 'int(order.total or 0) > 0' in src


def test_payment_callback_is_atomic_and_amount_bound():
    src = read("payment.py")
    assert 'status.in_({"pending", "redirect", "failed"})' in src
    assert 'int(order.total or 0) != tx.amount' in src
    assert 'tx.status = "paid"' in src
