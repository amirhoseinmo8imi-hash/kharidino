"""Provider-neutral payment lifecycle for Kharidino."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from flask import abort, flash, redirect, request, session, url_for
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
        if not session.get("user_id") or tx.user_id != session["user_id"]:
            abort(403)
        if tx.status == "paid":
            return redirect(url_for("my_orders"))
        if tx.status in {"cancelled", "refunded"}:
            abort(409, description="این تراکنش دیگر قابل تأیید نیست.")

        gateway = _gateway()
        if gateway.name != "test" and not _valid_callback_signature(tx.public_id, request.values.get("signature", "")):
            abort(403, description="امضای callback نامعتبر است.")
        returned_authority = str(request.values.get("authority", "")).strip()
        if tx.authority and returned_authority and not hmac.compare_digest(tx.authority, returned_authority):
            abort(409, description="شناسه پرداخت با تراکنش تطابق ندارد.")

        if tx.amount <= 0:
            abort(409, description="مبلغ تراکنش نامعتبر است.")
        tx.status = "verifying"
        db.session.commit()
        result = gateway.verify(tx.public_id, tx.amount, request.values.to_dict())
        if not result.paid:
            tx.status = "failed"
            tx.failed_at = db.func.now()
            db.session.commit()
            flash(result.message or "پرداخت ناموفق بود.", "danger")
            return redirect(url_for("my_orders"))
        if not result.reference:
            abort(502, description="درگاه مرجع پرداخت معتبری برنگرداند.")

        tx.status = "paid"
        tx.gateway_reference = result.reference[:200]
        tx.paid_at = db.func.now()
        order = db.session.get(Order, tx.order_id)
        if not order or order.user_id != tx.user_id or int(order.total or 0) != tx.amount:
            db.session.rollback()
            abort(409, description="سفارش با تراکنش پرداخت تطابق ندارد.")
        # Payment confirmation is the single point at which the marketplace
        # may move the master order forward and create seller suborders.
        order.status = "تأیید شد"
        db.session.commit()
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
        tx.status = "refunded"
        db.session.commit()
        return redirect(url_for("admin"))

    @app.after_request
    def payment_checkout_bridge(response):
        if request.endpoint == "checkout" and request.method == "POST" and response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            if "/orders" in location and session.get("user_id"):
                order = Order.query.filter_by(user_id=session["user_id"]).order_by(Order.id.desc()).first()
                if order:
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
        return ("<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>پرداخت | خریدینو</title>"
                f"<body style='font-family:Tahoma;max-width:560px;margin:60px auto;padding:24px'>"
                f"<h1>پرداخت سفارش #{order.id}</h1><p>مبلغ: {int(order.total):,}</p>"
                f"<form method='post' action='/payment/start/{order.id}'>"
                f"<input type='hidden' name='idempotency_key' value='{key}'>"
                "<button type='submit'>ادامه به درگاه پرداخت</button></form></body></html>")

    app._kharidino_payment = True
