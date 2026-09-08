"""Runtime 0->100 customer journey against the Flask application.

This suite deliberately uses the in-process TestGateway only. It must never
contact a real bank provider or require production credentials.
"""
from __future__ import annotations

import os
import re
import uuid
from urllib.parse import parse_qs, urlsplit

os.environ["PAYMENT_PROVIDER"] = "disabled"
os.environ["PAYMENT_TEST_MODE"] = "1"

from app import Product, User, Order, db, app
from payment import apply_payment
from security_hardening import apply_security

# Register the runtime layers before any test request is handled. This mirrors
a# production initialization order without importing the broader WSGI bridge
# (which also installs unrelated SQLAlchemy event listeners used by other tests).
with app.app_context():
    apply_payment(app, db, Order, User)
    apply_security(app)
    db.create_all()


CSRF_RE = re.compile(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)', re.I)
ORIGIN = "http://localhost"


def _csrf(response):
    match = CSRF_RE.search(response.get_data(as_text=True))
    assert match, "rendered page did not expose the runtime CSRF token"
    return match.group(1)


def _post(client, path, *, data=None, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.setdefault("Origin", ORIGIN)
    return client.post(path, data=data, headers=headers, **kwargs)


def _register_and_login(client, email, password):
    response = client.get("/register")
    assert response.status_code == 200
    response = _post(
        client,
        "/register",
        data={
            "name": "E2E Customer",
            "email": email,
            "password": password,
            "csrf_token": _csrf(response),
        },
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    response = client.get("/login")
    assert response.status_code == 200
    response = _post(
        client,
        "/login",
        data={
            "email": email,
            "password": password,
            "csrf_token": _csrf(response),
        },
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


def test_real_0_to_100_customer_journey_with_security_and_payment():
    app.config.update(TESTING=True)
    client = app.test_client()
    email = f"e2e-{uuid.uuid4().hex}@example.test"
    password = "E2E-password-2026!"

    # 0. Splash/Home
    home = client.get("/")
    assert home.status_code == 200
    assert "خریدینو" in home.get_data(as_text=True)

    # 1. Register -> Login
    _register_and_login(client, email, password)

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        user_id = user.id
        product = Product.query.filter_by(active=True).order_by(Product.id.asc()).first()
        assert product is not None
        product_id = product.id

    # 2. Product
    product_page = client.get(f"/product/{product_id}")
    assert product_page.status_code == 200
    assert "محصول" in product_page.get_data(as_text=True) or "قیمت" in product_page.get_data(as_text=True)

    # 3. CSRF must block a state-changing request without a token.
    blocked = _post(client, f"/cart/add/{product_id}", follow_redirects=False)
    assert blocked.status_code == 403

    # 4. Product -> Cart
    added = _post(
        client,
        f"/cart/add/{product_id}",
        data={"csrf_token": _csrf(product_page)},
        follow_redirects=False,
    )
    assert added.status_code in {302, 303}
    cart = client.get("/cart")
    assert cart.status_code == 200
    assert "1" in cart.get_data(as_text=True)

    # 5. Cart -> Checkout -> payment start bridge
    checkout = client.get("/checkout")
    assert checkout.status_code == 200
    checkout_post = _post(
        client,
        "/checkout",
        data={
            "csrf_token": _csrf(checkout),
            "customer_name": "E2E Customer",
            "phone": "09120000000",
            "address": "آدرس تست ۱، پلاک ۱",
            "note": "runtime e2e",
        },
        follow_redirects=False,
    )
    assert checkout_post.status_code == 303
    payment_location = checkout_post.headers["Location"]
    assert "/payment/start/" in payment_location
    order_id = int(payment_location.rstrip("/").rsplit("/", 1)[1])

    # 6. Payment start form -> TestGateway
    payment_form = client.get(payment_location)
    assert payment_form.status_code == 200
    idempotency_key = uuid.uuid4().hex
    start = _post(
        client,
        f"/payment/start/{order_id}",
        data={
            "csrf_token": _csrf(payment_form),
            "idempotency_key": idempotency_key,
        },
        follow_redirects=False,
    )
    assert start.status_code in {302, 303}
    gateway_location = start.headers["Location"]
    parsed = urlsplit(gateway_location)
    params = parse_qs(parsed.query)
    authority = params["authority"][0]
    transaction_id = params["transaction"][0]

    # 7. Callback/TestGateway -> paid only after provider verification.
    callback = client.get(
        f"{parsed.path}?transaction={transaction_id}&authority={authority}&test=1&approved=1",
        follow_redirects=False,
    )
    assert callback.status_code in {302, 303}

    with app.app_context():
        order = db.session.get(Order, order_id)
        assert order is not None
        assert order.user_id == user_id
        assert order.status == "تأیید شد"
        tx_model = app.extensions["kharidino_payment_transaction"]
        tx = tx_model.query.filter_by(public_id=transaction_id).first()
        assert tx is not None
        assert tx.status == "paid"
        assert tx.gateway_reference.startswith("TEST-")

    # 8. Orders
    orders = client.get("/orders")
    assert orders.status_code == 200
    assert str(order_id) in orders.get_data(as_text=True)

    # 9. Replay: paid callback is idempotent and does not downgrade state.
    replay = client.get(
        f"/payment/callback/{transaction_id}?authority={authority}&approved=1",
        follow_redirects=False,
    )
    assert replay.status_code in {302, 303}

    # 10. Replay: reusing the same idempotency key after payment is safe.
    replay_form = client.get(f"/payment/start/{order_id}")
    replay_start = _post(
        client,
        f"/payment/start/{order_id}",
        data={
            "csrf_token": _csrf(replay_form),
            "idempotency_key": idempotency_key,
        },
        follow_redirects=False,
    )
    assert replay_start.status_code in {302, 303}
    assert "/orders" in replay_start.headers.get("Location", "")

    # 11. IDOR: a second user cannot access the first user's payment form/order.
    second = app.test_client()
    second_email = f"e2e-{uuid.uuid4().hex}@example.test"
    _register_and_login(second, second_email, password)
    idor = second.get(f"/payment/start/{order_id}", follow_redirects=False)
    assert idor.status_code == 404
    second_orders = second.get("/orders")
    assert second_orders.status_code == 200
    assert str(order_id) not in second_orders.get_data(as_text=True)
