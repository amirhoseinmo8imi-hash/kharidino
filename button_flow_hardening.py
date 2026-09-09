"""Small cross-cutting hardening for state-changing UI actions.

Keeps button behavior safe even when a user reaches the endpoint directly instead
of using the rendered UI. The existing CSRF middleware remains authoritative.
"""
from __future__ import annotations

from flask import abort, redirect, request, url_for


def _safe_local_target(value: str | None, fallback: str) -> str:
    value = (value or "").strip()
    if not value or not value.startswith("/") or value.startswith("//"):
        return fallback
    return value


def apply_button_flow_hardening(app, db, Store):
    if getattr(app, "_kharidino_button_flow_hardening", False):
        return app

    @app.before_request
    def _button_flow_guard():
        # Compare removal historically redirected to Referer verbatim. Keep the
        # UX while ensuring an attacker cannot turn the action into an external
        # redirect if a crafted Referer is supplied.
        if request.endpoint == "compare_remove" and request.method == "POST":
            return None

        # A seller-owned Store must not be physically deleted by the generic
        # admin store button: MerchantStore keeps a one-to-one FK to it. Convert
        # this destructive action into a safe deactivation and let the normal
        # admin flow continue for ordinary stores.
        if request.path.startswith("/admin/store/delete/") and request.method == "POST":
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
        # Normalize redirects emitted by compare_remove without changing the
        # endpoint's existing behavior for ordinary same-site referrers.
        if request.endpoint == "compare_remove" and response.status_code in {301, 302, 303, 307, 308}:
            fallback = url_for("compare")
            location = response.headers.get("Location", "")
            safe = _safe_local_target(location, fallback)
            response.headers["Location"] = safe
        return response

    app._kharidino_button_flow_hardening = True
    return app
