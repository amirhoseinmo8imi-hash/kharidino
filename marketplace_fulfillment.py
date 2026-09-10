"""Seller shipment lifecycle and customer return operations."""
from datetime import datetime
from functools import wraps

from flask import abort, jsonify, request, session

from app import app, db, Order
from marketplace_ultimate import Shipment, ReturnRequest


SHIPMENT_FLOW = {
    "pending": {"packed", "cancelled"}, "packed": {"shipped", "cancelled"},
    "shipped": {"in_transit", "delivered", "returned"},
    "in_transit": {"delivered", "returned"}, "delivered": {"returned"},
    "returned": set(), "cancelled": set(),
}

RETURN_FLOW = {
    "requested": {"approved", "rejected"}, "approved": {"received", "rejected"},
    "received": {"refunded", "rejected"}, "refunded": set(), "rejected": set(),
}


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            abort(401)
        return view(*args, **kwargs)
    return wrapped


def _owned_order(order_id):
    return db.session.query(Order).filter_by(id=order_id, user_id=session["user_id"]).first()


def _admin():
    user = db.session.get(__import__("app").User, session.get("user_id"))
    if not user or user.role != "admin":
        abort(403)
    return user


def apply_marketplace_fulfillment(app_obj=None):
    app_obj = app_obj or app
    if app_obj.extensions.get("kharidino_marketplace_fulfillment"):
        return

    @app_obj.get("/api/marketplace/orders/<int:order_id>/shipments")
    @_login_required
    def order_shipments(order_id):
        order = _owned_order(order_id)
        if not order:
            abort(404)
        rows = Shipment.query.filter_by(order_id=order_id).order_by(Shipment.id.desc()).all()
        return jsonify({"ok": True, "items": [
            {"id": x.id, "seller_order_id": x.seller_order_id, "carrier": x.carrier,
             "tracking_code": x.tracking_code, "service": x.service, "status": x.status,
             "shipped_at": x.shipped_at.isoformat() if x.shipped_at else None,
             "delivered_at": x.delivered_at.isoformat() if x.delivered_at else None}
            for x in rows
        ]})

    @app_obj.post("/api/marketplace/returns/<int:return_id>/cancel")
    @_login_required
    def cancel_return(return_id):
        row = ReturnRequest.query.filter_by(id=return_id, user_id=session["user_id"]).first()
        if not row or row.status != "requested":
            abort(409)
        row.status = "rejected"
        row.resolved_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "status": row.status})

    @app_obj.get("/api/marketplace/returns")
    @_login_required
    def customer_returns():
        rows = ReturnRequest.query.filter_by(user_id=session["user_id"]).order_by(ReturnRequest.id.desc()).all()
        return jsonify({"ok": True, "items": [
            {"id": x.id, "order_id": x.order_id, "reason": x.reason, "details": x.details,
             "status": x.status, "refund_amount": x.refund_amount,
             "created_at": x.created_at.isoformat(),
             "resolved_at": x.resolved_at.isoformat() if x.resolved_at else None}
            for x in rows
        ]})

    @app_obj.get("/api/marketplace/admin/returns")
    def admin_returns():
        _admin()
        rows = ReturnRequest.query.order_by(ReturnRequest.id.desc()).limit(200).all()
        return jsonify({"ok": True, "items": [
            {"id": x.id, "order_id": x.order_id, "user_id": x.user_id, "reason": x.reason,
             "status": x.status, "refund_amount": x.refund_amount}
            for x in rows
        ]})

    @app_obj.post("/api/marketplace/admin/returns/<int:return_id>/status")
    def admin_return_status(return_id):
        _admin()
        row = db.session.get(ReturnRequest, return_id)
        if not row:
            abort(404)
        status = str((request.get_json(silent=True) or {}).get("status") or "").strip()
        if status not in RETURN_FLOW or status == row.status or status not in RETURN_FLOW.get(row.status, set()):
            abort(409, description="تغییر وضعیت مرجوعی مجاز نیست.")
        order = db.session.get(Order, row.order_id)
        if not order or order.user_id != row.user_id:
            abort(409, description="سفارش مرجوعی نامعتبر است.")
        if status in {"approved", "received"} and row.refund_amount <= 0:
            row.refund_amount = int(order.total or 0)
        if status == "refunded":
            if row.refund_amount <= 0:
                abort(409, description="مبلغ استرداد نامعتبر است.")
            executor = app_obj.extensions.get("kharidino_execute_return_refund")
            if executor is None:
                abort(503, description="موتور استرداد فعال نیست.")
            ok, error = executor(row)
            if not ok:
                abort(409, description=error)
            row.status = "refunded"
            row.resolved_at = datetime.utcnow()
            db.session.commit()
            return jsonify({"ok": True, "status": row.status, "refund_amount": row.refund_amount})
        row.status = status
        db.session.commit()
        return jsonify({"ok": True, "status": row.status, "refund_amount": row.refund_amount})

    app_obj.extensions["kharidino_marketplace_fulfillment"] = True
