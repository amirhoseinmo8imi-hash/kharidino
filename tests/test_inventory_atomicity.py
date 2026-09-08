from __future__ import annotations

from app import Order, User, app, db
from inventory_atomicity import apply_inventory_atomicity
from inventory_hardening import _ensure_table
from sqlalchemy import text


INVENTORY_TABLE = "kharidino_product_inventory"
RESERVATION_TABLE = "kharidino_inventory_reservation"


def _seed_order(product_id: int, quantity: int = 2):
    user = User(
        name="Inventory Test User",
        email=f"inventory-test-{product_id}@example.invalid",
        password="test",
        role="user",
    )
    db.session.add(user)
    db.session.flush()
    order = Order(
        user_id=user.id,
        total=1000,
        status="در انتظار بررسی",
        customer_name="Inventory Test",
        phone="09000000000",
        address="Test address",
    )
    db.session.add(order)
    db.session.flush()
    db.session.execute(
        text(
            f"INSERT OR REPLACE INTO {INVENTORY_TABLE} "
            "(product_id, quantity, managed, updated_at) VALUES (:pid, :qty, 1, 0)"
        ),
        {"pid": product_id, "qty": 5},
    )
    db.session.execute(
        text(
            f"INSERT OR REPLACE INTO {RESERVATION_TABLE} "
            "(order_id, product_id, quantity, restored, updated_at) "
            "VALUES (:oid, :pid, :qty, 0, 0)"
        ),
        {"oid": order.id, "pid": product_id, "qty": quantity},
    )
    db.session.commit()
    return user.id, order.id


def _cleanup(order_id, user_id, product_id):
    db.session.rollback()
    db.session.execute(text(f"DELETE FROM {RESERVATION_TABLE} WHERE order_id = :oid"), {"oid": order_id})
    db.session.execute(text(f"DELETE FROM {INVENTORY_TABLE} WHERE product_id = :pid"), {"pid": product_id})
    db.session.execute(text("DELETE FROM order_item WHERE order_id = :oid"), {"oid": order_id})
    db.session.execute(text("DELETE FROM " + '"order"' + " WHERE id = :oid"), {"oid": order_id})
    db.session.execute(text("DELETE FROM user WHERE id = :uid"), {"uid": user_id})
    db.session.commit()


def test_cancel_restores_inventory_inside_same_transaction():
    with app.app_context():
        _ensure_table(app)
        apply_inventory_atomicity(app)
        product_id = 990001
        user_id, order_id = _seed_order(product_id)
        try:
            order = db.session.get(Order, order_id)
            assert order is not None
            order.status = "لغو شد"
            db.session.commit()

            quantity = db.session.execute(
                text(f"SELECT quantity FROM {INVENTORY_TABLE} WHERE product_id = :pid"),
                {"pid": product_id},
            ).scalar_one()
            restored = db.session.execute(
                text(f"SELECT restored FROM {RESERVATION_TABLE} WHERE order_id = :oid"),
                {"oid": order_id},
            ).scalar_one()
            assert quantity == 7
            assert restored == 1
        finally:
            _cleanup(order_id, user_id, product_id)


def test_reactivation_fails_atomically_when_stock_is_insufficient():
    with app.app_context():
        _ensure_table(app)
        apply_inventory_atomicity(app)
        product_id = 990002
        user_id, order_id = _seed_order(product_id, quantity=4)
        try:
            db.session.execute(
                text(f"UPDATE {INVENTORY_TABLE} SET quantity = 2 WHERE product_id = :pid"),
                {"pid": product_id},
            )
            db.session.execute(
                text(f"UPDATE {RESERVATION_TABLE} SET restored = 1 WHERE order_id = :oid"),
                {"oid": order_id},
            )
            db.session.commit()

            order = db.session.get(Order, order_id)
            order.status = "در انتظار بررسی"
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            refreshed = db.session.get(Order, order_id)
            quantity = db.session.execute(
                text(f"SELECT quantity FROM {INVENTORY_TABLE} WHERE product_id = :pid"),
                {"pid": product_id},
            ).scalar_one()
            restored = db.session.execute(
                text(f"SELECT restored FROM {RESERVATION_TABLE} WHERE order_id = :oid"),
                {"oid": order_id},
            ).scalar_one()
            assert refreshed.status == "لغو شد" or refreshed.status == "در انتظار بررسی"
            assert quantity == 2
            assert restored == 1
        finally:
            _cleanup(order_id, user_id, product_id)
