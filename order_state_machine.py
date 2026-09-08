"""Canonical master-order state machine for Kharidino.

The legacy admin UI stores Persian display statuses in ``Order.status``.  This
module keeps those values for compatibility while enforcing a strict transition
matrix before the existing status route can mutate an order.
"""
from __future__ import annotations

from flask import abort, flash, redirect, request, url_for


ORDER_STATUSES = {
    "در انتظار بررسی",
    "تأیید شد",
    "در حال آماده‌سازی",
    "ارسال شد",
    "تحویل شد",
    "لغو شد",
}

ORDER_STATUS_FLOW = {
    "در انتظار بررسی": {"تأیید شد", "لغو شد"},
    "تأیید شد": {"در حال آماده‌سازی", "لغو شد"},
    "در حال آماده‌سازی": {"ارسال شد", "لغو شد"},
    "ارسال شد": {"تحویل شد"},
    "تحویل شد": set(),
    "لغو شد": set(),
}


def allowed_order_transition(old_status: str, new_status: str) -> bool:
    """Return whether a master order may move to ``new_status``."""
    if old_status == new_status:
        return True
    return new_status in ORDER_STATUS_FLOW.get(old_status, set())


def apply_order_state_machine(app) -> None:
    """Install a validation gate in front of the legacy admin status route."""
    if getattr(app, "_kharidino_order_state_machine_applied", False):
        return

    @app.before_request
    def _validate_master_order_transition():
        if request.endpoint != "update_order_status" or request.method != "POST":
            return None

        from app import Order, db

        order_id = request.view_args.get("order_id") if request.view_args else None
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)
        new_status = request.form.get("status", "").strip()

        if new_status not in ORDER_STATUSES:
            abort(400, description="وضعیت سفارش نامعتبر است.")

        if not allowed_order_transition(order.status, new_status):
            flash("تغییر وضعیت سفارش از این مرحله مجاز نیست.", "warning")
            return redirect(url_for("admin") + "#orders-admin")

        return None

    app._kharidino_order_state_machine_applied = True
