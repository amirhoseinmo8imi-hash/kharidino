"""Return-to-payment bridge with idempotent full-order refund semantics."""
from __future__ import annotations

import os
from datetime import datetime

import requests
from sqlalchemy.exc import IntegrityError


def _money(value) -> int:
    return max(0, int(round(value or 0)))


def apply_return_refund_bridge(app, db, Order, PaymentTransaction):
    if app.extensions.get("kharidino_return_refund_bridge"):
        return
    RefundRecord = app.extensions.get("kharidino_refund_record")
    if RefundRecord is None:
        raise RuntimeError("Refund hardening must be applied before return refund bridge.")

    def gateway_refund(tx):
        if os.environ.get("PAYMENT_TEST_MODE", "0").lower() in {"1", "true", "yes"}:
            return True, "TEST-RETURN-REFUND-" + tx.public_id[:24], ""
        if os.environ.get("PAYMENT_PROVIDER", "disabled").strip().lower() != "nextpay":
            return False, "", "Refund برای درگاه فعال پیاده‌سازی نشده است."
        api_key = os.environ.get("NEXTPAY_API_KEY", "").strip()
        trans_id = (tx.authority or "").strip()
        if not api_key or not trans_id:
            return False, "", "تنظیمات NextPay یا شناسه تراکنش ناقص است."
        try:
            timeout = max(2.0, min(float(os.environ.get("PAYMENT_HTTP_TIMEOUT", "10")), 30.0))
        except ValueError:
            timeout = 10.0
        try:
            response = requests.post(
                "https://nextpay.org/nx/gateway/verify",
                data={
                    "api_key": api_key,
                    "trans_id": trans_id,
                    "amount": int(tx.amount),
                    "refund_request": "yes_money_back",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            return False, "", f"خطای ارتباط با درگاه: {type(exc).__name__}"
        if str(body.get("code")) == "-90":
            return True, str(body.get("trans_id") or trans_id)[:200], ""
        return False, "", f"استرداد درگاه انجام نشد (کد {body.get('code')})."

    def execute_return_refund(return_row):
        order = db.session.get(Order, return_row.order_id)
        if not order or order.user_id != return_row.user_id:
            return False, "سفارش مرجوعی معتبر نیست."
        tx = (PaymentTransaction.query.filter_by(order_id=order.id, status="paid")
              .order_by(PaymentTransaction.id.desc()).first())
        if tx is None:
            existing = RefundRecord.query.filter_by(order_id=order.id, status="succeeded").first()
            return (True, "") if existing else (False, "تراکنش پرداخت‌شده‌ای برای این سفارش پیدا نشد.")

        requested = _money(return_row.refund_amount)
        if requested <= 0:
            requested = int(tx.amount)
        if requested != int(tx.amount):
            return False, "درگاه فعلی فقط استرداد کامل تراکنش را پشتیبانی می‌کند."

        existing = RefundRecord.query.filter_by(payment_transaction_id=tx.id).first()
        if existing and existing.status == "succeeded":
            return True, ""
        if existing and existing.status == "pending":
            return False, "استرداد قبلی هنوز در وضعیت نامشخص است و نباید دوباره به درگاه ارسال شود."
        if tx.status != "paid":
            return False, "این تراکنش دیگر در وضعیت قابل استرداد نیست."

        if existing is None:
            existing = RefundRecord(
                payment_transaction_id=tx.id,
                order_id=order.id,
                amount=int(tx.amount),
                status="pending",
            )
            db.session.add(existing)
            db.session.commit()

        ok, provider_reference, error = gateway_refund(tx)
        if not ok:
            existing.status = "failed"
            existing.error_message = error[:500]
            db.session.commit()
            return False, error

        tx.status = "refunded"
        order.status = "لغو شد"
        existing.status = "succeeded"
        existing.provider_reference = provider_reference
        existing.completed_at = datetime.utcnow()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            current = RefundRecord.query.filter_by(payment_transaction_id=tx.id).first()
            if current and current.status == "succeeded":
                return True, ""
            raise
        return True, ""

    app.extensions["kharidino_execute_return_refund"] = execute_return_refund
    app.extensions["kharidino_return_refund_bridge"] = True
