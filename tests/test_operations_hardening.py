from flask import Flask

from checkout_preflight import apply_checkout_preflight
from app import app as main_app, db
import system_health  # noqa: F401


def test_healthz_is_minimal_and_database_backed():
    client = main_app.test_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}


def test_system_health_dashboard_requires_admin():
    client = main_app.test_client()
    response = client.get("/admin/system-health")
    assert response.status_code in (302, 403)


def test_checkout_preflight_blocks_invalid_checkout_before_business_route():
    test_app = Flask(__name__)
    test_app.config.update(TESTING=True, SECRET_KEY="checkout-preflight-test")
    apply_checkout_preflight(test_app)

    @test_app.post("/checkout")
    def checkout():
        return "business route reached"

    client = test_app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 7
        sess["cart"] = {"1": 1}

    invalid = client.post("/checkout", data={"customer_name": "", "phone": "", "address": ""})
    assert invalid.status_code == 400
    assert b"business route reached" not in invalid.data

    valid = client.post("/checkout", data={"customer_name": "Test", "phone": "09000000000", "address": "Test address"})
    assert valid.status_code == 200
    assert valid.data == b"business route reached"
