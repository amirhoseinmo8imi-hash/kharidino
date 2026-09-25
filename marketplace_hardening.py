"""Security and transactional services for Kharidino Marketplace Ultimate.

This layer is additive: it hardens existing Marketplace Ultimate routes and adds
small, reusable services for wallet, coupons, price history and product comparison.
It intentionally avoids altering existing commerce/payment tables.
"""
from datetime import datetime
from functools import wraps

from flask import jsonify, request, session
from sqlalchemy import and_, update
from sqlalchemy.exc import IntegrityError

from app import app, db, Order, Product


class ProductPriceHistory(db.Model):
    __tablename__ = "kharidino_product_price_history"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=True, index=True)
    price = db.Column(db.Integer, nullable=False)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class ProductComparison(db.Model):
    __tablename__ = "kharidino_product_comparison"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_comparison_user_product"),
    )


def _json_int(value, minimum=0):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= minimum else None


def _json_login(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"ok": False, "error": "authentication_required"}), 401
        return view(*args, **kwargs)

    return wrapped


def _current_user_id():
    value = session.get("user_id")
    return _json_int(value, 1)


def _product_payload(product):
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "image": product.image or "",
    }


def _order_owned_by_current_user(order_id):
    user_id = _current_user_id()
    if not user_id or not order_id:
        return None
    return db.session.query(Order).filter_by(id=order_id, user_id=user_id).first()


def _harden_existing_marketplace_routes():
    """Reject forged product/order identifiers before legacy handlers run."""
    guarded_paths = {
        "/api/marketplace/wishlist/toggle",
        "/api/marketplace/price-alert",
        "/api/marketplace/support",
        "/api/marketplace/returns",
    }

    @app.before_request
    def _marketplace_ownership_guard():
        if request.path not in guarded_paths or request.method != "POST":
            return None

        user_id = _current_user_id()
        if not user_id:
            return None

        data = request.get_json(silent=True) or {}

        if request.path in {
            "/api/marketplace/wishlist/toggle",
            "/api/marketplace/price-alert",
        }:
            product_id = _json_int(data.get("product_id"), 1)
            if not product_id or not db.session.get(Product, product_id):
                return jsonify({"ok": False, "error": "product_not_found"}), 404
            return None

        order_id = _json_int(data.get("order_id"), 1)
        if order_id is None:
            if request.path == "/api/marketplace/support":
                return None
            return jsonify({"ok": False, "error": "order_not_found"}), 404

        if not _order_owned_by_current_user(order_id):
            return jsonify({"ok": False, "error": "order_not_found"}), 404
        return None


def get_or_create_wallet(user_id):
    from marketplace_ultimate import CustomerWallet

    wallet = CustomerWallet.query.filter_by(user_id=user_id).first()
    if wallet:
        return wallet

    wallet = CustomerWallet(user_id=user_id, balance=0, points=0, tier="standard")
    db.session.add(wallet)
    try:
        db.session.flush()
        return wallet
    except IntegrityError:
        db.session.rollback()
        return CustomerWallet.query.filter_by(user_id=user_id).first()


def _tier_for_points(points):
    if points >= 5000:
        return "platinum"
    if points >= 2000:
        return "gold"
    if points >= 500:
        return "silver"
    return "standard"


