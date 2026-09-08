"""Unit tests for the provider-specific NextPay adapter.

No network call is allowed in this test module. HTTP is replaced with a tiny
fake response so CI remains deterministic and credential-free.
"""
from payment_gateways import NextPayGateway


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_nextpay_start_uses_provider_contract(monkeypatch):
    monkeypatch.setenv("NEXTPAY_API_KEY", "test-key")
    calls = []

    def fake_post(url, data, timeout):
        calls.append((url, data, timeout))
        return FakeResponse({"code": -1, "trans_id": "np-token-123"})

    monkeypatch.setattr("payment_gateways.requests.post", fake_post)
    gateway = NextPayGateway()
    result = gateway.start("txn-123", 125000, "https://shop.test/payment/callback/txn-123")

    assert result.status == "redirect"
    assert result.authority == "np-token-123"
    assert result.payment_url.endswith("/np-token-123")
    assert calls[0][1]["api_key"] == "test-key"
    assert calls[0][1]["order_id"] == "txn-123"
    assert calls[0][1]["amount"] == 125000
    assert calls[0][1]["currency"] == "IRT"
    assert calls[0][1]["auto_verify"] == "no"


def test_nextpay_verify_uses_provider_token_and_binds_order_and_amount(monkeypatch):
    monkeypatch.setenv("NEXTPAY_API_KEY", "test-key")
    calls = []

    def fake_post(url, data, timeout):
        calls.append((url, data, timeout))
        return FakeResponse({
            "code": 0,
            "amount": 125000,
            "order_id": "txn-123",
            "Shaparak_Ref_Id": "ref-456",
        })

    monkeypatch.setattr("payment_gateways.requests.post", fake_post)
    gateway = NextPayGateway()
    result = gateway.verify("txn-123", 125000, {"trans_id": "np-token-123", "amount": "125000"})

    assert result.paid is True
    assert result.reference == "ref-456"
    assert calls[0][1]["api_key"] == "test-key"
    assert calls[0][1]["trans_id"] == "np-token-123"
    assert calls[0][1]["amount"] == 125000
    assert calls[0][1]["currency"] == "IRT"


def test_nextpay_verify_rejects_provider_order_mismatch(monkeypatch):
    monkeypatch.setenv("NEXTPAY_API_KEY", "test-key")

    def fake_post(url, data, timeout):
        return FakeResponse({"code": 0, "amount": 125000, "order_id": "other-txn", "Shaparak_Ref_Id": "ref"})

    monkeypatch.setattr("payment_gateways.requests.post", fake_post)
    result = NextPayGateway().verify("txn-123", 125000, {"trans_id": "np-token-123", "amount": "125000"})
    assert result.paid is False


def test_nextpay_verify_rejects_missing_provider_order(monkeypatch):
    monkeypatch.setenv("NEXTPAY_API_KEY", "test-key")

    def fake_post(url, data, timeout):
        return FakeResponse({"code": 0, "amount": 125000, "Shaparak_Ref_Id": "ref"})

    monkeypatch.setattr("payment_gateways.requests.post", fake_post)
    result = NextPayGateway().verify("txn-123", 125000, {"trans_id": "np-token-123", "amount": "125000"})
    assert result.paid is False


def test_nextpay_network_failure_fails_closed(monkeypatch):
    monkeypatch.setenv("NEXTPAY_API_KEY", "test-key")

    def fake_post(url, data, timeout):
        import requests
        raise requests.Timeout()

    monkeypatch.setattr("payment_gateways.requests.post", fake_post)
    result = NextPayGateway().verify("txn-123", 125000, {"trans_id": "np-token-123", "amount": "125000"})
    assert result.paid is False
    assert "شبکه" in result.message
