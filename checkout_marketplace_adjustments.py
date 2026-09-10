"""Atomic marketplace adjustments around the existing checkout flow."""
from functools import wraps

from flask import abort, request, session
from sqlalchemy import update

from app import app, db, Order, Product
from marketplace_ultimate import Coupon, CouponRedemption, CustomerWallet
from marketplace_hardening import _normalize_coupon


def _cart_total():
    cart = session.get("cart", {})
    if not isinstance(cart, dict):
        return 0
    total = 0
    for raw_id, raw_qty in cart.items():
        try:
            product_id, quantity = int(raw_id), int(raw_qty)
        except (TypeError, ValueError):
            continue
        if product_id <= 0 or quantity <= 0:
            continue
        product = db.session.get(Product, product_id)
        if product:
            total += max(0, int(product.price or 0)) * quantity
    return total


def _preview_coupon(code, total, user_id):
    code = _normalize_coupon(code)
    if not code:
        return None
    coupon = Coupon.query.filter_by(code=code, active=True).first()
    if not coupon:
        abort(400, description="کد تخفیف معتبر نیست.")
    from datetime import datetime
    now = datetime.utcnow()
    if coupon.starts_at and now < coupon.starts_at:
        abort(400, description="زمان استفاده از این کد تخفیف هنوز نرسیده است.")
    if coupon.expires_at and now >= coupon.expires_at:
        abort(400, description="کد تخفیف منقضی شده است.")
    if total < int(coupon.min_order or 0):
        abort(400, description="حداقل مبلغ سفارش برای این کد تخفیف رعایت نشده است.")
    if coupon.usage_limit is not None and int(coupon.used_count or 0) >= int(coupon.usage_limit):
        abort(409, description="ظرفیت مصرف این کد تخفیف تکمیل شده است.")
    if coupon.kind == "fixed":
        discount = min(total, max(0, int(coupon.value or 0)))
    else:
        discount = total * max(0, min(100, int(coupon.value or 0))) // 100
    if coupon.max_discount is not None:
        discount = min(discount, max(0, int(coupon.max_discount)))
    return coupon, discount


def _apply_adjustments(order, coupon_code, wallet_amount, use_wallet=False):
    original_total = max(0, int(order.total or 0))
    coupon = None
    discount = 0
    if coupon_code:
        coupon, discount = _preview_coupon(coupon_code, original_total, order.user_id)
        existing = CouponRedemption.query.filter_by(order_id=order.id).first()
        if existing:
            if existing.coupon_id != coupon.id:
                raise ValueError("order_coupon_already_set")
            discount = int(existing.discount or 0)
        else:
            filters = [Coupon.id == coupon.id, Coupon.active.is_(True)]
            if coupon.usage_limit is not None:
                filters.append(Coupon.used_count < coupon.usage_limit)
            changed = db.session.query(Coupon).filter(*filters).update(
                {Coupon.used_count: Coupon.used_count + 1}, synchronize_session=False
            )
            if changed != 1:
                raise ValueError("coupon_usage_exhausted")
            db.session.add(CouponRedemption(
                coupon_id=coupon.id, user_id=order.user_id, order_id=order.id, discount=discount
            ))

    subtotal_after_coupon = max(0, original_total - discount)
    wallet_used = 0
    wallet = CustomerWallet.query.filter_by(user_id=order.user_id).first()
    if use_wallet and wallet is None:
        raise ValueError("wallet_not_found")
    if use_wallet and wallet_amount <= 0:
        wallet_amount = int(wallet.balance or 0)
    if wallet_amount:
        requested = min(max(0, int(wallet_amount)), subtotal_after_coupon)
        if requested > 0:
            changed = db.session.execute(
                update(CustomerWallet)
                .where(CustomerWallet.id == wallet.id)
                .where(CustomerWallet.balance >= requested)
                .values(balance=CustomerWallet.balance - requested)
            )
            if changed.rowcount != 1:
                raise ValueError("insufficient_wallet_balance")
            wallet_used = requested
            from marketplace_ultimate import WalletTransaction
            reference = f"CHECKOUT:{order.id}:WALLET"
            existing_tx = WalletTransaction.query.filter_by(reference=reference).first()
            if not existing_tx:
                db.session.add(WalletTransaction(
                    wallet_id=wallet.id, amount=-wallet_used, kind="checkout",
                    reference=reference, note=f"پرداخت سفارش #{order.id}",
                ))
            else:
                # The debit reference already exists; restore the just-reserved amount
                # and use the existing transaction to make retries idempotent.
                db.session.execute(
                    update(CustomerWallet).where(CustomerWallet.id == wallet.id)
                    .values(balance=CustomerWallet.balance + requested)
                )
                wallet_used = abs(int(existing_tx.amount or 0))

    order.total = max(0, subtotal_after_coupon - wallet_used)
    return {"discount": discount, "wallet_used": wallet_used, "total": order.total}