def apply_wallet_transaction(user_id, amount, kind, reference, note="", points_delta=0):
    """Atomically apply one wallet movement; duplicate references are idempotent."""
    from marketplace_ultimate import CustomerWallet, WalletTransaction

    user_id = _json_int(user_id, 1)
    if not user_id:
        raise ValueError("invalid user")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise ValueError("invalid amount")
    if amount == 0:
        raise ValueError("amount must not be zero")
    reference = str(reference or "").strip()
    if not reference or len(reference) > 120:
        raise ValueError("invalid reference")
    kind = str(kind or "adjustment").strip()[:30] or "adjustment"

    existing = WalletTransaction.query.filter_by(reference=reference).first()
    if existing:
        if existing.amount != amount or existing.kind != kind:
            raise ValueError("reference_conflict")
        return existing

    wallet = get_or_create_wallet(user_id)
    if wallet is None:
        raise RuntimeError("wallet_creation_failed")

    if amount < 0:
        result = db.session.execute(
            update(CustomerWallet)
            .where(CustomerWallet.id == wallet.id)
            .where(CustomerWallet.balance + amount >= 0)
            .values(balance=CustomerWallet.balance + amount)
        )
        if result.rowcount != 1:
            db.session.rollback()
            raise ValueError("insufficient_balance")
    else:
        db.session.execute(
            update(CustomerWallet)
            .where(CustomerWallet.id == wallet.id)
            .values(balance=CustomerWallet.balance + amount)
        )

    points = max(0, wallet.points + int(points_delta or 0))
    db.session.execute(
        update(CustomerWallet)
        .where(CustomerWallet.id == wallet.id)
        .values(points=points, tier=_tier_for_points(points), updated_at=datetime.utcnow())
    )
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        kind=kind,
        reference=reference,
        note=str(note or "")[:300],
    )
    db.session.add(transaction)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = WalletTransaction.query.filter_by(reference=reference).first()
        if existing and existing.amount == amount and existing.kind == kind:
            return existing
        raise
    return transaction


def _normalize_coupon(code):
    return " ".join(str(code or "").strip().upper().split())[:80]


def validate_coupon(code, order_total, user_id, order_id=None):
    from marketplace_ultimate import Coupon, CouponRedemption

    code = _normalize_coupon(code)
    total = _json_int(order_total, 0)
    user_id = _json_int(user_id, 1)
    if not code or total is None or not user_id:
        return None, "invalid_coupon_request"

    coupon = Coupon.query.filter_by(code=code, active=True).first()
    if not coupon:
        return None, "coupon_not_found"
    now = datetime.utcnow()
    if coupon.starts_at and now < coupon.starts_at:
        return None, "coupon_not_started"
    if coupon.expires_at and now >= coupon.expires_at:
        return None, "coupon_expired"
    if total < coupon.min_order:
        return None, "minimum_order_not_met"
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return None, "coupon_usage_exhausted"
    if order_id:
        existing = CouponRedemption.query.filter_by(order_id=order_id).first()
        if existing:
            if existing.coupon_id == coupon.id and existing.user_id == user_id:
                return coupon, "already_redeemed"
            return None, "order_coupon_already_set"

    if coupon.kind == "fixed":
        discount = min(total, max(0, coupon.value))
    else:
        discount = (total * max(0, min(100, coupon.value))) // 100
    if coupon.max_discount is not None:
        discount = min(discount, max(0, coupon.max_discount))
    return {"coupon": coupon, "discount": discount}, None


def redeem_coupon(code, order_id, user_id, order_total):
    from marketplace_ultimate import Coupon, CouponRedemption

    user_id = _json_int(user_id, 1)
    order_id = _json_int(order_id, 1)
    if not user_id or not order_id:
        raise ValueError("invalid_order")
    order = db.session.query(Order).filter_by(id=order_id, user_id=user_id).first()
    if not order:
        raise ValueError("order_not_found")

    result, error = validate_coupon(code, order_total, user_id, order_id)
    if error == "already_redeemed":
        existing = CouponRedemption.query.filter_by(order_id=order_id).first()
        return existing
    if error or not result:
        raise ValueError(error or "invalid_coupon")
    coupon = result["coupon"]
    discount = result["discount"]

    condition = [Coupon.id == coupon.id, Coupon.active.is_(True)]
    if coupon.usage_limit is not None:
        condition.append(Coupon.used_count < coupon.usage_limit)
    changed = db.session.query(Coupon).filter(and_(*condition)).update(
        {Coupon.used_count: Coupon.used_count + 1}, synchronize_session=False
    )
    if changed != 1:
        db.session.rollback()
        raise ValueError("coupon_usage_exhausted")

    redemption = CouponRedemption(
        coupon_id=coupon.id,
        user_id=user_id,
        order_id=order_id,
        discount=discount,
    )
    db.session.add(redemption)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = CouponRedemption.query.filter_by(order_id=order_id).first()
        if existing:
            return existing
        raise
    return redemption


