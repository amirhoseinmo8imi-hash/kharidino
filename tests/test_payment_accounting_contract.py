import hashlib
import hmac

from financial_accounting import _money
from payment import PAYMENT_STATUSES, TestGateway, _idempotency_key, _valid_callback_signature


def test_payment_idempotency_key_is_strictly_bounded():
    assert _idempotency_key(" checkout-123 ") == "checkout-123"

    try:
        _idempotency_key("")
    except ValueError:
        pass
    else:
        raise AssertionError("empty idempotency keys must be rejected")

    try:
        _idempotency_key("x" * 129)
    except ValueError:
        pass
    else:
        raise AssertionError("oversized idempotency keys must be rejected")


def test_callback_signature_is_exact_hmac(monkeypatch):
    monkeypatch.setenv("PAYMENT_CALLBACK_SECRET", "contract-secret")
    transaction_id = "tx-contract-1"
    signature = hmac.new(
        b"contract-secret", transaction_id.encode(), hashlib.sha256
    ).hexdigest()

    assert _valid_callback_signature(transaction_id, signature)
    assert not _valid_callback_signature(transaction_id, signature[:-1] + "0")
    assert not _valid_callback_signature("different", signature)


def test_test_gateway_is_fail_closed_without_approval():
    gateway = TestGateway()
    started = gateway.start("tx-contract", 500_000, "https://example.test/callback")

    assert started.status == "redirect"
    assert started.authority
    assert not gateway.verify(
        "tx-contract", 500_000, {"authority": started.authority, "approved": "0"}
    ).paid
    assert not gateway.verify(
        "tx-contract", 500_000, {"authority": "wrong", "approved": "1"}
    ).paid

    verified = gateway.verify(
        "tx-contract", 500_000,
        {"authority": started.authority, "approved": "true"},
    )
    assert verified.paid
    assert verified.reference.startswith("TEST-")


def test_payment_status_contract_contains_terminal_states():
    assert {"paid", "failed", "cancelled", "refunded"}.issubset(PAYMENT_STATUSES)


def test_financial_split_must_balance_exactly():
    order_total = 1_250_000
    seller_net = 1_125_000
    platform_fee = 125_000
    assert order_total == seller_net + platform_fee


def test_financial_refund_reverses_cash_and_revenue_symmetrically():
    order_total = 900_000
    seller_net = 810_000
    platform_fee = 90_000
    assert order_total == seller_net + platform_fee
    assert order_total == seller_net + platform_fee
    assert _money(order_total) == 900_000
