"""Professional accounting workspace for Kharidino.

The accounting layer deliberately derives sales from the existing marketplace
ledger instead of duplicating order totals. It adds only accounting-specific
records: platform expenses and seller settlement requests.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import Response, abort, flash, redirect, render_template, request, session, url_for

from app import app, db, User, Store, admin_required
from merchant_marketplace import MerchantStore, seller_required, _seller_account
from merchant_marketplace_v2 import SellerLedger


class AccountingExpense(db.Model):
    __tablename__ = "kharidino_accounting_expense"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="سایر")
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    creator = db.relationship("User")


class SellerSettlement(db.Model):
    __tablename__ = "kharidino_seller_settlement"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="requested", index=True)
    note = db.Column(db.Text, default="")
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    store = db.relationship("Store")


def _money(value: int | float) -> int:
    return max(0, int(round(value or 0)))


def _date_range():
    end_raw = request.args.get("to", "").strip()
    start_raw = request.args.get("from", "").strip()
    today = datetime.utcnow().date()
    end = today
    start = today - timedelta(days=29)
    for raw, attr in ((start_raw, "start"), (end_raw, "end")):
        if not raw:
            continue
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        if attr == "start":
            start = parsed
        else:
            end = parsed
    if start > end:
        start, end = end, start
    return start, end


def _ledger_totals(ledger):
    gross = sum(_money(x.gross) for x in ledger)
    fee = sum(_money(x.platform_fee) for x in ledger)
    net = sum(_money(x.net) for x in ledger)
    available = sum(_money(x.net) for x in ledger if x.status == "available")
    paid = sum(_money(x.net) for x in ledger if x.status == "paid")
    cancelled = sum(_money(x.gross) for x in ledger if x.status == "cancelled")
    return {
        "gross": gross,
        "fee": fee,
        "net": net,
        "available": available,
        "paid": paid,
        "cancelled": cancelled,
    }


def _platform_data(start, end):
    ledgers = SellerLedger.query.filter(
        SellerLedger.created_at >= datetime.combine(start, datetime.min.time()),
        SellerLedger.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
    ).order_by(SellerLedger.created_at.desc()).all()
    expenses = AccountingExpense.query.filter(
        AccountingExpense.created_at >= datetime.combine(start, datetime.min.time()),
        AccountingExpense.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
    ).order_by(AccountingExpense.created_at.desc()).all()
    settlements = SellerSettlement.query.filter(
        SellerSettlement.created_at >= datetime.combine(start, datetime.min.time()),
        SellerSettlement.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
    ).order_by(SellerSettlement.created_at.desc()).all()
    totals = _ledger_totals(ledgers)
    total_expenses = sum(_money(x.amount) for x in expenses)
    pending_settlements = sum(_money(x.amount) for x in settlements if x.status == "requested")
    completed_settlements = sum(_money(x.amount) for x in settlements if x.status == "paid")
    platform_profit = totals["fee"] - total_expenses
    return {
        "ledgers": ledgers,
        "expenses": expenses,
        "settlements": settlements,
        "totals": totals,
        "expense_total": total_expenses,
        "pending_settlements": pending_settlements,
        "completed_settlements": completed_settlements,
        "platform_profit": platform_profit,
    }


@app.get("/admin/accounting")
@admin_required
def admin_accounting():
    start, end = _date_range()
    data = _platform_data(start, end)
    stores = Store.query.order_by(Store.name.asc()).all()
    seller_rows = []
    for store in stores:
        rows = SellerLedger.query.filter_by(store_id=store.id).order_by(SellerLedger.id.desc()).limit(500).all()
        t = _ledger_totals(rows)
        if t["gross"] or t["net"]:
            seller_rows.append({"store": store, **t})
    return render_template(
        "accounting_dashboard.html",
        mode="platform",
        start=start.isoformat(),
        end=end.isoformat(),
        seller_rows=seller_rows,
        **data,
    )


@app.get("/seller/accounting")
@seller_required
def seller_accounting():
    account = _seller_account()
    start, end = _date_range()
    rows = SellerLedger.query.filter(
        SellerLedger.store_id == account.store_id,
        SellerLedger.created_at >= datetime.combine(start, datetime.min.time()),
        SellerLedger.created_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
    ).order_by(SellerLedger.created_at.desc()).all()
    totals = _ledger_totals(rows)
    settlements = SellerSettlement.query.filter_by(store_id=account.store_id).order_by(SellerSettlement.id.desc()).all()
    requested = sum(_money(x.amount) for x in settlements if x.status == "requested")
    paid = sum(_money(x.amount) for x in settlements if x.status == "paid")
    withdrawable = max(0, totals["available"] - requested - paid)
    return render_template(
        "accounting_dashboard.html",
        mode="seller",
        account=account,
        start=start.isoformat(),
        end=end.isoformat(),
        ledgers=rows,
        totals=totals,
        settlements=settlements,
        withdrawable=withdrawable,
        requested_settlements=requested,
        paid_settlements=paid,
        seller_rows=[],
        expenses=[],
        expense_total=0,
        pending_settlements=requested,
        completed_settlements=paid,
        platform_profit=0,
    )


@app.post("/seller/accounting/settlement")
@seller_required
def seller_request_settlement():
    account = _seller_account()
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        abort(400, description="مبلغ تسویه نامعتبر است.")
    if amount <= 0:
        abort(400, description="مبلغ تسویه باید بیشتر از صفر باشد.")
    available_rows = SellerLedger.query.filter_by(store_id=account.store_id, status="available").all()
    available = sum(_money(x.net) for x in available_rows)
    already_requested = sum(_money(x.amount) for x in SellerSettlement.query.filter_by(store_id=account.store_id, status="requested").all())
    already_paid = sum(_money(x.amount) for x in SellerSettlement.query.filter_by(store_id=account.store_id, status="paid").all())
    if amount > max(0, available - already_requested - already_paid):
        abort(409, description="مبلغ درخواستی از مانده قابل تسویه بیشتر است.")
    db.session.add(SellerSettlement(
        store_id=account.store_id,
        amount=amount,
        note=request.form.get("note", "").strip()[:1000],
        requested_by=session.get("user_id"),
    ))
    db.session.commit()
    flash("درخواست تسویه با موفقیت ثبت شد. ✅", "success")
    return redirect(url_for("seller_accounting"))


@app.post("/admin/accounting/expense")
@admin_required
def admin_add_expense():
    try:
        amount = int(request.form.get("amount", "0"))
    except ValueError:
        abort(400, description="مبلغ هزینه نامعتبر است.")
    if amount <= 0:
        abort(400, description="مبلغ هزینه باید بیشتر از صفر باشد.")
    title = request.form.get("title", "").strip()[:200]
    if not title:
        abort(400, description="عنوان هزینه الزامی است.")
    db.session.add(AccountingExpense(
        title=title,
        category=request.form.get("category", "سایر").strip()[:80] or "سایر",
        amount=amount,
        description=request.form.get("description", "").strip()[:2000],
        created_by=session.get("user_id"),
    ))
    db.session.commit()
    flash("هزینه در دفتر حسابداری ثبت شد. ✅", "success")
    return redirect(url_for("admin_accounting"))


@app.post("/admin/accounting/settlements/<int:settlement_id>/pay")
@admin_required
def admin_pay_settlement(settlement_id):
    settlement = SellerSettlement.query.get_or_404(settlement_id)
    if settlement.status != "requested":
        abort(409, description="این درخواست قبلاً پردازش شده است.")
    available = sum(_money(x.net) for x in SellerLedger.query.filter_by(store_id=settlement.store_id, status="available").all())
    outstanding = sum(_money(x.amount) for x in SellerSettlement.query.filter_by(store_id=settlement.store_id, status="requested").all())
    if settlement.amount > available or settlement.amount > outstanding:
        abort(409, description="مانده فروشنده برای این تسویه کافی نیست.")
    settlement.status = "paid"
    settlement.processed_by = session.get("user_id")
    settlement.processed_at = datetime.utcnow()
    # Mark the oldest available ledger rows as paid until the settlement is covered.
    remaining = settlement.amount
    ledgers = SellerLedger.query.filter_by(store_id=settlement.store_id, status="available").order_by(SellerLedger.id.asc()).all()
    for ledger in ledgers:
        if remaining <= 0:
            break
        ledger.status = "paid"
        ledger.paid_at = datetime.utcnow()
        remaining -= _money(ledger.net)
    db.session.commit()
    flash("تسویه فروشنده با موفقیت پرداخت شد. 💳", "success")
    return redirect(url_for("admin_accounting"))


@app.get("/admin/accounting/export.csv")
@admin_required
def admin_accounting_export():
    start, end = _date_range()
    data = _platform_data(start, end)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "store_id", "gross", "platform_fee", "seller_net", "status"])
    for ledger in data["ledgers"]:
        writer.writerow([
            ledger.created_at.isoformat() if ledger.created_at else "",
            ledger.store_id,
            ledger.gross,
            ledger.platform_fee,
            ledger.net,
            ledger.status,
        ])
    writer.writerow([])
    writer.writerow(["EXPENSE", "", "", "", "", ""])
    for expense in data["expenses"]:
        writer.writerow([expense.created_at.isoformat() if expense.created_at else "", "", expense.title, expense.amount, expense.category, "expense"])
    return Response(
        output.getvalue().encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=kharidino-accounting-{start}-{end}.csv"},
    )
