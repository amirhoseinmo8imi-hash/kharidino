"""Optional commerce extensions inspired by mature shop architectures.

This module keeps the existing Kharidino models intact and adds isolated,
DB-backed account/order primitives: address book, order status history,
coupons, payment-gateway abstraction, and notifications.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from flask import jsonify, flash, redirect, render_template, request, session, url_for
from sqlalchemy import event, inspect, and_

from app import app, db, User, Order, OrderItem, Product, admin_required, login_required


class Address(db.Model):
    __tablename__ = "kharidino_address"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(80), nullable=False, default="آدرس من")
    recipient_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    province = db.Column(db.String(100), nullable=False, default="")
    city = db.Column(db.String(100), nullable=False, default="")
    postal_code = db.Column(db.String(20), nullable=False, default="")
    address = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("saved_addresses", lazy=True, cascade="all, delete-orphan"))


class OrderStatusHistory(db.Model):
    __tablename__ = "kharidino_order_status_history"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    old_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    note = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    order = db.relationship("Order", backref=db.backref("status_history", lazy=True, cascade="all, delete-orphan"))
    actor = db.relationship("User")


class Coupon(db.Model):
    __tablename__ = "kharidino_coupon"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False, default="percent")  # percent | fixed
    value = db.Column(db.Integer, nullable=False, default=0)
    min_total = db.Column(db.Integer, nullable=False, default=0)
    max_uses = db.Column(db.Integer, nullable=True)
    used_count = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CouponRedemption(db.Model):
    __tablename__ = "kharidino_coupon_redemption"
    id = db.Column(db.Integer, primary_key=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey("kharidino_coupon.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, unique=True)
    discount = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    coupon = db.relationship("Coupon", backref=db.backref("redemptions", lazy=True))


class PaymentTransaction(db.Model):
    __tablename__ = "kharidino_payment_transaction"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    gateway = db.Column(db.String(40), nullable=False, default="manual")
    status = db.Column(db.String(30), nullable=False, default="pending")
    amount = db.Column(db.Integer, nullable=False, default=0)
    authority = db.Column(db.String(120), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = db.relationship("Order", backref=db.backref("payments", lazy=True, cascade="all, delete-orphan"))


class Notification(db.Model):
    __tablename__ = "kharidino_notification"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    kind = db.Column(db.String(40), nullable=False, default="system")
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("notifications", lazy=True, cascade="all, delete-orphan"))


# ---------- account/address helpers ----------
def _current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None


def _set_default_address(user_id, address_id):
    Address.query.filter_by(user_id=user_id).update({Address.is_default: False})
    row = db.session.get(Address, address_id)
    if row and row.user_id == user_id:
        row.is_default = True


@app.route("/account/addresses", methods=["GET", "POST"])
@login_required
def account_addresses():
    user = _current_user()
    if request.method == "POST":
        title = (request.form.get("title") or "آدرس من").strip()[:80]
        recipient_name = (request.form.get("recipient_name") or "").strip()[:120]
        phone = (request.form.get("phone") or "").strip()[:30]
        province = (request.form.get("province") or "").strip()[:100]
        city = (request.form.get("city") or "").strip()[:100]
        postal_code = (request.form.get("postal_code") or "").strip()[:20]
        address_text = (request.form.get("address") or "").strip()
        if not recipient_name or not phone or not city or not address_text:
            flash("نام گیرنده، تلفن، شهر و آدرس الزامی است.", "danger")
            return redirect(url_for("account_addresses"))
        row = Address(user_id=user.id, title=title, recipient_name=recipient_name,
                      phone=phone, province=province, city=city, postal_code=postal_code,
                      address=address_text, is_default=not Address.query.filter_by(user_id=user.id).first())
        db.session.add(row)
        db.session.commit()
        flash("آدرس با موفقیت ذخیره شد.", "success")
        return redirect(url_for("account_addresses"))
    return render_template("account_addresses.html", addresses=Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc(), Address.id.desc()).all())


@app.post("/account/addresses/<int:address_id>/default")
@login_required
def set_default_address(address_id):
    user = _current_user()
    row = db.session.get(Address, address_id)
    if not row or row.user_id != user.id:
        return ("Not Found", 404)
    _set_default_address(user.id, address_id)
    db.session.commit()
    flash("آدرس پیش‌فرض تغییر کرد.", "success")
    return redirect(url_for("account_addresses"))


@app.post("/account/addresses/<int:address_id>/delete")
@login_required
def delete_address(address_id):
    user = _current_user()
    row = db.session.get(Address, address_id)
    if not row or row.user_id != user.id:
        return ("Not Found", 404)
    was_default = row.is_default
    db.session.delete(row)
    db.session.flush()
    if was_default:
        replacement = Address.query.filter_by(user_id=user.id).order_by(Address.id.desc()).first()
        if replacement:
            replacement.is_default = True
    db.session.commit()
    flash("آدرس حذف شد.", "success")
    return redirect(url_for("account_addresses"))


# ---------- order detail / IDOR protection ----------
def _owned_order(order_id):
    user = _current_user()
    if not user:
        return None
    order = db.session.get(Order, order_id)
    if not order:
        return None
    if user.role != "admin" and order.user_id != user.id:
        return None
    return order


@app.get("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    order = _owned_order(order_id)
    if not order:
        return ("Not Found", 404)
    return render_template("order_detail.html", order=order)


@app.get("/api/orders/<int:order_id>")
@login_required
def order_detail_api(order_id):
    order = _owned_order(order_id)
    if not order:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "id": order.id,
        "status": order.status,
        "total": order.total,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "customer": {"name": order.customer_name, "phone": order.phone, "address": order.address},
        "items": [{"product_id": i.product_id, "name": i.product_name, "price": i.price, "quantity": i.quantity} for i in order.items],
        "history": [{"old_status": h.old_status, "new_status": h.new_status, "note": h.note, "created_at": h.created_at.isoformat()} for h in order.status_history],
    })


# ---------- coupons ----------
def _coupon_discount(coupon, total):
    if not coupon or not coupon.active or total < coupon.min_total:
        return 0
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        return 0
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return 0
    if coupon.kind == "fixed":
        return max(0, min(int(coupon.value), int(total)))
    return max(0, min(int(total), int(Decimal(total) * Decimal(coupon.value) / Decimal(100))))


@app.post("/coupon/apply")
@login_required
def apply_coupon():
    code = (request.form.get("code") or "").strip().upper()[:64]
    coupon = Coupon.query.filter(db.func.upper(Coupon.code) == code).first()
    if not coupon:
        session.pop("coupon_code", None)
        return jsonify({"ok": False, "error": "کد تخفیف معتبر نیست."}), 400
    # Use the current cart total if available, without trusting client prices.
    try:
        from app import cart_data
        _, total = cart_data()
    except Exception:
        total = 0
    discount = _coupon_discount(coupon, total)
    if discount <= 0:
        return jsonify({"ok": False, "error": "این کد برای سبد فعلی قابل استفاده نیست."}), 400
    session["coupon_code"] = coupon.code
    return jsonify({"ok": True, "code": coupon.code, "discount": discount, "total_after_discount": total - discount})


@app.post("/coupon/remove")
@login_required
def remove_coupon():
    session.pop("coupon_code", None)
    return jsonify({"ok": True})


# ---------- payment abstraction ----------
class PaymentGateway:
    name = "base"
    def start(self, transaction):
        raise NotImplementedError
    def verify(self, transaction, payload):
        raise NotImplementedError


class ManualPaymentGateway(PaymentGateway):
    name = "manual"
    def start(self, transaction):
        transaction.authority = f"MANUAL-{transaction.id}-{int(datetime.utcnow().timestamp())}"
        transaction.status = "pending"
        return transaction.authority
    def verify(self, transaction, payload):
        transaction.status = "paid" if payload.get("confirm") == "1" else "failed"
        return transaction.status == "paid"


PAYMENT_GATEWAYS = {ManualPaymentGateway.name: ManualPaymentGateway()}


def payment_gateway(name):
    return PAYMENT_GATEWAYS.get(name)


@app.post("/orders/<int:order_id>/payment/start")
@login_required
def payment_start(order_id):
    order = _owned_order(order_id)
    if not order:
        return ("Not Found", 404)
    existing = PaymentTransaction.query.filter_by(order_id=order.id, status="paid").first()
    if existing:
        return jsonify({"ok": True, "status": "paid", "transaction_id": existing.id})
    tx = PaymentTransaction(order_id=order.id, gateway="manual", amount=order.total)
    db.session.add(tx)
    db.session.flush()
    gateway = payment_gateway(tx.gateway)
    authority = gateway.start(tx)
    db.session.commit()
    return jsonify({"ok": True, "transaction_id": tx.id, "authority": authority, "gateway": tx.gateway})


@app.post("/orders/<int:order_id>/payment/verify")
@login_required
def payment_verify(order_id):
    order = _owned_order(order_id)
    if not order:
        return ("Not Found", 404)
    tx = PaymentTransaction.query.filter_by(order_id=order.id).order_by(PaymentTransaction.id.desc()).first()
    if not tx:
        return jsonify({"ok": False, "error": "تراکنش یافت نشد."}), 404
    gateway = payment_gateway(tx.gateway)
    if gateway.verify(tx, request.form):
        db.session.commit()
        return jsonify({"ok": True, "status": tx.status})
    db.session.commit()
    return jsonify({"ok": False, "status": tx.status}), 400


# ---------- notifications ----------
@app.get("/account/notifications")
@login_required
def notifications():
    user = _current_user()
    rows = Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(100).all()
    return render_template("notifications.html", notifications=rows)


@app.post("/account/notifications/<int:notification_id>/read")
@login_required
def notification_read(notification_id):
    user = _current_user()
    row = db.session.get(Notification, notification_id)
    if not row or row.user_id != user.id:
        return ("Not Found", 404)
    row.is_read = True
    db.session.commit()
    return redirect(url_for("notifications"))


# ---------- admin coupon management ----------
@app.route("/admin/coupons", methods=["GET", "POST"])
@admin_required
def admin_coupons():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper()[:64]
        kind = request.form.get("kind") if request.form.get("kind") in {"percent", "fixed"} else "percent"
        try:
            value = int(request.form.get("value", "0"))
            min_total = max(0, int(request.form.get("min_total", "0")))
            max_uses_raw = (request.form.get("max_uses") or "").strip()
            max_uses = int(max_uses_raw) if max_uses_raw else None
        except ValueError:
            flash("مقادیر عددی نامعتبر است.", "danger")
            return redirect(url_for("admin_coupons"))
        if not code or value <= 0 or (kind == "percent" and value > 100) or (max_uses is not None and max_uses <= 0):
            flash("اطلاعات کد تخفیف نامعتبر است.", "danger")
            return redirect(url_for("admin_coupons"))
        if Coupon.query.filter_by(code=code).first():
            flash("این کد قبلاً ثبت شده است.", "danger")
            return redirect(url_for("admin_coupons"))
        db.session.add(Coupon(code=code, kind=kind, value=value, min_total=min_total, max_uses=max_uses))
        db.session.commit()
        flash("کد تخفیف ایجاد شد.", "success")
        return redirect(url_for("admin_coupons"))
    return render_template("admin_coupons.html", coupons=Coupon.query.order_by(Coupon.id.desc()).all())


@app.post("/admin/coupons/<int:coupon_id>/toggle")
@admin_required
def toggle_coupon(coupon_id):
    coupon = db.session.get(Coupon, coupon_id)
    if not coupon:
        return ("Not Found", 404)
    coupon.active = not coupon.active
    db.session.commit()
    return redirect(url_for("admin_coupons"))


# ---------- automatic order audit/history + coupon redemption ----------
@event.listens_for(db.session.registry(), "after_flush")
def _unused_scoped_listener(*args, **kwargs):
    # Kept intentionally empty; SQLAlchemy's scoped-session registry is not
    # the right event target for portable applications.
    return None


@event.listens_for(db.session.session_factory, "after_flush")
def _after_flush(session_obj, flush_context):
    actor_id = session.get("user_id")
    for obj in list(session_obj.new) + list(session_obj.dirty):
        if isinstance(obj, Order):
            state = inspect(obj)
            history = state.attrs.status.history
            if obj in session_obj.new:
                old_status = None
                new_status = obj.status
            elif history.has_changes():
                old_status = history.deleted[0] if history.deleted else None
                new_status = history.added[0] if history.added else obj.status
            else:
                continue
            session_obj.add(OrderStatusHistory(order=obj, old_status=old_status, new_status=new_status, actor_user_id=actor_id or None))

            if obj in session_obj.new:
                code = (session.get("coupon_code") or "").strip().upper()
                if code:
                    coupon = Coupon.query.filter(db.func.upper(Coupon.code) == code).with_for_update().first()
                    discount = _coupon_discount(coupon, obj.total) if coupon else 0
                    if discount > 0:
                        obj.total = max(0, obj.total - discount)
                        coupon.used_count += 1
                        session_obj.add(CouponRedemption(coupon=coupon, user_id=obj.user_id, order=obj, discount=discount))
                    session.pop("coupon_code", None)


# Database creation is performed after this module is registered from wsgi.py.
def apply_commerce_extensions(flask_app):
    flask_app.jinja_env.globals["unread_notification_count"] = lambda: (
        Notification.query.filter_by(user_id=session.get("user_id"), is_read=False).count()
        if session.get("user_id") else 0
    )
