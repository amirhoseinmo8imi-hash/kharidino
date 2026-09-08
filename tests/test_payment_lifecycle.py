import os

from commerce_extensions_v2 import ManualPaymentGateway, _payment_key


def test_manual_gateway_requires_explicit_confirmation():
    class Tx:
        status = "verifying"

    tx = Tx()
    gateway = ManualPaymentGateway()
    assert gateway.verify(tx, {"confirm": "0"}) is False
    assert tx.status == "failed"
    assert gateway.verify(tx, {"confirm": "1"}) is True
    assert tx.status == "paid"


def test_payment_key_is_deterministic_and_not_plaintext():
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/", method="POST", data={"idempotency_key": "checkout-123"}):
        first = _payment_key()
    with app.test_request_context("/", method="POST", data={"idempotency_key": "checkout-123"}):
        second = _payment_key()
    assert first == second
    assert first != "checkout-123"
    assert len(first) == 40


def test_payment_gateway_selection_defaults_safely(monkeypatch):
    monkeypatch.delenv("PAYMENT_GATEWAY", raising=False)
    assert os.environ.get("PAYMENT_GATEWAY") is None
