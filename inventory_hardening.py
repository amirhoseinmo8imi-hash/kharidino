"""Atomic product inventory enforcement for Kharidino."""
from __future__ import annotations

import os
import time

from flask import abort, redirect, render_template, request, session, url_for

_TABLE = "kharidino_product_inventory"


def _ensure_table(app) -> None:
    from sqlalchemy import text
    from app import db
    with db.engine.begin() as connection:
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_TABLE} (
                product_id INTEGER PRIMARY KEY,
                quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                managed INTEGER NOT NULL DEFAULT 1 CHECK (managed IN (0, 1)),
                updated_at REAL NOT NULL
            )
        """))
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{_TABLE}_managed ON {_TABLE}(managed)"))


def _cart() -> list[tuple[int, int]]:
    raw_cart = session.get("cart", {})
    if not isinstance(raw_cart, dict):
        abort(400, description="سبد خرید نامعتبر است.")
    result = []
    for raw_id, raw_qty in raw_cart.items():
        try:
            product_id, quantity = int(raw_id), int(raw_qty)
        except (TypeError, ValueError):
            abort(400, description="سبد خرید نامعتبر است.")
        if product_id <= 0 or quantity < 1 or quantity > 99:
            abort(400, description="تعداد کالا نامعتبر است.")
        result.append((product_id, quantity))
    return result


def _reserve_managed_stock() -> None:
    if request.endpoint != "checkout" or request.method != "POST" or not session.get("user_id"):
        return
    from sqlalchemy import text
    from app import db
    for product_id, quantity in _cart():
        row = db.session.execute(
            text(f"SELECT quantity, managed FROM {_TABLE} WHERE product_id = :product_id"),
            {"product_id": product_id},
        ).mappings().first()
        if not row or not bool(row["managed"]):
            continue
        result = db.session.execute(
            text(f"""
                UPDATE {_TABLE}
                SET quantity = quantity - :quantity, updated_at = :updated_at
                WHERE product_id = :product_id AND managed = 1 AND quantity >= :quantity
            """),
            {"product_id": product_id, "quantity": quantity, "updated_at": time.time()},
        )
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description="موجودی یکی از کالاها برای این تعداد کافی نیست.")
        remaining = db.session.execute(
            text(f"SELECT quantity FROM {_TABLE} WHERE product_id = :product_id"),
            {"product_id": product_id},
        ).scalar_one()
        if remaining == 0:
            db.session.execute(
                text("UPDATE offer SET in_stock = 0 WHERE product_id = :product_id"),
                {"product_id": product_id},
            )


def _admin_set_inventory():
    from app import Product, admin_required, db
    from sqlalchemy import text

    @admin_required
    def _handler():
        try:
            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", ""))
        except (TypeError, ValueError):
            abort(400, description="شناسه کالا یا موجودی نامعتبر است.")
        if product_id <= 0 or quantity < 0 or quantity > 2_147_483_647:
            abort(400, description="مقدار موجودی نامعتبر است.")
        if not db.session.get(Product, product_id):
            abort(404, description="کالا پیدا نشد.")
        db.session.execute(
            text(f"""
                INSERT INTO {_TABLE} (product_id, quantity, managed, updated_at)
                VALUES (:product_id, :quantity, 1, :updated_at)
                ON CONFLICT(product_id) DO UPDATE SET
                    quantity = excluded.quantity, managed = 1, updated_at = excluded.updated_at
            """),
            {"product_id": product_id, "quantity": quantity, "updated_at": time.time()},
        )
        if quantity == 0:
            db.session.execute(text("UPDATE offer SET in_stock = 0 WHERE product_id = :product_id"), {"product_id": product_id})
        db.session.commit()
        return redirect(url_for("admin_inventory"))
    return _handler()


def _admin_inventory_page():
    from app import Product, admin_required, db
    from sqlalchemy import text

    @admin_required
    def _handler():
        products = Product.query.order_by(Product.id.desc()).all()
        rows = db.session.execute(text(f"SELECT product_id, quantity, managed, updated_at FROM {_TABLE}")).mappings().all()
        inventory = {int(row["product_id"]): row for row in rows}
        return render_template("inventory_admin.html", products=products, inventory=inventory)
    return _handler()


def apply_inventory_security(app) -> None:
    if getattr(app, "_kharidino_inventory_applied", False):
        return
    try:
        _ensure_table(app)
    except Exception:
        app.logger.exception("Unable to initialize product inventory table")
        if os.environ.get("FLASK_ENV", "").lower() == "production":
            raise
        return

    @app.before_request
    def _inventory_before_request():
        _reserve_managed_stock()

    if not any(rule.rule == "/admin/inventory" for rule in app.url_map.iter_rules()):
        app.add_url_rule("/admin/inventory", endpoint="admin_inventory", view_func=_admin_inventory_page, methods=["GET"])
    if not any(rule.rule == "/admin/inventory/set" for rule in app.url_map.iter_rules()):
        app.add_url_rule("/admin/inventory/set", endpoint="admin_inventory_set", view_func=_admin_set_inventory, methods=["POST"])
    app._kharidino_inventory_applied = True
