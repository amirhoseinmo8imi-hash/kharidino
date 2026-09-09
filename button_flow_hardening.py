"""Small cross-cutting hardening for state-changing UI actions."""
from __future__ import annotations

from flask import abort, redirect, request, session, url_for


def _safe_local_target(value: str | None, fallback: str) -> str:
    value = (value or "").strip()
    if not value or not value.startswith("/") or value.startswith("//"):
        return fallback
    return value


def apply_button_flow_hardening(app, db, Store, User):
    if getattr(app, "_kharidino_button_flow_hardening", False):
        return app

    @app.before_request
    def _button_flow_guard():
        # The compare-remove endpoint uses Referer for its UX redirect. The
        # after-request guard below converts any external/malformed target to a
        # local compare page.
        if request.endpoint == "compare_remove" and request.method == "POST":
            return None

        # A seller-owned Store must not be physically deleted by the generic
        # admin store button: MerchantStore keeps a one-to-one FK to it. This
        # guard only runs for an authenticated admin; the normal admin decorator
        # remains authoritative for all other cases.
        if request.path.startswith("/admin/store/delete/") and request.method == "POST":
            user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
            if not user or user.role != "admin":
                return None
            try:
                store_id = int(request.path.rsplit("/", 1)[-1])
            except (TypeError, ValueError):
                abort(400)
            store = db.session.get(Store, store_id)
            if store is not None:
                try:
                    from merchant_marketplace import MerchantStore
                    merchant = MerchantStore.query.filter_by(store_id=store.id).first()
                except (ImportError, AttributeError):
                    merchant = None
                if merchant is not None:
                    store.active = False
                    merchant.status = "rejected"
                    db.session.commit()
                    return redirect(url_for("admin") + "#stores-admin")
        return None

    @app.after_request
    def _button_flow_redirect_guard(response):
        if request.endpoint == "compare_remove" and response.status_code in {301, 302, 303, 307, 308}:
            fallback = url_for("compare")
            location = response.headers.get("Location", "")
            response.headers["Location"] = _safe_local_target(location, fallback)
        return response

    app._kharidino_button_flow_hardening = True
    return app
