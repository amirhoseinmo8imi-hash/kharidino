"""Unified marketplace foundation for Kharidino.

This module deliberately builds on the existing commerce/payment/accounting modules
without changing their tables. It provides durable primitives for customer growth,
seller operations, fulfillment, support and product discovery.
"""
from datetime import datetime
from functools import wraps

from flask import jsonify, request, session

from app import app, db


class WishlistItem(db.Model):
    __tablename__ = "kharidino_wishlist_item"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)


class PriceAlert(db.Model):
    __tablename__ = "kharidino_price_alert"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    target_price = db.Column(db.Integer, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    triggered_at = db.Column(db.DateTime, nullable=True)


class ProductReview(db.Model):
    __tablename__ = "kharidino_product_review"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=True, index=True)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(180), default="", nullable=False)
    body = db.Column(db.Text, default="", nullable=False)
    verified_purchase = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "product_id", "order_id", name="uq_review_purchase"),)


class ProductQuestion(db.Model):
    __tablename__ = "kharidino_product_question"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    answered_at = db.Column(db.DateTime, nullable=True)


class CustomerWallet(db.Model):
    __tablename__ = "kharidino_customer_wallet"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0, nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    tier = db.Column(db.String(30), default="standard", nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class WalletTransaction(db.Model):
    __tablename__ = "kharidino_wallet_transaction"
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("kharidino_customer_wallet.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(30), nullable=False, index=True)
    reference = db.Column(db.String(120), unique=True, nullable=False)
    note = db.Column(db.String(300), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Coupon(db.Model):
    __tablename__ = "kharidino_coupon"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(20), default="percent", nullable=False)
    value = db.Column(db.Integer, default=0, nullable=False)
    min_order = db.Column(db.Integer, default=0, nullable=False)
    max_discount = db.Column(db.Integer, nullable=True)
    usage_limit = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, default=0, nullable=False)
    starts_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)


class CouponRedemption(db.Model):
    __tablename__ = "kharidino_coupon_redemption"
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("kharidino_coupon.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, unique=True)
    discount = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class CustomerNotification(db.Model):
    __tablename__ = "kharidino_customer_notification"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, default="", nullable=False)
    kind = db.Column(db.String(40), default="general", nullable=False, index=True)
    link = db.Column(db.String(500), default="", nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SellerStaff(db.Model):
    __tablename__ = "kharidino_seller_staff"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(40), default="operator", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("store_id", "user_id", name="uq_seller_staff_store_user"),)


class SellerProductMetric(db.Model):
    __tablename__ = "kharidino_seller_product_metric"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    views = db.Column(db.Integer, default=0, nullable=False)
    favorites = db.Column(db.Integer, default=0, nullable=False)
    sold_units = db.Column(db.Integer, default=0, nullable=False)
    revenue = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("store_id", "product_id", name="uq_seller_product_metric"),)


class Shipment(db.Model):
    __tablename__ = "kharidino_shipment"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=True, index=True)
    carrier = db.Column(db.String(80), default="", nullable=False)
    tracking_code = db.Column(db.String(120), default="", nullable=False, index=True)
    service = db.Column(db.String(60), default="standard", nullable=False)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    shipped_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ReturnRequest(db.Model):
    __tablename__ = "kharidino_return_request"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    reason = db.Column(db.String(300), nullable=False)
    details = db.Column(db.Text, default="", nullable=False)
    status = db.Column(db.String(30), default="requested", nullable=False, index=True)
    refund_amount = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)


