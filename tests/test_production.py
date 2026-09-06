import os

import pytest


@pytest.fixture(autouse=True)
def production_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("FLASK_DEBUG", "0")


def test_runtime_config_accepts_strong_secret():
    from run_kharidino import validate_runtime_config

    validate_runtime_config()


def test_runtime_config_rejects_missing_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    from run_kharidino import validate_runtime_config

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_runtime_config()


def test_security_headers_are_present():
    from run_kharidino import app

    client = app.test_client()
    response = client.get("/splash")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_existing_routes_are_not_broken():
    from run_kharidino import app

    client = app.test_client()

    # The splash gate intentionally redirects the homepage until the splash is accepted.
    response = client.get("/")
    assert response.status_code in {200, 302}

    response = client.get("/splash")
    assert response.status_code == 200
