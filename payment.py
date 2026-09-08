"""Payment domain for Kharidino.

The module deliberately keeps gateway-specific code behind a small adapter so a
real Iranian gateway can be plugged in without changing order accounting.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from flask import abort, redirect, request, session, url_for, flash
from sqlalchemy.exc import IntegrityError


PAYMENT_STATUSES = {
    "pending",
    "redirect",
    "verifying",
    "paid",
    "failed",
    "cancelled",
    "refunded",
}


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
    """Provider-neutral payment contract."""

    name = "abstract"

    @abstractmethod
    def start(self, transaction_id: str, amount: int, callback_url: str) -> GatewayStartResult:
        raise NotImplementedError

    @abstractmethod
    def verify(self, transaction_id: str, amount: int, payload: dict) -> GatewayVerifyResult:
        raise NotImplementedError


class DisabledGateway(PaymentGateway):
    """Safe default: production cannot accidentally mark money as paid."""

    name = "disabled"

    def start(self, transaction_id: str, amount: int, callback_url: str) -> GatewayStartResult:
        return GatewayStartResult("failed", "", "")

    def verify(self, transaction_id: str, amount: int, payload: dict) -> GatewayVerifyResult:
        return GatewayVerifyResult(False, "", "درگاه پرداخت فعال نیست.")


class TestGateway(PaymentGateway):
    """Deterministic local gateway for integration tests/development only."""

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
    if not value:
        raise ValueError("کلید idempotency الزامی است.")
    if len(value) > 128:
        raise ValueError("کلید idempotency بیش از حد طولانی است.")
    return value


def _callback_secret() -> str:
    return os.environ.get("PAYMENT_CALLBACK_SECRET", "").strip()


def _valid_callback_signature(transaction_id: str, signature: str) -> bool:
    secret = _callback_secret()
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode(),
        transaction_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _set_paid(transaction, reference: str) -> None:
    transaction.status = "paid"
    transaction.gateway_reference = reference[:200]
    transaction.paid_at = transaction.db.func.now() if hasattr(transaction, "db") else None


def apply_payment(app, db, Order):
    """Install payment models/routes exactly once."""
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
        if order.status == "لغو شد":
            abort(409, description="سفارش لغوشده قابل پرداخت نیست.")
        if int(order.total or 0) <= 0:
            abort(409, description="مبلغ سفارش نامعتبر است.")

        raw_key = request.form.get("idempotency_key") or request.headers.get("Idempotency-Key")
        try:
            key = _idempotency_key(raw_key)
        except ValueError as exc:
            abort(400, description=str(exc))

        existing = PaymentTransaction.query.filter_by(idempotency_key=key).first()
        if existing:
            if existing.user_id != session["user_id"] or existing.order_id != order.id:
                abort(409, description="کلید idempotency قبلاً برای تراکنش دیگری استفاده شده است.")
            if existing.status == "redirect" and existing.authority:
                return redirect(url_for("payment_callback", transaction_id=existing.public_id))
            if existing.status == "paid":
                flash("این سفارش قبلاً پرداخت شده است.", "success")
                return redirect(url_for("my_orders"))
            tx = existing
        else:
            tx = PaymentTransaction(
                order_id=order.id,
                user_id=session["user_id"],
                amount=int(order.total),
                status="pending",
                gateway=_gateway().name,
                idempotency_key=key,
            )
            db.session.add(tx)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                tx = PaymentTransaction.query.filter_by(idempotency_key=key).first()
                if not tx:
                    raise

        gateway = _gateway()
        result = gateway.start(
            tx.public_id,
            tx.amount,
            url_for("payment_callback", transaction_id=tx.public_id, _external=True),
        )
        if result.status != "redirect":
            tx.status = "failed"
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

        signature = request.values.get("signature", "")
        gateway = _gateway()
        if gateway.name != "test" and not _valid_callback_signature(tx.public_id, signature):
            abort(403, description="امضای callback نامعتبر است.")

        tx.status = "verifying"
        db.session.commit()
        result = gateway.verify(tx.public_id, tx.amount, request.values.to_dict())
        if not result.paid:
            tx.status = "failed"
            tx.failed_at = db.func.now()
            db.session.commit()
            flash(result.message or "پرداخت ناموفق بود.", "danger")
            return redirect(url_for("my_orders"))

        tx.status = "paid"
        tx.gateway_reference = result.reference[:200]
        tx.paid_at = db.func.now()
        db.session.commit()
        flash("پرداخت با موفقیت تأیید شد. 💳", "success")
        return redirect(url_for("my_orders"))

    @app.post("/payment/refund/<string:transaction_id>")
    def payment_refund(transaction_id):
        if not session.get("user_id"):
            abort(401)
        tx = PaymentTransaction.query.filter_by(public_id=transaction_id).first_or_404()
        user = db.session.get("User", session["user_id"])
        if not user or user.role != "admin":
            abort(403)
        if tx.status != "paid":
            abort(409, description="فقط تراکنش پرداخت‌شده قابل استرداد است.")
        tx.status = "refunded"
        db.session.commit()
        return redirect(url_for("admin"))

    @app.after_request
    def payment_checkout_bridge(response):
        """Connect the existing checkout to payment without rewriting its UI."""
        if request.endpoint == "checkout" and request.method == "POST" and response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            if "/orders" in location and session.get("user_id"):
                order = (
                    Order.query.filter_by(user_id=session["user_id"])
                    .order_by(Order.id.desc())
                    .first()
                )
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
        key = uuid.uuid4().hex
        return (
            "<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>پرداخت | خریدینو</title>"
            f"<body style='font-family:Tahoma;max-width:560px;margin:60px auto;padding:24px'>"
            f"<h1>پرداخت سفارش #{order.id}</h1><p>مبلغ: {int(order.total):,}</p>"
            "<form method='post' action='/payment/start/"
            f"{order.id}'><input type='hidden' name='idempotency_key' value='{key}'>"
            "<button type='submit'>ادامه به درگاه پرداخت</button></form></body></html>"
        )

    app._kharidino_payment = True