class SupportTicket(db.Model):
    __tablename__ = "kharidino_support_ticket"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=True, index=True)
    subject = db.Column(db.String(180), nullable=False)
    priority = db.Column(db.String(20), default="normal", nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SupportMessage(db.Model):
    __tablename__ = "kharidino_support_message"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("kharidino_support_ticket.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    internal = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Referral(db.Model):
    __tablename__ = "kharidino_referral"
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    reward = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def _login_required_json(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"ok": False, "error": "authentication_required"}), 401
        return view(*args, **kwargs)
    return wrapped


def _json_int(value, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= minimum else None


def _product_payload(product):
    return {"id": product.id, "name": product.name, "price": product.price, "image": product.image or ""}


def apply_marketplace_ultimate(app_obj=None):
    """Register additive marketplace APIs; safe to call once during startup."""
    app_obj = app_obj or app
    if app_obj.extensions.get("kharidino_marketplace_ultimate"):
        return

    @app_obj.get("/api/marketplace/wishlist")
    @_login_required_json
    def marketplace_wishlist():
        from app import Product
        rows = WishlistItem.query.filter_by(user_id=session["user_id"]).order_by(WishlistItem.id.desc()).all()
        ids = [r.product_id for r in rows]
        products = Product.query.filter(Product.id.in_(ids)).all() if ids else []
        by_id = {p.id: p for p in products}
        return jsonify({"ok": True, "items": [_product_payload(by_id[i]) for i in ids if i in by_id]})

    @app_obj.post("/api/marketplace/wishlist/toggle")
    @_login_required_json
    def marketplace_wishlist_toggle():
        product_id = _json_int((request.get_json(silent=True) or {}).get("product_id"), 1)
        if not product_id:
            return jsonify({"ok": False, "error": "invalid_product"}), 400
        row = WishlistItem.query.filter_by(user_id=session["user_id"], product_id=product_id).first()
        if row:
            db.session.delete(row)
            state = False
        else:
            db.session.add(WishlistItem(user_id=session["user_id"], product_id=product_id))
            state = True
        db.session.commit()
        return jsonify({"ok": True, "saved": state})

    @app_obj.post("/api/marketplace/price-alert")
    @_login_required_json
    def marketplace_price_alert():
        data = request.get_json(silent=True) or {}
        product_id = _json_int(data.get("product_id"), 1)
        target = data.get("target_price")
        if not product_id:
            return jsonify({"ok": False, "error": "invalid_product"}), 400
        target = _json_int(target, 0) if target not in (None, "") else None
        row = PriceAlert.query.filter_by(user_id=session["user_id"], product_id=product_id, active=True).first()
        if row:
            row.target_price = target
        else:
            db.session.add(PriceAlert(user_id=session["user_id"], product_id=product_id, target_price=target))
        db.session.commit()
        return jsonify({"ok": True, "target_price": target})

    @app_obj.get("/api/marketplace/notifications")
    @_login_required_json
    def marketplace_notifications():
        rows = (CustomerNotification.query.filter_by(user_id=session["user_id"])
                .order_by(CustomerNotification.id.desc()).limit(50).all())
        return jsonify({"ok": True, "unread": sum(1 for r in rows if not r.read_at), "items": [
            {"id": r.id, "title": r.title, "body": r.body, "kind": r.kind, "link": r.link,
             "read": bool(r.read_at), "created_at": r.created_at.isoformat()}
            for r in rows
        ]})

    @app_obj.post("/api/marketplace/notifications/<int:notification_id>/read")
    @_login_required_json
    def marketplace_notification_read(notification_id):
        row = CustomerNotification.query.filter_by(id=notification_id, user_id=session["user_id"]).first()
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        row.read_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True})

    @app_obj.post("/api/marketplace/support")
    @_login_required_json
    def marketplace_support_ticket():
        data = request.get_json(silent=True) or {}
        subject = str(data.get("subject") or "").strip()[:180]
        body = str(data.get("body") or "").strip()
        if len(subject) < 3 or not body:
            return jsonify({"ok": False, "error": "subject_and_body_required"}), 400
        ticket = SupportTicket(user_id=session["user_id"], order_id=_json_int(data.get("order_id"), 1), subject=subject)
        db.session.add(ticket)
        db.session.flush()
        db.session.add(SupportMessage(ticket_id=ticket.id, user_id=session["user_id"], body=body))
        db.session.commit()
        return jsonify({"ok": True, "ticket_id": ticket.id})

    @app_obj.post("/api/marketplace/returns")
    @_login_required_json
    def marketplace_return_request():
        data = request.get_json(silent=True) or {}
        order_id = _json_int(data.get("order_id"), 1)
        reason = str(data.get("reason") or "").strip()[:300]
        details = str(data.get("details") or "").strip()
        if not order_id or not reason:
            return jsonify({"ok": False, "error": "order_and_reason_required"}), 400
        existing = ReturnRequest.query.filter_by(order_id=order_id, user_id=session["user_id"], status="requested").first()
        if existing:
            return jsonify({"ok": False, "error": "return_already_requested", "id": existing.id}), 409
        row = ReturnRequest(order_id=order_id, user_id=session["user_id"], reason=reason, details=details)
        db.session.add(row)
        db.session.commit()
        return jsonify({"ok": True, "id": row.id, "status": row.status})

    @app_obj.get("/api/marketplace/customer-summary")
    @_login_required_json
    def marketplace_customer_summary():
        wallet = CustomerWallet.query.filter_by(user_id=session["user_id"]).first()
        wishlist_count = WishlistItem.query.filter_by(user_id=session["user_id"]).count()
        unread = CustomerNotification.query.filter_by(user_id=session["user_id"], read_at=None).count()
        tickets = SupportTicket.query.filter_by(user_id=session["user_id"], status="open").count()
        return jsonify({"ok": True, "wallet": {"balance": wallet.balance if wallet else 0,
                                                    "points": wallet.points if wallet else 0,
                                                    "tier": wallet.tier if wallet else "standard"},
                        "wishlist_count": wishlist_count, "unread_notifications": unread,
                        "open_tickets": tickets})

    app_obj.extensions["kharidino_marketplace_ultimate"] = True