def record_price_history(product_id, price, store_id=None):
    product_id = _json_int(product_id, 1)
    price = _json_int(price, 0)
    store_id = _json_int(store_id, 1) if store_id is not None else None
    if not product_id or price is None or not db.session.get(Product, product_id):
        raise ValueError("invalid_product_or_price")
    row = ProductPriceHistory(product_id=product_id, store_id=store_id, price=price)
    db.session.add(row)
    db.session.commit()
    return row


def apply_marketplace_hardening(app_obj=None):
    app_obj = app_obj or app
    if app_obj.extensions.get("kharidino_marketplace_hardening"):
        return

    _harden_existing_marketplace_routes()

    @app_obj.get("/api/marketplace/wallet")
    @_json_login
    def marketplace_wallet():
        from marketplace_ultimate import CustomerWallet, WalletTransaction

        wallet = CustomerWallet.query.filter_by(user_id=session["user_id"]).first()
        transactions = []
        if wallet:
            transactions = (
                WalletTransaction.query.filter_by(wallet_id=wallet.id)
                .order_by(WalletTransaction.id.desc()).limit(30).all()
            )
        return jsonify({
            "ok": True,
            "wallet": {
                "balance": wallet.balance if wallet else 0,
                "points": wallet.points if wallet else 0,
                "tier": wallet.tier if wallet else "standard",
            },
            "transactions": [
                {"amount": tx.amount, "kind": tx.kind, "reference": tx.reference,
                 "note": tx.note, "created_at": tx.created_at.isoformat()}
                for tx in transactions
            ],
        })

    @app_obj.post("/api/marketplace/coupons/validate")
    @_json_login
    def marketplace_coupon_validate():
        data = request.get_json(silent=True) or {}
        result, error = validate_coupon(
            data.get("code"), data.get("order_total"), session["user_id"], data.get("order_id")
        )
        if error and error != "already_redeemed":
            return jsonify({"ok": False, "error": error}), 400
        if error == "already_redeemed":
            return jsonify({"ok": True, "already_redeemed": True, "discount": 0})
        return jsonify({"ok": True, "discount": result["discount"], "code": result["coupon"].code})

    @app_obj.get("/api/marketplace/compare")
    @_json_login
    def marketplace_compare():
        rows = ProductComparison.query.filter_by(user_id=session["user_id"]).order_by(ProductComparison.id.desc()).all()
        products = {p.id: p for p in Product.query.filter(Product.id.in_([r.product_id for r in rows])).all()} if rows else {}
        return jsonify({"ok": True, "items": [_product_payload(products[r.product_id]) for r in rows if r.product_id in products]})

    @app_obj.post("/api/marketplace/compare/toggle")
    @_json_login
    def marketplace_compare_toggle():
        data = request.get_json(silent=True) or {}
        product_id = _json_int(data.get("product_id"), 1)
        product = db.session.get(Product, product_id) if product_id else None
        if not product:
            return jsonify({"ok": False, "error": "product_not_found"}), 404
        row = ProductComparison.query.filter_by(user_id=session["user_id"], product_id=product_id).first()
        if row:
            db.session.delete(row)
            saved = False
        else:
            db.session.add(ProductComparison(user_id=session["user_id"], product_id=product_id))
            saved = True
        db.session.commit()
        return jsonify({"ok": True, "saved": saved})

    @app_obj.delete("/api/marketplace/compare/<int:product_id>")
    @_json_login
    def marketplace_compare_remove(product_id):
        row = ProductComparison.query.filter_by(user_id=session["user_id"], product_id=product_id).first()
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        db.session.delete(row)
        db.session.commit()
        return jsonify({"ok": True})

    @app_obj.get("/api/marketplace/products/<int:product_id>/price-history")
    def marketplace_price_history(product_id):
        if not db.session.get(Product, product_id):
            return jsonify({"ok": False, "error": "product_not_found"}), 404
        rows = ProductPriceHistory.query.filter_by(product_id=product_id).order_by(ProductPriceHistory.captured_at.asc()).limit(365).all()
        return jsonify({"ok": True, "items": [
            {"price": row.price, "store_id": row.store_id, "captured_at": row.captured_at.isoformat()}
            for row in rows
        ]})

    app_obj.extensions["kharidino_marketplace_hardening"] = True
