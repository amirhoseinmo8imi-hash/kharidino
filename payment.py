"""Provider-neutral payment lifecycle for Kharidino."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

PAYMENT_STATUSES = {"pending", "redirect", "verifying", "paid", "failed", "cancelled", "refunded"}


@dataclass(frozen=True)
class GatewayStartResult:
    status: str
    payment_url: str
    authority: str


@dataclass(frozen=True)
class GatewayVerifyResult:
    paid: bool
    reference: str
    message: str = ""


class PaymentGateway(ABC):
    name = "abstract"

    @abstractmethod
    def start(self, transaction_id: str, amount: int, callback_url: str) -> GatewayStartResult:
        raise NotImplementedError

    @abstractmethod
    def verify(self, transaction_id: str, amount: int, payload: dict) -> GatewayVerifyResult:
        raise NotImplementedError


class DisabledGateway(PaymentGateway):
    name = "disabled"

    def start(self, transaction_id: str, amount: int, callback_url: str) -> GatewayStartResult:
        return GatewayStartResult("failed", "", "")

    def verify(self, transaction_id: str, amount: int, payload: dict) -> GatewayVerifyResult:
        return GatewayVerifyResult(False, "", "درگاه پرداخت فعال نیست.")


class TestGateway(PaymentGateway):
    name = "test"

    def start(self, transaction_id: str, amount: int, callback_url: str) -> GatewayStartResult:
        authority = secrets.token_urlsafe(24)
        return GatewayStartResult(
            "redirect",
            f"{callback_url}?transaction={transaction_id}&authority={authority}&test=1",
            authority,
        )

    def verify(self, transaction_id: str, amount: int, payload: dict) -> GatewayVerifyResult:
        authority = str(payload.get("authority", "")).strip()
        approved = payload.get("approved") in {"1", "true", "True", 1, True}
        if not authority or not approved:
            return GatewayVerifyResult(False, "", "پرداخت توسط درگاه تأیید نشد.")
        reference = "TEST-" + hashlib.sha256(authority.encode()).hexdigest()[:20]
        return GatewayVerifyResult(True, reference)


def _gateway() -> PaymentGateway:
    if os.environ.get("PAYMENT_TEST_MODE", "0").lower() in {"1", "true", "yes"}:
        return TestGateway()
    return DisabledGateway()


def _idempotency_key(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value or len(value) > 128:
        raise ValueError("کلید idempotency نامعتبر است.")
    return value


def _valid_callback_signature(transaction_id: str, signature: str) -> bool:
    secret = os.environ.get("PAYMENT_CALLBACK_SECRET", "").strip()
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), transaction_id.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def apply_payment(app, db, Order, User):
    if getattr(app, "_kharidino_payment", False):
        return

    class PaymentTransaction(db.Model):
        __tablename__ = "payment_transaction"
        id = db.Column(db.Integer, primary_key=True)
        public_id = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
        order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
        amount = db.Column(db.Integer, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="pending", index=True)
        gateway = db.Column(db.String(50), nullable=False, default="disabled")
        authority = db.Column(db.String(200), unique=True, nullable=True)
        gateway_reference = db.Column(db.String(200), unique=True, nullable=True)
        idempotency_key = db.Column(db.String(128), unique=True, nullable=False)
        created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
        paid_at = db.Column(db.DateTime, nullable=True)
        failed_at = db.Column(db.DateTime, nullable=True)
        order = db.relationship("Order", backref=db.backref("payment_transactions", lazy=True))

    app.extensions["kharidino_payment_transaction"] = PaymentTransaction

    checkout_view = app.view_functions.get("checkout")
    if checkout_view and not getattr(checkout_view, "_kharidino_payment_wrapped", False):
        def checkout_payment_wrapper(*args, **kwargs):
            before_ids = {
                order.id
                for order in Order.query.filter_by(user_id=session.get("user_id")).all()
            }
            response = checkout_view(*args, **kwargs)
            if request.method == "POST" and session.get("user_id"):
                after_orders = Order.query.filter_by(user_id=session["user_id"]).order_by(Order.id.desc()).all()
                new_orders = [order for order in after_orders if order.id not in before_ids]
                if len(new_orders) == 1:
                    session["checkout_payment_order_id"] = new_orders[0].id
                    session.modified = True
            return response
        checkout_payment_wrapper.__name__ = getattr(checkout_view, "__name__", "checkout")
        checkout_payment_wrapper._kharidino_payment_wrapped = True
        app.view_functions["checkout"] = checkout_payment_wrapper

    @app.post("/payment/start/<int:order_id>")
    def payment_start(order_id):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        order = db.session.get(Order, order_id)
        if not order or order.user_id != session["user_id"]:
            abort(404)
        if order.status != "در انتظار بررسی" or int(order.total or 0) <= 0:
            abort(409, description="این سفارش در وضعیت قابل پرداخت نیست.")
        try:
            key = _idempotency_key(request.form.get("idempotency_key") or request.headers.get("Idempotency-Key"))
        except ValueError as exc:
            abort(400, description=str(exc))

        tx = PaymentTransaction.query.filter_by(idempotency_key=key).first()
        if tx:
            if tx.user_id != session["user_id"] or tx.order_id != order.id:
                abort(409, description="کلید idempotency قبلاً برای تراکنش دیگری استفاده شده است.")
            if tx.status == "paid":
                flash("این سفارش قبلاً پرداخت شده است.", "success")
                return redirect(url_for("my_orders"))
        else:
            tx = PaymentTransaction(order_id=order.id, user_id=session["user_id"], amount=int(order.total), gateway=_gateway().name, idempotency_key=key)
            db.session.add(tx)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                tx = PaymentTransaction.query.filter_by(idempotency_key=key).first()
                if not tx:
                    raise

        if tx.amount != int(order.total):
            abort(409, description="مبلغ تراکنش با مبلغ سفارش یکسان نیست.")
        gateway = _gateway()
        result = gateway.start(tx.public_id, tx.amount, url_for("payment_callback", transaction_id=tx.public_id, _external=True))
        if result.status != "redirect":
            tx.status = "failed"
            tx.failed_at = db.func.now()
            db.session.commit()
            abort(503, description="درگاه پرداخت در دسترس نیست.")
        tx.status = "redirect"
        tx.authority = result.authority
        db.session.commit()
        return redirect(result.payment_url)

    @app.route("/payment/callback/<string:transaction_id>", methods=["GET", "POST"])
    def payment_callback(transaction_id):
        tx = PaymentTransaction.query.filter_by(public_id=transaction_id).first_or_404()
        gateway = _gateway()
        signature = str(request.values.get("signature", "") or request.headers.get("X-Payment-Signature", "")).strip()

        if gateway.name != "test":
            if not _valid_callback_signature(tx.public_id, signature):
                abort(403, description="امضای callback نامعتبر است.")
        elif os.environ.get("PAYMENT_TEST_MODE", "0").lower() not in {"1", "true", "yes"}:
            abort(503, description="حالت آزمایشی پرداخت فعال نیست.")

        if tx.status == "paid":
            return redirect(url_for("my_orders"))
        if tx.status in {"cancelled", "refunded"}:
            abort(409, description="این تراکنش دیگر قابل تأیید نیست.")

        returned_authority = str(request.values.get("authority", "")).strip()
        if not returned_authority or not tx.authority or not hmac.compare_digest(tx.authority, returned_authority):
            abort(409, description="شناسه پرداخت با تراکنش تطابق ندارد.")

        if tx.amount <= 0:
            abort(409, description="مبلغ تراکنش نامعتبر است.")

        claim = PaymentTransaction.query.filter(
            PaymentTransaction.id == tx.id,
            PaymentTransaction.status.in_({"pending", "redirect", "failed"}),
        ).update({"status": "verifying"}, synchronize_session=False)
        if claim != 1:
            db.session.rollback()
            current = db.session.get(PaymentTransaction, tx.id)
            if current and current.status == "paid":
                return redirect(url_for("my_orders"))
            abort(409, description="این callback هم‌زمان در حال پردازش است.")
        db.session.commit()
        tx = db.session.get(PaymentTransaction, tx.id)

        result = gateway.verify(tx.public_id, tx.amount, request.values.to_dict())
        if not result.paid:
            failed = PaymentTransaction.query.filter(
                PaymentTransaction.id == tx.id,
                PaymentTransaction.status == "verifying",
            ).update({"status": "failed", "failed_at": db.func.now()}, synchronize_session=False)
            if failed != 1:
                db.session.rollback()
                current = db.session.get(PaymentTransaction, tx.id)
                if current and current.status == "paid":
                    return redirect(url_for("my_orders"))
                abort(409, description="وضعیت تراکنش هنگام ثبت نتیجه تغییر کرده است.")
            db.session.commit()
            flash(result.message or "پرداخت ناموفق بود.", "danger")
            return redirect(url_for("my_orders"))
        if not result.reference:
            db.session.rollback()
            abort(502, description="درگاه مرجع پرداخت معتبری برنگرداند.")

        order = db.session.get(Order, tx.order_id)
        if not order or order.user_id != tx.user_id or int(order.total or 0) != tx.amount:
            db.session.rollback()
            abort(409, description="سفارش با تراکنش پرداخت تطابق ندارد.")

        tx.status = "paid"
        tx.gateway_reference = result.reference[:200]
        tx.paid_at = db.func.now()
        order.status = "تأیید شد"
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current = db.session.get(PaymentTransaction, tx.id)
            if current and current.status == "paid":
                return redirect(url_for("my_orders"))
            abort(409, description="ثبت هم‌زمان نتیجه پرداخت ممکن نشد.")
        flash("پرداخت با موفقیت تأیید شد. 💳", "success")
        return redirect(url_for("my_orders"))

    @app.post("/payment/refund/<string:transaction_id>")
    def payment_refund(transaction_id):
        if not session.get("user_id"):
            abort(401)
        tx = PaymentTransaction.query.filter_by(public_id=transaction_id).first_or_404()
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "admin":
            abort(403)
        if tx.status != "paid":
            abort(409, description="فقط تراکنش پرداخت‌شده قابل استرداد است.")
        order = db.session.get(Order, tx.order_id)
        if not order:
            abort(409, description="سفارش مرتبط با تراکنش پیدا نشد.")
        if order.status not in {"تأیید شد", "در حال آماده‌سازی"}:
            abort(409, description="پس از ارسال، استرداد از مسیر مرجوعی انجام می‌شود.")

        tx.status = "refunded"
        order.status = "لغو شد"
        try:
            from merchant_marketplace_v2 import SellerLedger
            for seller_order in list(getattr(order, "seller_orders", []) or []):
                if seller_order.status not in {"delivered", "cancelled"}:
                    seller_order.status = "cancelled"
                ledger = SellerLedger.query.filter_by(seller_order_id=seller_order.id).first()
                if ledger and ledger.status not in {"paid", "cancelled"}:
                    ledger.status = "cancelled"
        except ImportError:
            pass
        db.session.commit()
        return redirect(url_for("admin"))

    @app.after_request
    def payment_checkout_bridge(response):
        if request.endpoint == "checkout" and request.method == "POST" and response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            order_id = session.pop("checkout_payment_order_id", None)
            session.modified = True
            if "/orders" in location and order_id:
                order = db.session.get(Order, int(order_id))
                if order and order.user_id == session.get("user_id"):
                    response.status_code = 303
                    response.headers["Location"] = url_for("payment_start_form", order_id=order.id)
        return response

    @app.get("/payment/start/<int:order_id>")
    def payment_start_form(order_id):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        order = db.session.get(Order, order_id)
        if not order or order.user_id != session["user_id"]:
            abort(404)
        if order.status != "در انتظار بررسی" or int(order.total or 0) <= 0:
            abort(409, description="این سفارش در وضعیت قابل پرداخت نیست.")
        key = uuid.uuid4().hex
        token_factory = app.jinja_env.globals.get("csrf_token")
        token = str(token_factory()) if callable(token_factory) else ""
        return render_template(
            "payment_start.html",
            order=order,
            csrf_token=token,
            idempotency_key=key,
        )

    app._kharidino_payment = True
