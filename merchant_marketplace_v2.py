"""Advanced multi-vendor marketplace layer for Kharidino.

This extension deliberately leaves the storefront/home design and the existing
Order schema intact. It adds isolated seller suborders, seller-scoped earnings,
notifications, analytics and bulk inventory operations around the existing
checkout/order records.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session
from flask import abort, flash, redirect, render_template, request, url_for

from app import app, db, User, Order, OrderItem, Product, Store, Offer, admin_required
from merchant_marketplace import MerchantStore, SellerProduct, _seller_account, seller_required


SELLER_STATUSES = {
    "new": "جدید",
    "confirmed": "تأیید شده",
    "preparing": "در حال آماده‌سازی",
    "shipped": "ارسال شده",
    "delivered": "تحویل شده",
    "cancelled": "لغو شده",
}

STATUS_FLOW = {
    "new": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


class SellerOrder(db.Model):
    __tablename__ = "kharidino_seller_order"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="new", nullable=False, index=True)
    subtotal = db.Column(db.Integer, default=0, nullable=False)
    shipping_fee = db.Column(db.Integer, default=0, nullable=False)
    platform_fee = db.Column(db.Integer, default=0, nullable=False)
    seller_total = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    order = db.relationship("Order", backref=db.backref("seller_orders", lazy=True))
    store = db.relationship("Store")


class SellerOrderItem(db.Model):
    __tablename__ = "kharidino_seller_order_item"
    id = db.Column(db.Integer, primary_key=True)
    seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=False, index=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey("order_item.id"), nullable=False, unique=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    seller_order = db.relationship("SellerOrder", backref=db.backref("items", lazy=True, cascade="all, delete-orphan"))
    order_item = db.relationship("OrderItem")
    product = db.relationship("Product")


class SellerLedger(db.Model):
    __tablename__ = "kharidino_seller_ledger"
    id = db.Column(db.Integer, primary_key=True)
    seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=False, unique=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    gross = db.Column(db.Integer, default=0, nullable=False)
    shipping = db.Column(db.Integer, default=0, nullable=False)
    platform_fee = db.Column(db.Integer, default=0, nullable=False)
    net = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    seller_order = db.relationship("SellerOrder")


class SellerNotification(db.Model):
    __tablename__ = "kharidino_seller_notification"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)


def _merchant_store_ids():
    return {a.store_id for a in MerchantStore.query.filter_by(status="approved").all()}


def _offer_for_order_item(item):
    """Choose the deterministic seller offer that produced the checkout price."""
    offers = (
        Offer.query.join(Store, Offer.store_id == Store.id)
        .filter(Offer.product_id == item.product_id,
                Offer.price == item.price,
                Offer.in_stock.is_(True),
                Store.active.is_(True))
        .order_by(Offer.id.asc()).all()
    )
    approved = _merchant_store_ids()
    for offer in offers:
        if offer.store_id in approved:
            return offer
    return None


def sync_order_to_seller_orders(order):
    """Build seller suborders for an existing master order, idempotently."""
    if not order or not order.items:
        return []
    created = []
    existing_item_ids = {x.order_item_id for x in SellerOrderItem.query.join(SellerOrder).filter(SellerOrder.order_id == order.id).all()}
    grouped = {}
    for item in order.items:
        if item.id in existing_item_ids:
            continue
        offer = _offer_for_order_item(item)
        if offer:
            grouped.setdefault(offer.store_id, []).append((item, offer))
    for store_id, rows in grouped.items():
        sub = SellerOrder(order_id=order.id, store_id=store_id, status="new")
        db.session.add(sub)
        db.session.flush()
        subtotal = 0
        for item, _offer in rows:
            subtotal += int(item.price or 0) * int(item.quantity or 0)
            db.session.add(SellerOrderItem(
                seller_order_id=sub.id, order_item_id=item.id,
                product_id=item.product_id, product_name=item.product_name,
                price=item.price, quantity=item.quantity,
            ))
        sub.subtotal = subtotal
        sub.shipping_fee = 0
        # 5% is a placeholder marketplace fee and can be moved to a site setting later.
        sub.platform_fee = max(0, round(subtotal * 0.05))
        sub.seller_total = max(0, subtotal + sub.shipping_fee - sub.platform_fee)
        db.session.add(SellerLedger(
            seller_order_id=sub.id, store_id=store_id,
            gross=subtotal, shipping=sub.shipping_fee,
            platform_fee=sub.platform_fee, net=sub.seller_total,
            status="pending",
        ))
        db.session.add(SellerNotification(
            store_id=store_id, seller_order_id=sub.id,
            title="سفارش جدید",
            body=f"یک سفارش جدید برای فروشگاه شما ثبت شده است. سفارش اصلی #{order.id}",
        ))
        created.append(sub)
    return created


@event.listens_for(Session, "after_flush")
def _seller_order_after_flush(session_obj, flush_context):
    """Automatically split newly-created master orders after checkout flush."""
    processed = session_obj.info.setdefault("kharidino_seller_split_orders", set())
    for obj in list(session_obj.new):
        if isinstance(obj, Order) and obj.id and obj.id not in processed:
            processed.add(obj.id)
            sync_order_to_seller_orders(obj)


@app.context_processor
def inject_seller_workspace_globals():
    account = _seller_account()
    if not account or account.status != "approved":
        return {"seller_unread_notifications": 0}
    return {
        "seller_unread_notifications": SellerNotification.query.filter_by(store_id=account.store_id, is_read=False).count()
    }


@app.get("/seller/orders")
@seller_required
def seller_orders():
    account = _seller_account()
    orders = SellerOrder.query.filter_by(store_id=account.store_id).order_by(SellerOrder.id.desc()).all()
    return render_template("seller_orders.html", account=account, orders=orders, statuses=SELLER_STATUSES)


@app.post("/seller/orders/<int:seller_order_id>/status")
@seller_required
def seller_order_status(seller_order_id):
    account = _seller_account()
    order = SellerOrder.query.filter_by(id=seller_order_id, store_id=account.store_id).first_or_404()
    new_status = request.form.get("status", "").strip()
    if new_status not in SELLER_STATUSES:
        abort(400)
    if new_status != order.status and new_status not in STATUS_FLOW.get(order.status, set()):
        flash("این تغییر وضعیت در این مرحله مجاز نیست.", "warning")
        return redirect(url_for("seller_orders"))
    order.status = new_status
    ledger = SellerLedger.query.filter_by(seller_order_id=order.id).first()
    if ledger:
        if new_status == "delivered":
            ledger.status = "available"
        elif new_status == "cancelled":
            ledger.status = "cancelled"
        elif ledger.status != "paid":
            ledger.status = "pending"
    db.session.add(SellerNotification(
        store_id=account.store_id, seller_order_id=order.id,
        title="وضعیت سفارش تغییر کرد",
        body=f"وضعیت سفارش #{order.order_id} به «{SELLER_STATUSES[new_status]}» تغییر کرد.",
    ))
    db.session.commit()
    flash("وضعیت سفارش با موفقیت تغییر کرد. ✅", "success")
    return redirect(url_for("seller_orders"))


@app.post("/seller/notifications/read-all")
seller_required
def seller_notifications_read_all():
    account = _seller_account()
    SellerNotification.query.filter_by(store_id=account.store_id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("seller_orders"))


@app.get("/seller/finance")
@seller_required
def seller_finance():
    account = _seller_account()
    ledger = SellerLedger.query.filter_by(store_id=account.store_id).order_by(SellerLedger.id.desc()).all()
    totals = {
        "gross": sum(x.gross for x in ledger),
        "fee": sum(x.platform_fee for x in ledger),
        "net": sum(x.net for x in ledger),
        "available": sum(x.net for x in ledger if x.status == "available"),
        "paid": sum(x.net for x in ledger if x.status == "paid"),
    }
    return render_template("seller_finance.html", account=account, ledger=ledger, totals=totals)


@app.get("/seller/analytics")
@seller_required
def seller_analytics():
    account = _seller_account()
    orders = SellerOrder.query.filter_by(store_id=account.store_id).all()
    delivered = [x for x in orders if x.status == "delivered"]
    revenue = sum(x.seller_total for x in delivered)
    return render_template("seller_analytics.html", account=account, orders=orders, revenue=revenue,
                           total_orders=len(orders), delivered_orders=len(delivered), products=SellerProduct.query.filter_by(store_id=account.store_id).count())


@app.post("/seller/products/bulk-stock")
@seller_required
def seller_bulk_stock():
    account = _seller_account()
    action = request.form.get("action", "").strip()
    ids = []
    for raw in request.form.getlist("product_id"):
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if action not in {"on", "off"} or not ids:
        flash("عملیات موجودی نامعتبر است.", "warning")
        return redirect(url_for("seller_dashboard") + "#products")
    owned = SellerProduct.query.filter(SellerProduct.store_id == account.store_id, SellerProduct.product_id.in_(ids)).all()
    owned_ids = {x.product_id for x in owned}
    offers = Offer.query.filter(Offer.store_id == account.store_id, Offer.product_id.in_(owned_ids)).all()
    for offer in offers:
        offer.in_stock = action == "on"
    db.session.commit()
    flash(f"موجودی {len(owned_ids)} محصول به‌روزرسانی شد. ✅", "success")
    return redirect(url_for("seller_dashboard") + "#products")


@app.post("/admin/merchants/sync-orders")
@admin_required
def admin_sync_seller_orders():
    created = 0
    for order in Order.query.order_by(Order.id.asc()).all():
        created += len(sync_order_to_seller_orders(order))
    db.session.commit()
    flash(f"{created} زیرسفارش فروشنده‌ای همگام شد. ✅", "success")
    return redirect(url_for("admin_merchants"))