def apply_checkout_marketplace_adjustments(app_obj=None):
    app_obj = app_obj or app
    if app_obj.extensions.get("kharidino_checkout_marketplace_adjustments"):
        return
    checkout_view = app_obj.view_functions.get("checkout")
    if checkout_view and not getattr(checkout_view, "_kharidino_marketplace_adjustments", False):
        @wraps(checkout_view)
        def checkout_with_marketplace_adjustments(*args, **kwargs):
            if request.method != "POST" or not session.get("user_id"):
                return checkout_view(*args, **kwargs)
            coupon_code = _normalize_coupon(request.form.get("coupon_code") or request.form.get("coupon"))
            raw_wallet = request.form.get("wallet_amount")
            use_wallet = str(request.form.get("use_wallet", "")).lower() in {"1", "true", "yes", "on"}
            if raw_wallet not in (None, ""):
                try:
                    wallet_amount = max(0, int(raw_wallet))
                except (TypeError, ValueError):
                    abort(400, description="مبلغ استفاده از کیف پول نامعتبر است.")
            else:
                wallet_amount = 0
            if coupon_code:
                _preview_coupon(coupon_code, _cart_total(), session["user_id"])
            if wallet_amount:
                wallet = CustomerWallet.query.filter_by(user_id=session["user_id"]).first()
                if not wallet or int(wallet.balance or 0) < wallet_amount:
                    abort(409, description="موجودی کیف پول برای این پرداخت کافی نیست.")
            if use_wallet and not CustomerWallet.query.filter_by(user_id=session["user_id"]).first():
                abort(409, description="کیف پول کاربر فعال نیست.")

            before_ids = {o.id for o in Order.query.filter_by(user_id=session["user_id"]).all()}
            response = checkout_view(*args, **kwargs)
            after = Order.query.filter_by(user_id=session["user_id"]).order_by(Order.id.desc()).all()
            new_orders = [o for o in after if o.id not in before_ids]
            if len(new_orders) != 1 or (not coupon_code and not wallet_amount and not use_wallet):
                return response
            order = new_orders[0]
            try:
                result = _apply_adjustments(order, coupon_code, wallet_amount, use_wallet)
                if result["total"] <= 0:
                    # Keep zero-value orders out of the external gateway path.
                    # The payment layer will be extended to finalize these safely.
                    raise ValueError("zero_total_requires_free_checkout")
                db.session.commit()
            except Exception:
                db.session.rollback()
                order = db.session.get(Order, new_orders[0].id)
                if order:
                    order.status = "لغو شد"
                    db.session.commit()
                abort(409, description="اعمال تخفیف یا کیف پول روی سفارش انجام نشد؛ سفارش لغو شد.")
            session["checkout_marketplace_adjustment"] = {"order_id": order.id, **result}
            session.modified = True
            return response
        checkout_with_marketplace_adjustments._kharidino_marketplace_adjustments = True
        app_obj.view_functions["checkout"] = checkout_with_marketplace_adjustments

    @app_obj.get("/api/marketplace/checkout-adjustment")
    def marketplace_checkout_adjustment():
        data = session.get("checkout_marketplace_adjustment") or {}
        return {"ok": True, **data}
    app_obj.extensions["kharidino_checkout_marketplace_adjustments"] = True
