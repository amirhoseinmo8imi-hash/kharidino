from flask import Flask, redirect

from redirect_hardening import _safe_local_target, apply_redirect_hardening


def test_local_redirect_targets_only():
    assert _safe_local_target("/compare")
    assert _safe_local_target("/product/12?x=1")
    assert not _safe_local_target("https://evil.example/")
    assert not _safe_local_target("//evil.example/")
    assert not _safe_local_target("/\\evil.example/")
    assert not _safe_local_target("/\r\nLocation:https://evil.example/")


def test_compare_remove_external_location_is_replaced():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    @app.get("/compare")
    def compare():
        return "compare"

    @app.get("/compare/remove")
    def compare_remove():
        return redirect("https://evil.example/")

    apply_redirect_hardening(app)
    client = app.test_client()
    response = client.get("/compare/remove")
    assert response.status_code == 302
    assert response.headers["Location"] == "/compare"
