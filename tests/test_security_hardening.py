import io
import os

import pytest
from flask import Flask

from security_hardening import apply_security, csrf_token


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cf000000020001e221bc33"
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


def test_cross_site_state_change_is_blocked():
    app = make_app()

    @app.post("/mutate")
    def mutate():
        return "changed"

    response = app.test_client().post(
        "/mutate",
        headers={"Origin": "https://evil.example"},
    )
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
