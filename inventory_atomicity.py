"""Transactional inventory bridge for order status changes.

The legacy inventory module performs checkout reservation in before_request.
This module keeps that behavior, but moves cancellation/restoration into the
SQLAlchemy flush transaction so invalid order-status requests cannot mutate
stock before the business route accepts the transition.
"""
from __future__ import annotations

import time

from flask import abort, flash, redirect, request, session, url_for
from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session

from inventory_hardening import (
    _TABLE,
    _RESERVATION_TABLE,
    _reserve_managed_stock,
    _sync_cart_to_inventory,
    _validate_cart_quantities,
)


def _set_offer_stock(session_obj, product_id: int, quantity: int) -> None:
    session_obj.execute(
        text("UPDATE offer SET in_stock = :in_stock WHERE product_id = :product_id"),
        {"product_id": int(product_id), "in_stock": quantity > 0},
    )


def _restore_order_inventory_atomic(session_obj, order_id: int) -> None:
    rows = session_obj.execute(
        text(
            f"SELECT product_id, quantity FROM {_RESERVATION_TABLE} "
            "WHERE order_id = :order_id AND restored = 0"
        ),
        {"order_id": int(order_id)},
    ).mappings().all()
    now = time.time()
    for row in rows:
        product_id = int(row["product_id"])
        quantity = int(row["quantity"])
        session_obj.execute(
            text(
                f"UPDATE {_TABLE} SET quantity = quantity + :quantity, "
                "updated_at = :updated_at WHERE product_id = :product_id AND managed = 1"
            ),
            {"product_id": product_id, "quantity": quantity, "updated_at": now},
        )
        session_obj.execute(
            text(
                f"UPDATE {_RESERVATION_TABLE} SET restored = 1, updated_at = :updated_at "
                "WHERE order_id = :order_id AND product_id = :product_id AND restored = 0"
            ),
            {"order_id": int(order_id), "product_id": product_id, "updated_at": now},
        )
        remaining = session_obj.execute(
            text(f"SELECT quantity FROM {_TABLE} WHERE product_id = :product_id"),
            {"product_id": product_id},
        ).scalar_one_or_none()
        if remaining is not None:
            _set_offer_stock(session_obj, product_id, int(remaining))


def _reserve_order_inventory_atomic(session_obj, order_id: int) -> None:
    rows = session_obj.execute(
        text(
            f"SELECT product_id, quantity FROM {_RESERVATION_TABLE} "
            "WHERE order_id = :order_id AND restored = 1"
        ),
        {"order_id": int(order_id)},
    ).mappings().all()
    now = time.time()
    for row in rows:
        product_id = int(row["product_id"])
        quantity = int(row["quantity"])
        result = session_obj.execute(
            text(
                f"UPDATE {_TABLE} SET quantity = quantity - :quantity, "
                "updated_at = :updated_at "
                "WHERE product_id = :product_id AND managed = 1 AND quantity >= :quantity"
            ),
            {"product_id": product_id, "quantity": quantity, "updated_at": now},
        )
        if result.rowcount != 1:
            abort(409, description="موجودی برای فعال‌سازی دوباره سفارش کافی نیست.")
        session_obj.execute(
            text(
                f"UPDATE {_RESERVATION_TABLE} SET restored = 0, updated_at = :updated_at "
                "WHERE order_id = :order_id AND product_id = :product_id AND restored = 1"
            ),
            {"order_id": int(order_id), "product_id": product_id, "updated_at": now},
        )
        remaining = session_obj.execute(
            text(f"SELECT quantity FROM {_TABLE} WHERE product_id = :product_id"),
            {"product_id": product_id},
        ).scalar_one()
        _set_offer_stock(session_obj, product_id, int(remaining))


def apply_inventory_atomicity(app) -> None:
    """Replace the pre-route status inventory mutation with transactional hooks."""
    if getattr(app, "_kharidino_inventory_atomicity_applied", False):
        return

    # The legacy handler mutates stock in before_request, before the route has
    # validated the requested status transition. Remove only that handler.
    handlers = app.before_request_funcs.get(None, [])
    app.before_request_funcs[None] = [
        fn for fn in handlers if getattr(fn, "__name__", "") != "_inventory_before_request"
    ]

    @app.before_request
    def _inventory_atomicity_before_request():
        if request.endpoint == "cart_add" and request.method == "POST":
            try:
                pid = int(request.view_args.get("product_id"))
                current = session.get("cart", {})
                if not isinstance(current, dict):
                    current = {}
                current_qty = int(current.get(str(pid), 0) or 0)
                ok, failed_pid, available = _validate_cart_quantities(pid, current_qty + 1)
            except (TypeError, ValueError):
                abort(400, description="تعداد کالا نامعتبر است.")
            if not ok:
                flash(f"موجودی این کالا فقط {available} عدد است.", "warning")
                return redirect(request.referrer or url_for("product_detail", product_id=failed_pid))
        elif request.endpoint == "cart_update" and request.method == "POST":
            ok, pid, available = _validate_cart_quantities()
            if not ok:
                flash(f"موجودی کالا برای این تعداد کافی نیست؛ حداکثر {available} عدد قابل انتخاب است.", "warning")
                return redirect(url_for("cart"))
        elif request.endpoint == "cart":
            _sync_cart_to_inventory()
        # IMPORTANT: order-status inventory is intentionally absent here.
        _reserve_managed_stock()

    if not getattr(app, "_kharidino_inventory_atomicity_session_hook", False):
        @event.listens_for(Session, "before_flush")
        def _inventory_status_before_flush(session_obj, flush_context, instances):
            from app import Order

            for order in list(session_obj.dirty):
                if not isinstance(order, Order):
                    continue
                history = inspect(order).attrs.status.history
                if not history.has_changes() or not history.deleted or not history.added:
                    continue
                old_status = history.deleted[0]
                new_status = history.added[0]
                if old_status == new_status:
                    continue
                if old_status != "لغو شد" and new_status == "لغو شد":
                    _restore_order_inventory_atomic(session_obj, order.id)
                elif old_status == "لغو شد" and new_status != "لغو شد":
                    _reserve_order_inventory_atomic(session_obj, order.id)

        app._kharidino_inventory_atomicity_session_hook = True

    app._kharidino_inventory_atomicity_applied = True
