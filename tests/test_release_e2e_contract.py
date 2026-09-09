"""Release-level contract checks for the customer checkout/payment journey.

These tests stay provider-neutral: CI must never call a real bank gateway.
They verify the application wiring and fail-closed payment configuration.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_customer_journey_contract_is_present():
    app = _read("app.py")
    payment = _read("payment.py")
    for route in ("/login", "/product/", "/cart", "/checkout", "/orders"):
        assert route in app or route in payment
    assert '@app.post("/payment/start/<int:order_id>")' in payment
    assert '@app.route("/payment/callback/<string:transaction_id>"' in payment


def test_checkout_to_payment_bridge_is_explicit_and_owned():
    payment = _read("payment.py")
    start = payment.index('def payment_checkout_bridge(')
    end = payment.index('\n\n    @app.get("/payment/start/', start)
    block = payment[start:end]
    assert 'session.pop("checkout_payment_order_id", None)' in block
    assert 'order.user_id == session.get("user_id")' in block
    assert 'response.status_code = 303' in block
    assert 'url_for("payment_start_form", order_id=order.id)' in block


def test_payment_start_uses_branded_template_without_changing_post_flow():
    payment = _read("payment.py")
    start = payment.index('def payment_start_form(')
    end = payment.index('\n\n    app._kharidino_payment', start)
    block = payment[start:end]
    assert 'render_template(' in block
    assert '"payment_start.html"' in block
    assert 'csrf_token=token' in block
    assert 'idempotency_key=key' in block
    assert 'uuid.uuid4().hex' in block


def test_payment_start_has_no_secret_or_test_gateway_fallback_in_route():
    payment = _read("payment.py")
    start = payment.index('def payment_start(')
    end = payment.index('\n\n    @app.route("/payment/callback/', start)
    block = payment[start:end]
    assert 'gateway = _gateway()' in block
    assert 'if result.status != "redirect":' in block
    assert 'abort(503, description="درگاه پرداخت در دسترس نیست.")' in block
    assert 'PAYMENT_TEST_MODE' not in block


def test_production_gateway_selection_is_fail_closed_and_provider_selectable():
    payment = _read("payment.py")
    start = payment.index('def _gateway()')
    end = payment.index('\n\n\ndef _idempotency_key', start)
    block = payment[start:end]
    assert 'TestGateway()' in block
    assert 'return DisabledGateway()' in block
    assert 'PAYMENT_TEST_MODE' in block
    assert 'PAYMENT_PROVIDER' in block
    assert 'provider == "nextpay"' in block
    assert 'NextPayGateway' in block


def test_nextpay_adapter_is_present_and_provider_neutral_layer_remains():
    gateway = _read("payment_gateways.py")
    assert 'class NextPayGateway' in gateway
    assert 'NEXTPAY_API_KEY' in gateway
    assert 'PAYMENT_HTTP_TIMEOUT' in gateway
    assert 'https://nextpay.org/nx/gateway/token' in gateway
    assert 'https://nextpay.org/nx/gateway/verify' in gateway
    assert 'Shaparak_Ref_Id' in gateway


def test_callback_requires_provider_verification_before_paid_transition():
    payment = _read("payment.py")
    start = payment.index('def payment_callback(')
    end = payment.index('\n\n    @app.post("/payment/refund/', start)
    block = payment[start:end]
    assert 'result = gateway.verify(' in block
    assert block.index('result = gateway.verify(') < block.index('tx.status = "paid"')
    assert 'tx.gateway_reference = result.reference[:200]' in block


def test_environment_template_documents_provider_secrets_only():
    env = ROOT / ".env.example"
    assert env.exists()
    source = env.read_text(encoding="utf-8")
    assert "PAYMENT_PROVIDER" in source
    assert "PAYMENT_CALLBACK_SECRET" in source
    assert "PAYMENT_TEST_MODE" in source
    assert "NEXTPAY_API_KEY" in source
    assert "SECRET_KEY" in source
