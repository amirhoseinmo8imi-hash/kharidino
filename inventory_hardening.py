"""Atomic product inventory enforcement for Kharidino.

Inventory is kept in a separate table so the existing Offer schema remains
backwards-compatible. Existing products start as unmanaged and therefore keep
the legacy Offer.in_stock behaviour until an administrator assigns a numeric
quantity. Once managed, checkout decrements quantity atomically in the same
SQLAlchemy transaction as the order.
"""
from __future__ import annotations

from flask import abort, request, session

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
        connection.execute(text(
            f"CREATE INDEX IF NOT EXISTS ix_{_TABLE}_managed ON {_TABLE}(managed)"
        ))


def _cart() -> list[tuple[int, int]]:
    raw_cart = session.get("cart", {})
    if not isinstance(raw_cart, dict):
        abort(400, description="سبد خرید نامعتبر است.")
    result: list[tuple[int, int]] = []
    for raw_id, raw_qty in raw_cart.items():
        try:
            product_id = int(raw_id)
            quantity = int(raw_qty)
        except (TypeError, ValueError):
            abort(400, description="سبد خرید نامعتبر است.")
        if product_id <= 0 or quantity < 1 or quantity > 99:
            abort(400, description="تعداد کالا نامعتبر است.")
        result.append((product_id, quantity))
    return result


def _reserve_managed_stock() -> None:
    """Atomically decrement every managed product in the current cart.

    The UPDATE uses `quantity >= requested` so concurrent checkouts cannot both
    consume the same final units. The caller's checkout route commits this
    transaction together with the Order/OrderItem rows.
    """
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
            # Migration-safe: products without an explicit inventory setting
            # continue to use the existing Offer.in_stock availability check.
            continue

        result = db.session.execute(
            text(f"""
                UPDATE {_TABLE}
                SET quantity = quantity - :quantity,
                    updated_at = :updated_at
                WHERE product_id = :product_id
                  AND managed = 1
                  AND quantity >= :quantity
            """),
            {
                "product_id": product_id,
                "quantity": quantity,
                "updated_at": __import__("time").time(),
            },
        )
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description="موجودی یکی از کالاها برای این تعداد کافی نیست.")


def _admin_set_inventory():
    from app import db
    from sqlalchemy import text
    import time

    try:
        product_id = int(request.form.get("product_id", ""))
        quantity = int(request.form.get("quantity", ""))
    except (TypeError, ValueError):
        abort(400, description="شناسه کالا یا موجودی نامعتبر است.")
    if product_id <= 0 or quantity < 0 or quantity > 2_147_483_647:
        abort(400, description="مقدار موجودی نامعتبر است.")

    db.session.execute(
        text(f"""
            INSERT INTO {_TABLE} (product_id, quantity, managed, updated_at)
            VALUES (:product_id, :quantity, 1, :updated_at)
            ON CONFLICT(product_id) DO UPDATE SET
                quantity = excluded.quantity,
                managed = 1,
                updated_at = excluded.updated_at
        """),
        {"product_id": product_id, "quantity": quantity, "updated_at": time.time()},
    )
    db.session.commit()
    return {"ok": True, "product_id": product_id, "quantity": quantity}


def apply_inventory_security(app) -> None:
    if getattr(app, "_kharidino_inventory_applied", False):
        return

    try:
        _ensure_table(app)
    except Exception:
        app.logger.exception("Unable to initialize product inventory table")
        if app.config.get("ENV") == "production":
            raise
        return

    @app.before_request
    def _inventory_before_request():
        _reserve_managed_stock()

    if not any(rule.rule == "/admin/inventory/set" for rule in app.url_map.iter_rules()):
        app.add_url_rule(
            "/admin/inventory/set",
            endpoint="admin_inventory_set",
            view_func=app.view_functions.get("admin_inventory_set") or _admin_set_inventory,
            methods=["POST"],
        )

    app._kharidino_inventory_applied = True
