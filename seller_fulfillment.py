"""Seller-facing shipment controls with strict store ownership."""
from datetime import datetime

from flask import abort, jsonify, request

from app import app, db, Order
from merchant_marketplace import seller_required, _seller_account
from merchant_marketplace_v2 import SellerOrder, SellerLedger
from marketplace_ultimate import Shipment


FLOW = {
    "pending": {"packed", "cancelled"}, "packed": {"shipped", "cancelled"},
    "shipped": {"in_transit", "delivered", "returned"},
    "in_transit": {"delivered", "returned"}, "delivered": {"returned"},
    "returned": set(), "cancelled": set(),
}


def _refresh_delivery_state(seller_order):
    shipments = Shipment.query.filter_by(seller_order_id=seller_order.id).all()
    if not shipments:
        return
    order = db.session.get(Order, seller_order.order_id)
    if not order:
        return
    if all(x.status == "delivered" for x in shipments):
        seller_order.status = "delivered"
        if order.status in {"تأیید شد", "در حال آماده‌سازی", "ارسال شد"}:
            order.status = "تحویل شد"
        ledger = SellerLedger.query.filter_by(seller_order_id=seller_order.id).first()
        if ledger and ledger.status not in {"paid", "cancelled"}:
            ledger.status = "available"
    elif any(x.status in {"shipped", "in_transit"} for x in shipments):
        if seller_order.status in {"new", "confirmed", "preparing"}:
            seller_order.status = "shipped"


@app.get("/api/seller/shipments")
@seller_required
def seller_shipments():
    account = _seller_account()
    rows = (Shipment.query.join(SellerOrder, Shipment.seller_order_id == SellerOrder.id)
            .filter(SellerOrder.store_id == account.store_id)
            .order_by(Shipment.id.desc()).limit(200).all())
    return jsonify({"ok": True, "items": [
        {"id": x.id, "order_id": x.order_id, "seller_order_id": x.seller_order_id,
         "carrier": x.carrier, "tracking_code": x.tracking_code, "service": x.service,
         "status": x.status, "shipped_at": x.shipped_at.isoformat() if x.shipped_at else None,
         "delivered_at": x.delivered_at.isoformat() if x.delivered_at else None}
        for x in rows
    ]})


@app.post("/api/seller/shipments")
@seller_required
def seller_create_shipment():
    account = _seller_account()
    data = request.get_json(silent=True) or {}
    try:
        seller_order_id = int(data.get("seller_order_id") or 0)
    except (TypeError, ValueError):
        abort(400, description="شناسه سفارش فروشنده نامعتبر است.")
    seller_order = SellerOrder.query.filter_by(id=seller_order_id, store_id=account.store_id).first()
    if not seller_order:
        abort(404)
    tracking = str(data.get("tracking_code") or "").strip()[:120]
    carrier = str(data.get("carrier") or "").strip()[:80]
    if not carrier or not tracking:
        abort(400, description="شرکت حمل و کد رهگیری الزامی است.")
    existing = Shipment.query.filter_by(seller_order_id=seller_order.id).first()
    if existing:
        abort(409, description="برای این سفارش قبلاً مرسوله ثبت شده است.")
    if seller_order.status in {"cancelled", "delivered"}:
        abort(409, description="این سفارش دیگر قابل ارسال نیست.")
    shipment = Shipment(
        order_id=seller_order.order_id, seller_order_id=seller_order.id,
        carrier=carrier, tracking_code=tracking,
        service=str(data.get("service") or "standard").strip()[:60] or "standard",
        status="packed",
    )
    db.session.add(shipment)
    seller_order.status = "preparing"
    db.session.commit()
    return jsonify({"ok": True, "shipment_id": shipment.id, "status": shipment.status}), 201


@app.post("/api/seller/shipments/<int:shipment_id>/status")
@seller_required
def seller_update_shipment(shipment_id):
    account = _seller_account()
    shipment = (Shipment.query.join(SellerOrder, Shipment.seller_order_id == SellerOrder.id)
                .filter(Shipment.id == shipment_id, SellerOrder.store_id == account.store_id).first())
    if not shipment:
        abort(404)
    status = str((request.get_json(silent=True) or {}).get("status") or "").strip()
    if status not in FLOW or status == shipment.status or status not in FLOW.get(shipment.status, set()):
        abort(409, description="تغییر وضعیت مرسوله در این مرحله مجاز نیست.")
    shipment.status = status
    now = datetime.utcnow()
    if status == "shipped":
        shipment.shipped_at = shipment.shipped_at or now
    if status == "delivered":
        shipment.delivered_at = shipment.delivered_at or now
        shipment.shipped_at = shipment.shipped_at or now
    _refresh_delivery_state(shipment.seller_order)
    db.session.commit()
    return jsonify({"ok": True, "status": shipment.status,
                    "seller_order_status": shipment.seller_order.status,
                    "order_status": shipment.seller_order.order.status if shipment.seller_order.order else None})
