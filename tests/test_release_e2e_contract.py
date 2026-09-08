"""Release-level contract checks for the customer checkout/payment journey.

These tests stay provider-neutral: CI must never call a real bank gateway.
They verify that the application exposes the expected flow and that the
production payment configuration cannot silently fall back to TestGateway.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_customer_journey_routes_exist_in_source():
    app = _read("app.py")
    payment = _read("payment.py")
    assert '@app.route("/login"' in app or '@app.post("/login")' in app
    assert '@app.route("/product/' in app or '@app.get("/product/' in app
    assert '@app.route("/cart"' in app or '@app.get("/cart")' in app
    assert '@app.route("/checkout"' in app or '@app.post("/checkout")' in app
    assert '@app.post("/payment/start/<int:order_id>")' in payment
    assert '@app.route("/payment/callback/<string:transaction_id>"' in payment
    assert '@app.route("/orders"' in app or '@app.get("/orders")' in app


def test_checkout_to_payment_bridge_is_explicit_and_owned():
    payment = _read("payment.py")
    start = payment.index('def payment_checkout_bridge(')
    end = payment.index('\n\n    @app.get("/payment/start/', start)
    block = payment[start:end]
    assert 'session.get("checkout_payment_order_id")' in block
    assert 'order.user_id == session.get("user_id")' in block
    assert 'response.status_code = 303' in block
    assert 'url_for("payment_start", order_id=order.id)' in block


def test_payment_start_has_no_secret_or_test_gateway_fallback_in_route():
    payment = _read("payment.py")
    start = payment.index('def payment_start(')
    end = payment.index('\n\n    @app.route("/payment/callback/', start)
    block = payment[start:end]
    assert 'gateway = _gateway()' in block
    assert 'if result.status != "redirect":' in block
    assert 'abort(503, description="درگاه پرداخت در دسترس نیست.")' in block
    assert 'PAYMENT_TEST_MODE' not in block


def test_production_gateway_selection_is_fail_closed():
    payment = _read("payment.py")
    start = payment.index('def _gateway()')
    end = payment.index('\n\n\ndef _idempotency_key', start)
    block = payment[start:end]
    assert 'TestGateway()' in block
    assert 'return DisabledGateway()' in block
    assert 'PAYMENT_TEST_MODE' in block


def test_callback_requires_provider_verification_before_paid_transition():
    payment = _read("payment.py")
    start = payment.index('def payment_callback(')
    end = payment.index('\n\n    @app.post("/payment/refund/', start)
    block = payment[start:end]
    assert 'result = gateway.verify(' in block
    assert block.index('result = gateway.verify(') < block.index('tx.status = "paid"')
    assert 'tx.gateway_reference = result.reference[:200]' in block


def test_environment_template_documents_secret_only_configuration():
    env = ROOT / ".env.example"
    if env.exists():
        source = env.read_text(encoding="utf-8")
        assert "PAYMENT_CALLBACK_SECRET" in source
        assert "PAYMENT_TEST_MODE" in source
        assert "SECRET_KEY" in source
