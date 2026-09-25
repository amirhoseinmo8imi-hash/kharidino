"""Customer-side marketplace integration for seller suborders."""
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app import app, db, Order
from merchant_marketplace_v2 import SellerOrder, SellerLedger, SellerNotification


@app.context_processor
def inject_customer_marketplace_orders():
    user_id = __import__("flask").session.get("user_id")
    if not user_id:
        return {"seller_orders_by_master": {}}
    rows = (SellerOrder.query.join(Order, SellerOrder.order_id == Order.id)
            .filter(Order.user_id == user_id)
            .order_by(SellerOrder.id.asc()).all())
    grouped = {}
    for row in rows:
        grouped.setdefault(row.order_id, []).append(row)
    return {"seller_orders_by_master": grouped}


@event.listens_for(Session, "after_flush")
def _sync_master_cancellation(session_obj, flush_context):
    for obj in list(session_obj.dirty):
        if not isinstance(obj, Order):
            continue
        state = inspect(obj)
        attr = state.attrs.status
        if not attr.history.has_changes() or obj.status not in {"لغو شد", "cancelled"}:
            continue
        subs = SellerOrder.query.filter_by(order_id=obj.id).all()
        for sub in subs:
            if sub.status in {"delivered", "cancelled"}:
                continue
            sub.status = "cancelled"
            ledger = SellerLedger.query.filter_by(seller_order_id=sub.id).first()
            if ledger:
                ledger.status = "cancelled"
            db.session.add(SellerNotification(
                store_id=sub.store_id,
                seller_order_id=sub.id,
                title="سفارش لغو شد",
                body=f"سفارش اصلی #{obj.id} توسط مشتری لغو شد.",
            ))
