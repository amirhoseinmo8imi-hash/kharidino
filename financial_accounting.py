"""Idempotent double-entry financial journal for Kharidino.

This module is intentionally separate from the existing accounting dashboard.
It records immutable financial facts from payment, seller split, refund and
settlement events. Operational dashboards can safely derive balances from it.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session


def _money(value) -> int:
    return max(0, int(round(value or 0)))


def apply_financial_accounting(app, db, Order, SellerLedger, SellerSettlement):
    if getattr(app, "_kharidino_financial_accounting", False):
        return

    class FinancialJournalEntry(db.Model):
        __tablename__ = "kharidino_financial_journal"
        id = db.Column(db.Integer, primary_key=True)
        reference = db.Column(db.String(180), unique=True, nullable=False, index=True)
        event_type = db.Column(db.String(40), nullable=False, index=True)
        account = db.Column(db.String(60), nullable=False, index=True)
        direction = db.Column(db.String(10), nullable=False)
        amount = db.Column(db.Integer, nullable=False)
        order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=True, index=True)
        seller_order_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_order.id"), nullable=True, index=True)
        store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=True, index=True)
        payment_transaction_id = db.Column(db.Integer, nullable=True, index=True)
        settlement_id = db.Column(db.Integer, nullable=True, index=True)
        description = db.Column(db.String(500), nullable=False, default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    app.extensions["kharidino_financial_journal"] = FinancialJournalEntry

    def add_entry(session_obj, *, reference, event_type, account, direction, amount,
                  order_id=None, seller_order_id=None, store_id=None,
                  payment_transaction_id=None, settlement_id=None, description=""):
        amount = _money(amount)
        if amount <= 0:
            return
        if session_obj.query(FinancialJournalEntry.id).filter_by(reference=reference).first():
            return
        session_obj.add(FinancialJournalEntry(
            reference=reference,
            event_type=event_type,
            account=account,
            direction=direction,
            amount=amount,
            order_id=order_id,
            seller_order_id=seller_order_id,
            store_id=store_id,
            payment_transaction_id=payment_transaction_id,
            settlement_id=settlement_id,
            description=description[:500],
        ))

    def paid_order_journal(session_obj, tx):
        if not tx or tx.status != "paid":
            return
        order = session_obj.get(Order, tx.order_id)
        if not order or int(order.total or 0) != int(tx.amount or 0):
            return

        seller_orders = list(getattr(order, "seller_orders", []) or [])
        # If a payment is confirmed but no approved seller offer exists, keep
        # the customer cash/sales fact balanced without inventing seller debt.
        gross_seller = sum(_money(x.subtotal) + _money(x.shipping_fee) for x in seller_orders)
        fee = sum(_money(x.platform_fee) for x in seller_orders)
        seller_net = sum(_money(x.seller_total) for x in seller_orders)
        remainder = max(0, int(tx.amount) - gross_seller)
        if not seller_orders:
            seller_net = 0
            fee = int(tx.amount)
            remainder = 0
        elif remainder:
            # Any non-seller portion (e.g. platform shipping/adjustment) is
            # treated as platform revenue so the journal remains balanced.
            fee += remainder

        add_entry(session_obj, reference=f"PAYMENT:{tx.public_id}:CASH", event_type="payment", account="cash", direction="debit", amount=tx.amount, order_id=order.id, payment_transaction_id=tx.id, description=f"دریافت وجه سفارش #{order.id}")
        if seller_net:
            add_entry(session_obj, reference=f"PAYMENT:{tx.public_id}:SELLER", event_type="payment", account="seller_payable", direction="credit", amount=seller_net, order_id=order.id, payment_transaction_id=tx.id, description=f"بدهی فروشندگان سفارش #{order.id}")
        if fee:
            add_entry(session_obj, reference=f"PAYMENT:{tx.public_id}:PLATFORM", event_type="payment", account="platform_revenue", direction="credit", amount=fee, order_id=order.id, payment_transaction_id=tx.id, description=f"درآمد پلتفرم از سفارش #{order.id}")

    def refunded_order_journal(session_obj, tx):
        if not tx or tx.status != "refunded":
            return
        original = session_obj.query(FinancialJournalEntry).filter_by(reference=f"PAYMENT:{tx.public_id}:CASH").first()
        if not original:
            return
        order = session_obj.get(Order, tx.order_id)
        if not order:
            return
        seller_orders = list(getattr(order, "seller_orders", []) or [])
        seller_net = sum(_money(x.seller_total) for x in seller_orders)
        fee = sum(_money(x.platform_fee) for x in seller_orders)
        if seller_orders:
            fee += max(0, int(tx.amount) - seller_net - fee)
        else:
            fee = int(tx.amount)
        add_entry(session_obj, reference=f"REFUND:{tx.public_id}:CASH", event_type="refund", account="cash", direction="credit", amount=tx.amount, order_id=order.id, payment_transaction_id=tx.id, description=f"استرداد وجه سفارش #{order.id}")
        if seller_net:
            add_entry(session_obj, reference=f"REFUND:{tx.public_id}:SELLER", event_type="refund", account="seller_payable", direction="debit", amount=seller_net, order_id=order.id, payment_transaction_id=tx.id, description=f"برگشت بدهی فروشندگان سفارش #{order.id}")
        if fee:
            add_entry(session_obj, reference=f"REFUND:{tx.public_id}:PLATFORM", event_type="refund", account="platform_revenue", direction="debit", amount=fee, order_id=order.id, payment_transaction_id=tx.id, description=f"برگشت درآمد پلتفرم سفارش #{order.id}")

    @event.listens_for(Session, "after_flush_postexec")
    def _financial_after_flush_postexec(session_obj, flush_context):
        if session_obj.info.get("kharidino_financial_running"):
            return
        session_obj.info["kharidino_financial_running"] = True
        try:
            payment_model = app.extensions.get("kharidino_payment_transaction")
            if payment_model:
                paid_ids = session_obj.info.setdefault("kharidino_financial_paid_ids", set())
                refund_ids = session_obj.info.setdefault("kharidino_financial_refund_ids", set())
                for tx in session_obj.query(payment_model).filter(payment_model.status.in_(["paid", "refunded"])).all():
                    if tx.status == "paid" and tx.id not in paid_ids:
                        paid_order_journal(session_obj, tx)
                        paid_ids.add(tx.id)
                    elif tx.status == "refunded" and tx.id not in refund_ids:
                        refunded_order_journal(session_obj, tx)
                        refund_ids.add(tx.id)

            settlement_ids = session_obj.info.setdefault("kharidino_financial_settlement_ids", set())
            for settlement in session_obj.query(SellerSettlement).filter_by(status="paid").all():
                if settlement.id in settlement_ids:
                    continue
                add_entry(session_obj, reference=f"SETTLEMENT:{settlement.id}:SELLER", event_type="settlement", account="seller_payable", direction="debit", amount=settlement.amount, store_id=settlement.store_id, settlement_id=settlement.id, description=f"تسویه فروشنده #{settlement.id}")
                add_entry(session_obj, reference=f"SETTLEMENT:{settlement.id}:CASH", event_type="settlement", account="cash", direction="credit", amount=settlement.amount, store_id=settlement.store_id, settlement_id=settlement.id, description=f"پرداخت تسویه فروشنده #{settlement.id}")
                settlement_ids.add(settlement.id)

            # Seller delivery is not enough to release funds: the master order
            # must also be delivered. This repairs early availability changes.
            delivered_orders = session_obj.query(Order).filter_by(status="تحویل شد").all()
            delivered_ids = session_obj.info.setdefault("kharidino_financial_release_ids", set())
            for order in delivered_orders:
                if order.id in delivered_ids:
                    continue
                for seller_order in list(getattr(order, "seller_orders", []) or []):
                    ledger = session_obj.query(SellerLedger).filter_by(seller_order_id=seller_order.id).first()
                    if ledger and ledger.status not in {"paid", "cancelled"}:
                        ledger.status = "available"
                delivered_ids.add(order.id)
        finally:
            session_obj.info["kharidino_financial_running"] = False

    app._kharidino_financial_accounting = True
