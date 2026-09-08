"""High-signal regression contracts for payment, accounting and IDOR boundaries.

These tests intentionally inspect the production source where a full external
bank gateway is unavailable in CI. They lock down the security invariants that
must remain true when a real gateway adapter is added.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_callback_claim_is_atomic_and_happens_before_gateway_verification():
    source = _read("payment.py")
    start = source.index('def payment_callback(')
    end = source.index('\n\n    @app.post("/payment/refund/', start)
    block = source[start:end]

    assert 'PaymentTransaction.status.in_({"pending", "redirect", "failed"})' in block
    assert '.update({"status": "verifying"}, synchronize_session=False)' in block
    assert 'if claim != 1:' in block
    assert 'db.session.commit()' in block
    assert 'result = gateway.verify(' in block
    assert block.index('db.session.commit()') < block.index('result = gateway.verify(')
    assert 'if current and current.status == "paid":' in block
    assert 'callback هم‌زمان در حال پردازش است' in block


def test_payment_identity_and_amount_are_bound_to_order():
    source = _read("payment.py")
    start = source.index('def payment_callback(')
    end = source.index('\n\n    @app.post("/payment/refund/', start)
    block = source[start:end]

    assert 'order.user_id != tx.user_id' in block
    assert 'int(order.total or 0) != tx.amount' in block
    assert 'tx.amount <= 0' in block
    assert 'hmac.compare_digest(tx.authority, returned_authority)' in block
    assert 'tx.gateway_reference = result.reference[:200]' in block


def test_payment_start_has_idempotency_and_cross_order_protection():
    source = _read("payment.py")
    start = source.index('def payment_start(')
    end = source.index('\n\n    @app.route("/payment/callback/', start)
    block = source[start:end]

    assert 'request.form.get("idempotency_key")' in block
    assert 'request.headers.get("Idempotency-Key")' in block
    assert 'unique=True' in source[source.index('idempotency_key'):source.index('idempotency_key') + 120]
    assert 'tx.user_id != session["user_id"] or tx.order_id != order.id' in block
    assert 'if tx.status == "paid":' in block


def test_checkout_payment_bridge_only_redirects_to_owned_order_payment():
    source = _read("payment.py")
    start = source.index('def payment_checkout_bridge(')
    end = source.index('\n\n    @app.get("/payment/start/', start)
    block = source[start:end]
    assert 'order.user_id == session.get("user_id")' in block
    assert 'session.pop("checkout_payment_order_id", None)' in block
    assert 'response.status_code = 303' in block


def test_refund_is_admin_only_and_idempotently_transitions_paid_transaction():
    source = _read("payment.py")
    start = source.index('def payment_refund(')
    end = source.index('\n\n    @app.after_request', start)
    block = source[start:end]
    assert 'user.role != "admin"' in block
    assert 'tx.status != "paid"' in block
    assert 'tx.status = "refunded"' in block
    assert 'order.status = "لغو شد"' in block
    assert 'ledger.status = "cancelled"' in block


def test_financial_journal_has_unique_references_and_balanced_payment_entries():
    source = _read("financial_accounting.py")
    assert 'reference = db.Column(db.String(180), unique=True' in source
    assert 'reference=f"PAYMENT:{tx.public_id}:CASH"' in source
    assert 'reference=f"PAYMENT:{tx.public_id}:SELLER"' in source
    assert 'reference=f"PAYMENT:{tx.public_id}:PLATFORM"' in source
    assert 'reference=f"REFUND:{tx.public_id}:CASH"' in source
    assert 'reference=f"REFUND:{tx.public_id}:SELLER"' in source
    assert 'reference=f"REFUND:{tx.public_id}:PLATFORM"' in source


def test_financial_journal_does_not_create_duplicate_facts_on_repeated_flushes():
    source = _read("financial_accounting.py")
    assert 'filter_by(reference=reference).first()' in source
    assert 'kharidino_financial_paid_ids' in source
    assert 'kharidino_financial_refund_ids' in source
    assert 'kharidino_financial_settlement_ids' in source


def test_seller_funds_are_released_only_after_master_order_delivery():
    accounting = _read("financial_accounting.py")
    marketplace = _read("merchant_marketplace_v2.py")
    assert 'filter_by(status="تحویل شد")' in accounting
    assert 'ledger.status = "available"' in accounting
    assert 'if order.order and order.order.status == "تحویل شد":' in marketplace
    assert 'if new_status == "delivered":' in marketplace


def test_settlement_journal_is_tied_to_paid_settlement_and_unique_reference():
    source = _read("financial_accounting.py")
    assert 'filter_by(status="paid")' in source
    assert 'reference=f"SETTLEMENT:{settlement.id}:SELLER"' in source
    assert 'reference=f"SETTLEMENT:{settlement.id}:CASH"' in source
    assert 'kharidino_financial_settlement_ids' in source


def test_refund_journal_reverses_the_original_payment_accounts():
    source = _read("financial_accounting.py")
    start = source.index('def refunded_order_journal(')
    end = source.index('\n\n    @event.listens_for', start)
    block = source[start:end]
    assert 'if not original:' in block
    assert 'direction="credit"' in block
    assert 'direction="debit"' in block
    assert 'amount=tx.amount' in block
    assert 'REFUND:{tx.public_id}:CASH' in block


def test_idor_boundaries_cover_payment_order_and_seller_finance():
    payment = _read("payment.py")
    commerce = _read("commerce_extensions_v2.py")
    marketplace = _read("merchant_marketplace_v2.py")

    assert 'order.user_id != session["user_id"]' in payment
    assert 'def _owned_order(order_id):' in commerce
    assert 'SellerOrder.query.filter_by(id=seller_order_id, store_id=account.store_id)' in marketplace
    assert 'SellerLedger.query.filter_by(store_id=account.store_id)' in marketplace


def test_payment_reference_cannot_be_reused_across_transactions():
    source = _read("payment.py")
    assert 'gateway_reference = db.Column(db.String(200), unique=True' in source
    assert 'authority = db.Column(db.String(200), unique=True' in source
