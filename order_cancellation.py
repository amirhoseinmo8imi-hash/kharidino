"""Customer-owned master-order cancellation endpoint."""
from __future__ import annotations

from flask import flash, redirect, url_for, session


def apply_order_cancellation(app):
    """Register a safe customer cancellation endpoint once."""
    if getattr(app, "_kharidino_order_cancellation_applied", False):
        return app

    @app.post("/orders/<int:order_id>/cancel")
    def cancel_order(order_id):
        from app import Order, db

        if not session.get("user_id"):
            flash("ابتدا وارد حساب کاربری شوید.", "warning")
            return redirect(url_for("login", next=url_for("my_orders")))

        order = db.session.get(Order, order_id)
        if not order or order.user_id != session["user_id"]:
            flash("سفارش موردنظر پیدا نشد.", "danger")
            return redirect(url_for("my_orders"))

        if order.status != "در انتظار بررسی":
            flash("این سفارش دیگر قابل لغو نیست.", "warning")
            return redirect(url_for("my_orders"))

        order.status = "لغو شد"
        db.session.commit()
        flash("سفارش با موفقیت لغو شد.", "success")
        return redirect(url_for("my_orders"))

    app._kharidino_order_cancellation_applied = True
    return app
