import os

import pytest
from flask import Flask

from security_hardening import apply_security


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

    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "Content-Security-Policy" in response.headers
    cookie = response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_cross_site_state_change_is_blocked(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret")
    app = Flask(__name__)
    app.config["TESTING"] = True
    apply_security(app)

    @app.post("/mutate")
    def mutate():
        return "changed"

    response = app.test_client().post(
        "/mutate",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_same_origin_state_change_is_allowed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret")
    app = Flask(__name__)
    app.config["TESTING"] = True
    apply_security(app)

    @app.post("/mutate")
    def mutate():
        return "changed"

    response = app.test_client().post(
        "/mutate",
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 200


def test_production_rejects_known_default_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")
    app = Flask(__name__)
    with pytest.raises(RuntimeError):
        apply_security(app)
