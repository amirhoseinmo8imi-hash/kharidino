"""Seller-facing shipment controls with strict store ownership."""
from datetime import datetime

from flask import abort, jsonify, request, session

from app import app, db
from merchant_marketplace import seller_required, _seller_account
from merchant_marketplace_v2 import SellerOrder
from marketplace_ultimate import Shipment


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
    seller_order_id = int(data.get("seller_order_id") or 0)
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
    shipment = Shipment(
        order_id=seller_order.order_id,
        seller_order_id=seller_order.id,
        carrier=carrier,
        tracking_code=tracking,
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
    allowed = {"packed", "shipped", "in_transit", "delivered", "returned", "cancelled"}
    if status not in allowed:
        abort(400)
    shipment.status = status
    now = datetime.utcnow()
    if status == "shipped":
        shipment.shipped_at = shipment.shipped_at or now
    if status == "delivered":
        shipment.delivered_at = shipment.delivered_at or now
        shipment.shipped_at = shipment.shipped_at or now
    db.session.commit()
    return jsonify({"ok": True, "status": shipment.status})
