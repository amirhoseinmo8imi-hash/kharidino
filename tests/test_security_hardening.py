import io
import os
import hashlib

import pytest
from flask import Flask

from app import db
from security_hardening import apply_security, csrf_token, _is_safe_local_redirect

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8cfc0f01f00050001ff89993d1d"
    "0000000049454e44ae426082"
)


def make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "unit-test-secret"
    apply_security(app)
    return app


def test_security_headers_and_cookie_flags(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-that-is-not-used-in-production")
    monkeypatch.delenv("FLASK_ENV", raising=False)
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    apply_security(app)

    @app.get("/")
    def home():
        from flask import session
        session["x"] = "1"
        return "ok"

    response = app.test_client().get("/")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Content-Security-Policy" in response.headers
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_csrf_token_required_and_valid_token_allowed():
    app = make_app()

    @app.get("/token")
    def token():
        return csrf_token()

    @app.post("/mutate")
    def mutate():
        return "changed"

    client = app.test_client()
    token_value = client.get("/token").get_data(as_text=True)
    missing = client.post("/mutate", headers={"Origin": "http://localhost"})
    assert missing.status_code == 403
    valid = client.post(
        "/mutate",
        data={"csrf_token": token_value},
        headers={"Origin": "http://localhost"},
    )
    assert valid.status_code == 200


def test_auth_form_csrf_token_survives_get_to_post():
    app = make_app()

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if __import__("flask").request.method == "POST":
            return "logged-in"
        return csrf_token()

    client = app.test_client()
    token_value = client.get("/login").get_data(as_text=True)
    response = client.post(
        "/login",
        data={"csrf_token": token_value},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200


def test_auth_success_does_not_rotate_csrf_token_after_response():
    app = make_app()

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if __import__("flask").request.method == "POST":
            return "registered"
        return csrf_token()

    client = app.test_client()
    token_value = client.get("/register").get_data(as_text=True)
    response = client.post(
        "/register",
        data={"csrf_token": token_value},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess["_kharidino_csrf_token"] == token_value


def test_cross_site_state_change_is_blocked():
    app = make_app()

    @app.post("/mutate")
    def mutate():
        return "changed"

    response = app.test_client().post("/mutate", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_production_rejects_known_default_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    app = Flask(__name__)
    with pytest.raises(RuntimeError):
        apply_security(app)


def test_real_image_content_is_accepted():
    app = make_app()

    @app.post("/upload")
    def upload():
        return "ok"

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_kharidino_csrf_token"] = "a" * 64

    response = client.post(
        "/upload",
        data={"file": (io.BytesIO(PNG_1X1), "photo.png")},
        headers={"Origin": "http://localhost", "X-CSRF-Token": "a" * 64},
    )
    assert response.status_code == 200


def test_mismatched_image_content_is_rejected():
    app = make_app()

    @app.post("/upload")
    def upload():
        return "ok"

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_kharidino_csrf_token"] = "a" * 64

    response = client.post(
        "/upload",
        data={"file": (io.BytesIO(PNG_1X1), "photo.jpg")},
        headers={"Origin": "http://localhost", "X-CSRF-Token": "a" * 64},
    )
    assert response.status_code == 400


def test_local_redirect_policy():
    assert _is_safe_local_redirect("/cart")
    assert _is_safe_local_redirect("/product/12?next=/cart")
    assert not _is_safe_local_redirect("https://evil.example")
    assert not _is_safe_local_redirect("//evil.example")
    assert not _is_safe_local_redirect("javascript:alert(1)")
    assert not _is_safe_local_redirect("/\\evil.example")
    assert not _is_safe_local_redirect("/\x00evil")


def test_mobile_api_get_rate_limit():
    app = make_app()

    @app.get("/api/mobile/ping")
    def ping():
        return "ok"

    client = app.test_client()
    for _ in range(120):
        response = client.get("/api/mobile/ping")
        assert response.status_code == 200
    assert client.get("/api/mobile/ping").status_code == 429


def test_login_rejects_unsafe_next_before_route_logic():
    app = make_app()

    @app.get("/login")
    @app.post("/login")
    def login():
        return "login"

    client = app.test_client()
    assert client.get("/login").status_code == 200
    with client.session_transaction() as sess:
        sess["_kharidino_csrf_token"] = "b" * 64

    response = client.post(
        "/login?next=https://evil.example",
        data={"csrf_token": "b" * 64},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 400


def _register_checkout_route(app):
    @app.get("/token")
    def token():
        return csrf_token()

    @app.post("/checkout")
    def checkout():
        return "order-created"


def test_checkout_idempotency_is_database_backed_across_app_instances():
    app1 = make_app()
    _register_checkout_route(app1)
    client1 = app1.test_client()
    token1 = client1.get("/token").get_data(as_text=True)
    with client1.session_transaction() as sess:
        sess["user_id"] = 424242
        sess["cart"] = {"991001": 1}

    data = {
        "customer_name": "Test User 424242",
        "phone": "09000000001",
        "address": "Test Address",
        "note": "database idempotency",
        "csrf_token": token1,
    }

    first = client1.post("/checkout", data=data, headers={"Origin": "http://localhost"})
    assert first.status_code == 200

    app2 = make_app()
    _register_checkout_route(app2)
    client2 = app2.test_client()
    token2 = client2.get("/token").get_data(as_text=True)
    with client2.session_transaction() as sess:
        sess["user_id"] = 424242
        sess["cart"] = {"991001": 1}

    data["csrf_token"] = token2
    second = client2.post("/checkout", data=data, headers={"Origin": "http://localhost"})
    assert second.status_code == 409

    payload = "|".join([
        "424242",
        repr(sorted((("991001", "1"),))),
        "Test User 424242",
        "09000000001",
        "Test Address",
        "database idempotency",
    ])
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    from sqlalchemy import text
    with db.engine.begin() as connection:
        connection.execute(
            text("DELETE FROM kharidino_checkout_guard WHERE fingerprint = :fingerprint"),
            {"fingerprint": fingerprint},
        )


def test_upload_size_limit_is_enforced_when_content_length_is_known():
    app = make_app()

    @app.post("/upload")
    def upload():
        return "ok"

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_kharidino_csrf_token"] = "a" * 64

    response = client.post(
        "/upload",
        data={"file": (io.BytesIO(PNG_1X1), "photo.png")},
        headers={"Origin": "http://localhost", "X-CSRF-Token": "a" * 64},
        content_length=101 * 1024 * 1024,
    )
    assert response.status_code == 413
