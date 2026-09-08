from payment import PAYMENT_STATUSES, TestGateway, _idempotency_key


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
