from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_storefront_uses_runtime_csrf_token_with_safe_fallback():
    base = _read("templates/base.html")
    assert "csrf_token() if csrf_token is defined and not (csrf_token is string)" in base
    assert 'name="csrf-token"' in base
    assert 'name="csrf_token"' in base


def test_security_layer_provides_and_enforces_browser_csrf():
    security = _read("security_hardening.py")
    assert 'app.jinja_env.globals["csrf_token"] = csrf_token' in security
    assert 'if request.method in {"POST", "PUT", "PATCH", "DELETE"}' in security
    assert "_check_same_origin()" in security
    assert "_check_csrf()" in security
    assert 'abort(403, description="Invalid or missing CSRF token.")' in security


def test_payment_callback_remains_provider_driven_while_browser_payment_forms_get_csrf():
    payment = _read("payment.py")
    assert 'token_factory = app.jinja_env.globals.get("csrf_token")' in payment
    assert 'render_template("payment_start.html", order=order, csrf_token=token, idempotency_key=key)' in payment
    assert '@app.route("/payment/callback/<string:transaction_id>", methods=["GET", "POST"])' in payment


def test_security_hardening_uses_the_app_csrf_session_key():
    security = _read("security_hardening.py")
    assert 'session.get("csrf_token")' in security
    assert "_CSRF_SESSION_KEY" not in security or "_CSRF_SESSION_KEY" in security and 'session.get(_CSRF_SESSION_KEY)' not in security


def test_app_initialization_does_not_seed_on_import():
    app = _read("app.py")
    assert "seed_demo_vehicle_ads(db, User)" not in app.split("if __name__ == \"__main__\":", 1)[0]
