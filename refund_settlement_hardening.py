"""Refund/cancellation guardrails for seller settlement integrity.

A refund must unwind seller availability before money can be paid out. This
module runs at the ORM boundary so an admin refund, a customer cancellation,
or another code path changing the master order cannot leave a settlement
reservation attached to a refunded seller ledger.

The existing payment adapters do not expose a provider-side refund operation
yet. Therefore production refund requests fail closed instead of pretending
that money was returned to the customer. Test mode remains usable for CI and
local lifecycle tests.
"""
from __future__ import annotations

import os

from flask import abort
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

    @app.before_request
    def _refund_gateway_guard():
        if not (os.environ.get("PAYMENT_TEST_MODE", "0").lower() in {"1", "true", "yes"}):
            if __import__("flask").request.path.startswith("/payment/refund/"):
                abort(503, description="بازگشت وجه واقعی هنوز توسط آداپتور درگاه فعال پیاده‌سازی نشده است؛ تراکنش داخلی تغییر نکرد.")

    def _affected_ledger_ids(session_obj, order):
        seller_order_ids = [
            x.id for x in session_obj.query(SellerOrder.id)
            .filter_by(order_id=order.id).all()
        ]
        if not seller_order_ids:
            return set()
        return {
            int(x.id)
            for x in session_obj.query(SellerLedger.id)
            .filter(SellerLedger.seller_order_id.in_(seller_order_ids)).all()
        }

    def _protect_and_release(session_obj, ledger_ids, order_id):
        """Reject paid payouts; cancel only reservations touching this order."""
        if not ledger_ids:
            return

        affected_settlement_ids = {
            int(x.settlement_id)
            for x in session_obj.query(SellerSettlementAllocation.settlement_id)
            .filter(SellerSettlementAllocation.ledger_id.in_(ledger_ids)).all()
        }
        if not affected_settlement_ids:
            return

        paid = session_obj.query(SellerSettlement).filter(
            SellerSettlement.id.in_(affected_settlement_ids),
            SellerSettlement.status == "paid",
        ).all()
        if paid:
            ids = ", ".join(str(x.id) for x in paid[:5])
            abort(
                409,
                description=(
                    f"سفارش #{order_id} قبلاً وارد تسویه پرداخت‌شده شده است؛ "
                    f"ابتدا تسویه‌های پرداخت‌شده باید با فرآیند clawback مدیریت شوند. "
                    f"شناسه تسویه: {ids}"
                ),
            )

        requested = session_obj.query(SellerSettlement).filter(
            SellerSettlement.id.in_(affected_settlement_ids),
            SellerSettlement.status == "requested",
        ).all()
        for settlement in requested:
            allocations = session_obj.query(SellerSettlementAllocation).filter_by(
                settlement_id=settlement.id
            ).all()
            # A settlement request is a reservation, not a payment. Once one
            # of its underlying order ledgers is refunded, cancel the whole
            # request so its remaining allocations cannot be paid accidentally.
            for allocation in allocations:
                session_obj.delete(allocation)
            settlement.status = "cancelled"
            settlement.note = (
                (settlement.note or "") +
                f"\nرزرو به‌دلیل لغو/مرجوعی سفارش #{order_id} آزاد شد."
            )[:5000]

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
                _protect_and_release(session_obj, ledger_ids, order_id)

                # Keep seller-side balances aligned with the master order.
                for seller_order in session_obj.query(SellerOrder).filter_by(order_id=order.id).all():
                    if seller_order.status not in {"delivered", "cancelled"}:
                        seller_order.status = "cancelled"
                    ledger = session_obj.query(SellerLedger).filter_by(
                        seller_order_id=seller_order.id
                    ).first()
                    if ledger and ledger.status not in {"paid", "cancelled"}:
                        ledger.status = "cancelled"
        finally:
            session_obj.info["kharidino_refund_guard_running"] = False

    app._kharidino_refund_settlement_hardening = True
