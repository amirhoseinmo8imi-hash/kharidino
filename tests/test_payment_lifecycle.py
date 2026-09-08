import os

from payment import DisabledGateway, PAYMENT_STATUSES, TestGateway, _idempotency_key, _gateway


def test_payment_statuses():
    assert {"pending", "redirect", "verifying", "paid", "failed", "cancelled", "refunded"} == PAYMENT_STATUSES


def test_idempotency_key_validation():
    assert _idempotency_key(" checkout-123 ") == "checkout-123"
    for value in (None, "", "   ", "x" * 129):
        try:
            _idempotency_key(value)
        except ValueError:
            continue
        assert False


def test_test_gateway_requires_approval():
    gateway = TestGateway()
    started = gateway.start("tx-1", 1000, "https://example.test/callback")
    assert started.status == "redirect"
    assert started.authority
    assert not gateway.verify("tx-1", 1000, {"authority": started.authority}).paid
    result = gateway.verify("tx-1", 1000, {"authority": started.authority, "approved": "1"})
    assert result.paid
    assert result.reference.startswith("TEST-")


def test_production_default_gateway_is_disabled(monkeypatch):
    monkeypatch.delenv("PAYMENT_TEST_MODE", raising=False)
    gateway = _gateway()
    assert isinstance(gateway, DisabledGateway)
    started = gateway.start("tx-prod", 1000, "https://example.test/callback")
    assert started.status == "failed"
    assert not gateway.verify("tx-prod", 1000, {}).paid


def test_test_mode_is_explicit(monkeypatch):
    monkeypatch.setenv("PAYMENT_TEST_MODE", "true")
    assert isinstance(_gateway(), TestGateway)
    monkeypatch.setenv("PAYMENT_TEST_MODE", "0")
    assert isinstance(_gateway(), DisabledGateway)


def test_payment_callback_secret_never_has_a_usable_fallback(monkeypatch):
    monkeypatch.delenv("PAYMENT_CALLBACK_SECRET", raising=False)
    from payment import _valid_callback_signature

    assert not _valid_callback_signature("tx-prod", "anything")
