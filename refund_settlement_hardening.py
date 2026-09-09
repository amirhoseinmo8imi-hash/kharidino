"""Production refund execution and seller-settlement clawback safeguards."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

import requests
from flask import abort, redirect, session, url_for
from sqlalchemy import event
from sqlalchemy.orm import Session


def _money(value) -> int:
    return max(0, int(round(value or 0)))


def apply_refund_settlement_hardening(
    app,
    db,
    Order,
    PaymentTransaction,
    SellerOrder,
    SellerLedger,
    SellerSettlement,
    SellerSettlementAllocation,
):
    if getattr(app, "_kharidino_refund_settlement_hardening", False):
        return

    class RefundRecord(db.Model):
        __tablename__ = "kharidino_refund_record"
        id = db.Column(db.Integer, primary_key=True)
        public_id = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
        payment_transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transaction.id"), nullable=False, unique=True, index=True)
        order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
        amount = db.Column(db.Integer, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="pending", index=True)
        provider_reference = db.Column(db.String(200), nullable=True)
        error_message = db.Column(db.String(500), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        completed_at = db.Column(db.DateTime, nullable=True)

    class SellerClawback(db.Model):
        __tablename__ = "kharidino_seller_clawback"
        id = db.Column(db.Integer, primary_key=True)
        reference = db.Column(db.String(180), unique=True, nullable=False, index=True)
        refund_id = db.Column(db.Integer, db.ForeignKey("kharidino_refund_record.id"), nullable=False, index=True)
        seller_ledger_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_ledger.id"), nullable=False, index=True)
        store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
        amount = db.Column(db.Integer, nullable=False)
        status = db.Column(db.String(20), nullable=False, default="open", index=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        settled_at = db.Column(db.DateTime, nullable=True)
        __table_args__ = (
            db.UniqueConstraint("refund_id", "seller_ledger_id", name="uq_refund_clawback_ledger"),
        )

    app.extensions["kharidino_refund_record"] = RefundRecord
    app.extensions["kharidino_seller_clawback"] = SellerClawback

    def _affected_ledger_ids(session_obj, order):
        seller_order_ids = [
            x.id for x in session_obj.query(SellerOrder.id).filter_by(order_id=order.id).all()
        ]
        if not seller_order_ids:
            return set()
        return {
            int(x.id)
            for x in session_obj.query(SellerLedger.id)
            .filter(SellerLedger.seller_order_id.in_(seller_order_ids)).all()
        }

    def _settlements_for_ledgers(session_obj, ledger_ids):
        if not ledger_ids:
            return []
        ids = {
            int(x.settlement_id)
            for x in session_obj.query(SellerSettlementAllocation.settlement_id)
            .filter(SellerSettlementAllocation.ledger_id.in_(ledger_ids)).all()
        }
        if not ids:
            return []
        return session_obj.query(SellerSettlement).filter(SellerSettlement.id.in_(ids)).all()

    def _nextpay_refund(tx):
        """Execute NextPay's documented money-back request."""
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
        code = body.get("code")
        if str(code) == "-90":
            return True, str(body.get("trans_id") or trans_id)[:200], ""
        return False, "", f"استرداد درگاه انجام نشد (کد {code})."

    def _gateway_refund(tx):
        if os.environ.get("PAYMENT_TEST_MODE", "0").lower() in {"1", "true", "yes"}:
            return True, "TEST-REFUND-" + tx.public_id[:24], ""
        if (os.environ.get("PAYMENT_PROVIDER", "disabled").strip().lower()) == "nextpay":
            return _nextpay_refund(tx)
        return False, "", "Refund برای درگاه فعال فعلاً پیاده‌سازی نشده است."

    def _cancel_requested_reservations(session_obj, settlements, order_id):
        for settlement in settlements:
            if settlement.status != "requested":
                continue
            allocations = session_obj.query(SellerSettlementAllocation).filter_by(settlement_id=settlement.id).all()
            for allocation in allocations:
                session_obj.delete(allocation)
            settlement.status = "cancelled"
            settlement.note = ((settlement.note or "") + f"\nتسویه به‌دلیل مرجوعی سفارش #{order_id} لغو شد.")[:5000]

    def _create_clawbacks(session_obj, refund, ledger_ids):
        for ledger in session_obj.query(SellerLedger).filter(SellerLedger.id.in_(ledger_ids)).all():
            existing = session_obj.query(SellerClawback).filter_by(
                refund_id=refund.id, seller_ledger_id=ledger.id
            ).first()
            if existing:
                continue
            amount = _money(ledger.net)
            if amount <= 0:
                continue
            session_obj.add(SellerClawback(
                reference=f"CLAWBACK:{refund.public_id}:{ledger.id}",
                refund_id=refund.id,
                seller_ledger_id=ledger.id,
                store_id=ledger.store_id,
                amount=amount,
                status="open",
            ))

    @event.listens_for(Session, "before_flush")
    def _refund_before_flush(session_obj, flush_context, instances):
        if session_obj.info.get("kharidino_refund_guard_running"):
            return
        session_obj.info["kharidino_refund_guard_running"] = True
        try:
            refund_orders = set()
            for obj in list(session_obj.dirty):
                if isinstance(obj, PaymentTransaction):
                    state = __import__("sqlalchemy").inspect(obj)
                    history = state.attrs.status.history
                    if history.has_changes() and obj.status == "refunded":
                        refund_orders.add(int(obj.order_id))
                elif isinstance(obj, Order):
                    state = __import__("sqlalchemy").inspect(obj)
                    history = state.attrs.status.history
                    if history.has_changes() and obj.status in {"لغو شد", "cancelled"}:
                        refund_orders.add(int(obj.id))

            for order_id in refund_orders:
                order = session_obj.get(Order, order_id)
                if not order:
                    continue
                ledger_ids = _affected_ledger_ids(session_obj, order)
                settlements = _settlements_for_ledgers(session_obj, ledger_ids)
                paid = [x for x in settlements if x.status == "paid"]
                if paid:
                    # Paid settlements are not silently reversed: the explicit
                    # clawback records created by the refund endpoint represent
                    # the seller's debt back to the platform.
                    pass
                else:
                    _cancel_requested_reservations(session_obj, settlements, order_id)

                for seller_order in session_obj.query(SellerOrder).filter_by(order_id=order.id).all():
                    if seller_order.status not in {"delivered", "cancelled"}:
                        seller_order.status = "cancelled"
                    ledger = session_obj.query(SellerLedger).filter_by(seller_order_id=seller_order.id).first()
                    if ledger and ledger.status not in {"paid", "cancelled"}:
                        ledger.status = "cancelled"
        finally:
            session_obj.info["kharidino_refund_guard_running"] = False

    original_refund = app.view_functions.get("payment_refund")
    if original_refund:
        def hardened_payment_refund(*args, **kwargs):
            if not session.get("user_id"):
                abort(401)
            transaction_id = kwargs.get("transaction_id") or (args[0] if args else "")
            tx = PaymentTransaction.query.filter_by(public_id=transaction_id).first_or_404()
            user = db.session.get(__import__("app").User, session["user_id"])
            if not user or user.role != "admin":
                abort(403)

            existing = RefundRecord.query.filter_by(payment_transaction_id=tx.id).first()
            if existing and existing.status == "succeeded":
                return redirect(url_for("admin"))
            if tx.status != "paid":
                abort(409, description="فقط تراکنش پرداخت‌شده قابل استرداد است.")
            order = db.session.get(Order, tx.order_id)
            if not order:
                abort(409, description="سفارش مرتبط با تراکنش پیدا نشد.")
            if order.status not in {"تأیید شد", "در حال آماده‌سازی"}:
                abort(409, description="این سفارش در وضعیت قابل استرداد نیست.")

            ledger_ids = _affected_ledger_ids(db.session, order)
            settlements = _settlements_for_ledgers(db.session, ledger_ids)
            paid_settlements = [x for x in settlements if x.status == "paid"]

            if not existing:
                existing = RefundRecord(
                    payment_transaction_id=tx.id,
                    order_id=order.id,
                    amount=int(tx.amount),
                    status="pending",
                )
                db.session.add(existing)
                db.session.commit()

            ok, provider_reference, error = _gateway_refund(tx)
            if not ok:
                existing.status = "failed"
                existing.error_message = error[:500]
                db.session.commit()
                abort(502, description=error)

            tx.status = "refunded"
            order.status = "لغو شد"
            existing.status = "succeeded"
            existing.provider_reference = provider_reference
            existing.completed_at = db.func.now()

            if paid_settlements:
                _create_clawbacks(db.session, existing, ledger_ids)
            else:
                _cancel_requested_reservations(db.session, settlements, order.id)

            for seller_order in SellerOrder.query.filter_by(order_id=order.id).all():
                if seller_order.status not in {"delivered", "cancelled"}:
                    seller_order.status = "cancelled"
                ledger = SellerLedger.query.filter_by(seller_order_id=seller_order.id).first()
                if ledger and ledger.status not in {"paid", "cancelled"}:
                    ledger.status = "cancelled"
            db.session.commit()
            return redirect(url_for("admin"))

        app.view_functions["payment_refund"] = hardened_payment_refund

    app._kharidino_refund_settlement_hardening = True
