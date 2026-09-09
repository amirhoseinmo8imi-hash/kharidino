"""Refund/cancellation guardrails for seller settlement integrity.

A refund must unwind seller availability before money can be paid out.  This
module deliberately runs at the ORM boundary so an admin refund, a customer
cancellation, or another code path changing the master order cannot leave a
requested settlement reserving money that no longer exists.
"""
from __future__ import annotations

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

    def _affected_store_ids(session_obj, order):
        return {
            int(sub.store_id)
            for sub in session_obj.query(SellerOrder).filter_by(order_id=order.id).all()
            if sub.store_id is not None
        }

    def _protect_and_release(session_obj, store_ids, order_id):
        """Reject already-paid payouts; cancel stale requested reservations."""
        if not store_ids:
            return

        paid = session_obj.query(SellerSettlement).filter(
            SellerSettlement.store_id.in_(store_ids),
            SellerSettlement.status == "paid",
        ).all()
        if paid:
            ids = ", ".join(str(x.id) for x in paid[:5])
            raise ValueError(
                f"سفارش #{order_id} قبلاً وارد تسویه پرداخت‌شده شده است؛ "
                f"ابتدا تسویه‌های پرداخت‌شده باید با فرآیند clawback مدیریت شوند. "
                f"شناسه تسویه: {ids}"
            )

        requested = session_obj.query(SellerSettlement).filter(
            SellerSettlement.store_id.in_(store_ids),
            SellerSettlement.status == "requested",
        ).all()
        for settlement in requested:
            allocations = session_obj.query(SellerSettlementAllocation).filter_by(
                settlement_id=settlement.id
            ).all()
            # A settlement request is a reservation, not a payment. Once its
            # underlying order is cancelled/refunded, the reservation must die.
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
                store_ids = _affected_store_ids(session_obj, order)
                _protect_and_release(session_obj, store_ids, order_id)

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
