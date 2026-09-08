"""Checkout validation that must run before inventory reservation."""
from __future__ import annotations

from flask import abort, request, session


def apply_checkout_preflight(app) -> None:
    if getattr(app, "_kharidino_checkout_preflight", False):
        return

    @app.before_request
    def _checkout_preflight():
        if request.endpoint != "checkout" or request.method != "POST":
            return None
        if not session.get("user_id"):
            return None
        required = ("customer_name", "phone", "address")
        if any(not request.form.get(field, "").strip() for field in required):
            abort(400, description="نام، شماره تماس و آدرس الزامی است.")
        return None

    app._kharidino_checkout_preflight = True
