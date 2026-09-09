"""Deterministic financial reconciliation for Kharidino.

This module does not mutate financial facts. It audits payment, refund,
ledger, settlement, allocation and clawback records and returns explicit
failures. A failed reconciliation is intentionally suitable for blocking a
future settlement in an orchestration layer.
"""
from __future__ import annotations

from flask import jsonify, session
from sqlalchemy import func

from app import app, db, Order, admin_required
from merchant_marketplace_v2 import SellerLedger, SellerOrder
from accounting import SellerSettlement, SellerSettlementAllocation


def _money(value) -> int:
    return max(0, int(round(value or 0)))


def reconcile_payment(tx):
    Journal = app.extensions["kharidino_financial_journal"]
    rows = Journal.query.filter_by(payment_transaction_id=tx.id).all()
    payment = [x for x in rows if x.event_type == "payment"]
    refunds = [x for x in rows if x.event_type == "refund"]
    cash_in = sum(_money(x.amount) for x in payment if x.account == "cash" and x.direction == "debit")
    seller_in = sum(_money(x.amount) for x in payment if x.account == "seller_payable" and x.direction == "credit")
    platform_in = sum(_money(x.amount) for x in payment if x.account == "platform_revenue" and x.direction == "credit")
    cash_out = sum(_money(x.amount) for x in refunds if x.account == "cash" and x.direction == "credit")
    seller_out = sum(_money(x.amount) for x in refunds if x.account == "seller_payable" and x.direction == "debit")
    platform_out = sum(_money(x.amount) for x in refunds if x.account == "platform_revenue" and x.direction == "debit")
    errors = []
    if tx.status in {"paid", "refunded"} and cash_in != _money(tx.amount):
        errors.append(f"payment cash mismatch: {cash_in} != {tx.amount}")
    if seller_in + platform_in != cash_in and payment:
        errors.append("payment split is not balanced")
    if refunds and cash_out != seller_out + platform_out:
        errors.append("refund split is not balanced")
    if tx.status == "refunded" and cash_out != _money(tx.amount):
        errors.append(f"refund cash mismatch: {cash_out} != {tx.amount}")
    return errors


def reconcile_ledger(ledger):
    expected = _money(ledger.gross) + _money(ledger.shipping) - _money(ledger.platform_fee)
    errors = []
    if _money(ledger.net) != max(0, expected):
        errors.append(f"ledger #{ledger.id} net mismatch")
    allocations = _money(db.session.query(func.coalesce(func.sum(SellerSettlementAllocation.amount), 0)).filter_by(ledger_id=ledger.id).scalar())
    if allocations > _money(ledger.net):
        errors.append(f"ledger #{ledger.id} over-allocated")
    if ledger.status == "paid" and allocations != _money(ledger.net):
        errors.append(f"paid ledger #{ledger.id} is not fully allocated")
    return errors


def reconcile_settlement(settlement):
    allocations = SellerSettlementAllocation.query.filter_by(settlement_id=settlement.id).all()
    allocated = sum(_money(x.amount) for x in allocations)
    errors = []
    if allocated != _money(settlement.amount):
        errors.append(f"settlement #{settlement.id} allocation mismatch")
    for allocation in allocations:
        ledger = db.session.get(SellerLedger, allocation.ledger_id)
        if not ledger or ledger.store_id != settlement.store_id:
            errors.append(f"settlement #{settlement.id} has invalid ledger ownership")
            continue
        if _money(allocation.amount) <= 0 or _money(allocation.amount) > _money(ledger.net):
            errors.append(f"settlement #{settlement.id} has invalid allocation amount")
    Journal = app.extensions["kharidino_financial_journal"]
    if settlement.status == "paid":
        seller_ref = f"SETTLEMENT:{settlement.id}:SELLER"
        cash_ref = f"SETTLEMENT:{settlement.id}:CASH"
        if Journal.query.filter_by(reference=seller_ref).count() != 1:
            errors.append(f"settlement #{settlement.id} missing/duplicate seller journal")
        if Journal.query.filter_by(reference=cash_ref).count() != 1:
            errors.append(f"settlement #{settlement.id} missing/duplicate cash journal")
    return errors


def reconcile_all(*, fail_fast=False):
    PaymentTransaction = app.extensions["kharidino_payment_transaction"]
    RefundRecord = app.extensions.get("kharidino_refund_record")
    SellerClawback = app.extensions.get("kharidino_seller_clawback")
    Resolution = app.extensions.get("kharidino_seller_clawback_resolution")
    failures = []
    for tx in PaymentTransaction.query.filter(PaymentTransaction.status.in_(["paid", "refunded"])).all():
        for error in reconcile_payment(tx):
            failures.append({"type": "payment", "id": tx.id, "error": error})
            if fail_fast:
                return failures
    for ledger in SellerLedger.query.all():
        for error in reconcile_ledger(ledger):
            failures.append({"type": "ledger", "id": ledger.id, "error": error})
            if fail_fast:
                return failures
    for settlement in SellerSettlement.query.all():
        for error in reconcile_settlement(settlement):
            failures.append({"type": "settlement", "id": settlement.id, "error": error})
            if fail_fast:
                return failures
    if SellerClawback is not None:
        for clawback in SellerClawback.query.all():
            resolved = 0
            if Resolution is not None:
                resolved = _money(db.session.query(func.coalesce(func.sum(Resolution.amount), 0)).filter_by(clawback_id=clawback.id).scalar())
            if resolved > _money(clawback.amount):
                failures.append({"type": "clawback", "id": clawback.id, "error": "clawback resolutions exceed target"})
            expected_status = "settled" if _money(clawback.amount) and resolved >= _money(clawback.amount) else ("partial" if resolved else "open")
            if clawback.status != expected_status:
                failures.append({"type": "clawback", "id": clawback.id, "error": f"status mismatch: {clawback.status} != {expected_status}"})
            if fail_fast and failures:
                return failures
    return failures


def is_store_settlement_safe(store_id: int) -> tuple[bool, list[dict]]:
    failures = []
    for ledger in SellerLedger.query.filter_by(store_id=store_id).all():
        failures.extend({"type": "ledger", "id": ledger.id, "error": e} for e in reconcile_ledger(ledger))
    for settlement in SellerSettlement.query.filter_by(store_id=store_id).all():
        failures.extend({"type": "settlement", "id": settlement.id, "error": e} for e in reconcile_settlement(settlement))
    return not failures, failures


@app.get("/admin/accounting/reconciliation")
@admin_required
def admin_financial_reconciliation():
    failures = reconcile_all()
    return jsonify({"ok": not failures, "failure_count": len(failures), "failures": failures})


def apply_financial_reconciliation(app_obj, db_obj):
    if getattr(app_obj, "_kharidino_financial_reconciliation", False):
        return
    app_obj.extensions["kharidino_financial_reconciliation"] = reconcile_all
    app_obj.extensions["kharidino_store_settlement_safe"] = is_store_settlement_safe
    app_obj._kharidino_financial_reconciliation = True
