from flask import Flask

from app import BASE_DIR, db
from checkout_preflight import apply_checkout_preflight
from security_hardening import apply_security, csrf_token


# Use a deliberately synthetic product id so this contract test is not affected
# by products that may exist in the developer's persistent kharidino.db.
_SYNTHETIC_PRODUCT_ID = "2147483647"


def make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "checkout-preflight-test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(BASE_DIR / "kharidino.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        apply_security(app)
        apply_checkout_preflight(app)
    return app


def register_checkout(app):
    @app.get("/token")
    def token():
        return csrf_token()

    @app.post("/checkout")
    def checkout():
        return "created"


def authenticated_client(app):
    client = app.test_client()
    token = client.get("/token").get_data(as_text=True)
    with client.session_transaction() as sess:
        sess["user_id"] = 424243
        sess["cart"] = {_SYNTHETIC_PRODUCT_ID: 1}
    return client, token


def valid_data(token):
    return {
        "customer_name": "Test User",
        "phone": "09000000002",
        "address": "Test Address 123",
        "note": "",
        "csrf_token": token,
    }


def test_checkout_preflight_accepts_valid_customer_and_cart():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    response = client.post("/checkout", data=valid_data(token), headers={"Origin": "http://localhost"})
    assert response.status_code == 200


def test_checkout_preflight_rejects_missing_customer_field():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    data = valid_data(token)
    data["address"] = ""
    response = client.post("/checkout", data=data, headers={"Origin": "http://localhost"})
    assert response.status_code == 400


def test_checkout_preflight_rejects_invalid_phone():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    data = valid_data(token)
    data["phone"] = "not-a-phone"
    response = client.post("/checkout", data=data, headers={"Origin": "http://localhost"})
    assert response.status_code == 400


def test_checkout_preflight_rejects_empty_cart():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    with client.session_transaction() as sess:
        sess["cart"] = {}
    response = client.post("/checkout", data=valid_data(token), headers={"Origin": "http://localhost"})
    assert response.status_code == 400


def test_checkout_preflight_rejects_malformed_cart_quantity():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    with client.session_transaction() as sess:
        sess["cart"] = {_SYNTHETIC_PRODUCT_ID: "not-an-int"}
    response = client.post("/checkout", data=valid_data(token), headers={"Origin": "http://localhost"})
    assert response.status_code == 400


def test_checkout_preflight_rejects_oversized_note():
    app = make_app()
    register_checkout(app)
    client, token = authenticated_client(app)
    data = valid_data(token)
    data["note"] = "x" * 2001
    response = client.post("/checkout", data=data, headers={"Origin": "http://localhost"})
    assert response.status_code == 400
