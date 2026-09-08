from flask import Flask, redirect

from redirect_hardening import apply_redirect_hardening


def test_external_redirect_is_rewritten_to_local_home():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    @app.get("/")
    def home():
        return "home"

    @app.get("/bounce")
    def bounce():
        return redirect("https://evil.example/phish")

    apply_redirect_hardening(app)
    response = app.test_client().get("/bounce")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_local_redirect_is_preserved():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    @app.get("/")
    def home():
        return "home"

    @app.get("/cart")
    def cart():
        return "cart"

    @app.get("/bounce")
    def bounce():
        return redirect("/cart")

    apply_redirect_hardening(app)
    response = app.test_client().get("/bounce")
    assert response.headers["Location"] == "/cart"
