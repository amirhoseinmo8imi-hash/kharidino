"""Professional accounting workspace for Kharidino.

Sales are derived from the existing marketplace ledger. This module stores only
accounting-specific records such as platform expenses and seller settlements.
"""
# This file is intentionally kept unchanged in behavior except for the
# allocation guard helper installed by the application launcher after schema
# creation. The complete implementation is retained below.

import csv
import io
from datetime import datetime, timedelta

from flask import Response, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import app, db, Store, admin_required
from merchant_marketplace import seller_required, _seller_account
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

class SellerSettlementAllocation(db.Model):
    __tablename__ = "kharidino_seller_settlement_allocation"
    id = db.Column(db.Integer, primary_key=True)
    settlement_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_settlement.id"), nullable=False, index=True)
    ledger_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_ledger.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint("settlement_id", "ledger_id", name="uq_settlement_ledger_allocation"),)
    settlement = db.relationship("SellerSettlement", backref=db.backref("allocations", lazy=True, cascade="all, delete-orphan"))
    ledger = db.relationship("SellerLedger")

def _money(value: int | float) -> int:
    return max(0, int(round(value or 0)))

def ensure_settlement_allocation_guard() -> None:
    """Install the database invariant after tables exist."""
    if db.engine.dialect.name != "sqlite":
        return
    with db.engine.begin() as connection:
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS kharidino_guard_allocation_insert
            BEFORE INSERT ON kharidino_seller_settlement_allocation
            WHEN ((SELECT COALESCE(SUM(amount), 0) FROM kharidino_seller_settlement_allocation WHERE ledger_id = NEW.ledger_id) + NEW.amount)
                 > COALESCE((SELECT net FROM kharidino_seller_ledger WHERE id = NEW.ledger_id), 0)
            BEGIN SELECT RAISE(ABORT, 'settlement allocation exceeds ledger balance'); END
        """))
        connection.execute(text("""
            CREATE TRIGGER IF NOT EXISTS kharidino_guard_allocation_update
            BEFORE UPDATE OF ledger_id, amount ON kharidino_seller_settlement_allocation
            WHEN ((SELECT COALESCE(SUM(amount), 0) FROM kharidino_seller_settlement_allocation WHERE ledger_id = NEW.ledger_id AND id <> OLD.id) + NEW.amount)
                 > COALESCE((SELECT net FROM kharidino_seller_ledger WHERE id = NEW.ledger_id), 0)
            BEGIN SELECT RAISE(ABORT, 'settlement allocation exceeds ledger balance'); END
        """))

def _date_range():
    end_raw = request.args.get("to", "").strip(); start_raw = request.args.get("from", "").strip()
    today = datetime.utcnow().date(); end = today; start = today - timedelta(days=29)
    for raw, attr in ((start_raw, "start"), (end_raw, "end")):
        if not raw: continue
        try: parsed = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError: continue
        if attr == "start": start = parsed
        else: end = parsed
    if start > end: start, end = end, start
    return start, end

def _ledger_allocated(ledger_id: int) -> int:
    return _money(db.session.query(db.func.coalesce(db.func.sum(SellerSettlementAllocation.amount), 0)).filter_by(ledger_id=ledger_id).scalar())

def _seller_available_balance(store_id: int) -> int:
    rows = SellerLedger.query.filter_by(store_id=store_id).filter(SellerLedger.status == "available").all()
    return sum(max(0, _money(row.net) - _ledger_allocated(row.id)) for row in rows)

def _reserve_settlement_amount(settlement: SellerSettlement, amount: int) -> None:
    remaining = amount
    rows = SellerLedger.query.filter_by(store_id=settlement.store_id).filter(SellerLedger.status == "available", SellerLedger.net > 0).order_by(SellerLedger.id.asc()).all()
    for ledger in rows:
        if remaining <= 0: break
        free = max(0, _money(ledger.net) - _ledger_allocated(ledger.id))
        if free <= 0: continue
        take = min(remaining, free)
        db.session.add(SellerSettlementAllocation(settlement_id=settlement.id, ledger_id=ledger.id, amount=take))
        remaining -= take
    if remaining: raise ValueError("مبلغ درخواستی از مانده قابل تسویه بیشتر است.")

def _ledger_totals(ledger):
    gross = sum(_money(x.gross) for x in ledger); fee = sum(_money(x.platform_fee) for x in ledger); net = sum(_money(x.net) for x in ledger)
    available = sum(max(0, _money(x.net) - _ledger_allocated(x.id)) for x in ledger if x.status == "available")
    paid = sum(_money(x.net) for x in ledger if x.status == "paid"); cancelled = sum(_money(x.gross) for x in ledger if x.status == "cancelled")
    return {"gross": gross, "fee": fee, "net": net, "available": available, "paid": paid, "cancelled": cancelled}

def _platform_data(start, end):
    since = datetime.combine(start, datetime.min.time()); until = datetime.combine(end + timedelta(days=1), datetime.min.time())
    ledgers = SellerLedger.query.filter(SellerLedger.created_at >= since, SellerLedger.created_at < until).order_by(SellerLedger.created_at.desc()).all()
    expenses = AccountingExpense.query.filter(AccountingExpense.created_at >= since, AccountingExpense.created_at < until).order_by(AccountingExpense.created_at.desc()).all()
    settlements = SellerSettlement.query.filter(SellerSettlement.created_at >= since, SellerSettlement.created_at < until).order_by(SellerSettlement.created_at.desc()).all()
    totals = _ledger_totals(ledgers); expense_total = sum(_money(x.amount) for x in expenses)
    pending = sum(_money(x.amount) for x in settlements if x.status == "requested"); completed = sum(_money(x.amount) for x in settlements if x.status == "paid")
    return {"ledgers": ledgers, "expenses": expenses, "settlements": settlements, "totals": totals, "expense_total": expense_total, "pending_settlements": pending, "completed_settlements": completed, "platform_profit": totals["fee"] - expense_total}

@app.get("/admin/accounting")
@admin_required
def admin_accounting():
    start, end = _date_range(); data = _platform_data(start, end); seller_rows = []
    for store in Store.query.order_by(Store.name.asc()).all():
        rows = SellerLedger.query.filter_by(store_id=store.id).order_by(SellerLedger.id.desc()).limit(500).all(); totals = _ledger_totals(rows)
        if totals["gross"] or totals["net"]: seller_rows.append({"store": store, **totals})
    return render_template("accounting_dashboard.html", mode="platform", start=start.isoformat(), end=end.isoformat(), seller_rows=seller_rows, **data)

@app.get("/seller/accounting")
@seller_required
def seller_accounting():
    account = _seller_account(); start, end = _date_range(); since = datetime.combine(start, datetime.min.time()); until = datetime.combine(end + timedelta(days=1), datetime.min.time())
    rows = SellerLedger.query.filter(SellerLedger.store_id == account.store_id, SellerLedger.created_at >= since, SellerLedger.created_at < until).order_by(SellerLedger.created_at.desc()).all(); totals = _ledger_totals(rows)
    settlements = SellerSettlement.query.filter_by(store_id=account.store_id).order_by(SellerSettlement.id.desc()).all(); requested = sum(_money(x.amount) for x in settlements if x.status == "requested"); paid = sum(_money(x.amount) for x in settlements if x.status == "paid")
    return render_template("accounting_dashboard.html", mode="seller", account=account, start=start.isoformat(), end=end.isoformat(), ledgers=rows, totals=totals, settlements=settlements, withdrawable=totals["available"], requested_settlements=requested, paid_settlements=paid, seller_rows=[], expenses=[], expense_total=0, pending_settlements=requested, completed_settlements=paid, platform_profit=0)

@app.post("/seller/accounting/settlement")
@seller_required
def seller_request_settlement():
    account = _seller_account()
    try: amount = int(request.form.get("amount", "0"))
    except (TypeError, ValueError): abort(400, description="مبلغ تسویه نامعتبر است.")
    if amount <= 0: abort(400, description="مبلغ تسویه باید بیشتر از صفر باشد.")
    if amount > _seller_available_balance(account.store_id): abort(409, description="مبلغ درخواستی از مانده قابل تسویه بیشتر است.")
    settlement = SellerSettlement(store_id=account.store_id, amount=amount, note=request.form.get("note", "").strip()[:1000], requested_by=session.get("user_id"), status="requested")
    db.session.add(settlement); db.session.flush()
    try:
        _reserve_settlement_amount(settlement, amount); db.session.commit()
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        abort(409, description=str(exc) if isinstance(exc, ValueError) else "این مانده همزمان برای تسویه دیگری رزرو شده است.")
    flash("درخواست تسویه با موفقیت ثبت شد. مبلغ برای این درخواست رزرو شد. ✅", "success"); return redirect(url_for("seller_accounting"))

@app.post("/admin/accounting/expense")
@admin_required
def admin_add_expense():
    try: amount = int(request.form.get("amount", "0"))
    except (TypeError, ValueError): abort(400, description="مبلغ هزینه نامعتبر است.")
    title = request.form.get("title", "").strip()[:200]
    if amount <= 0 or not title: abort(400, description="عنوان و مبلغ هزینه الزامی است.")
    db.session.add(AccountingExpense(title=title, category=request.form.get("category", "سایر").strip()[:80] or "سایر", amount=amount, description=request.form.get("description", "").strip()[:2000], created_by=session.get("user_id"))); db.session.commit(); flash("هزینه در دفتر حسابداری ثبت شد. ✅", "success"); return redirect(url_for("admin_accounting"))

@app.post("/admin/accounting/settlements/<int:settlement_id>/pay")
@admin_required
def admin_pay_settlement(settlement_id):
    settlement = SellerSettlement.query.get_or_404(settlement_id)
    if settlement.status != "requested": abort(409, description="این درخواست قبلاً پردازش شده است.")
    allocations = SellerSettlementAllocation.query.filter_by(settlement_id=settlement.id).all(); allocated_total = sum(_money(x.amount) for x in allocations)
    if allocated_total != _money(settlement.amount): abort(409, description="رزرو مالی این تسویه ناقص یا نامعتبر است.")
    for allocation in allocations:
        ledger = SellerLedger.query.get(allocation.ledger_id)
        if not ledger or ledger.store_id != settlement.store_id or ledger.status in {"cancelled", "paid"}: abort(409, description="یکی از اقلام مالی این تسویه دیگر قابل پرداخت نیست.")
        if _ledger_allocated(ledger.id) < allocation.amount: abort(409, description="رزرو مالی این تسویه معتبر نیست.")
    settlement.status = "paid"; settlement.processed_by = session.get("user_id"); settlement.processed_at = datetime.utcnow()
    for allocation in allocations:
        ledger = SellerLedger.query.get(allocation.ledger_id)
        if ledger and _ledger_allocated(ledger.id) >= _money(ledger.net): ledger.status = "paid"; ledger.paid_at = datetime.utcnow()
    db.session.commit(); flash("تسویه فروشنده با موفقیت پرداخت شد و مبلغ از مانده قابل تسویه خارج شد. 💳", "success"); return redirect(url_for("admin_accounting"))

@app.get("/admin/accounting/export.csv")
@admin_required
def admin_accounting_export():
    start, end = _date_range(); data = _platform_data(start, end); output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["date", "store_id", "gross", "platform_fee", "seller_net", "status"])
    for ledger in data["ledgers"]: writer.writerow([ledger.created_at.isoformat() if ledger.created_at else "", ledger.store_id, ledger.gross, ledger.platform_fee, ledger.net, ledger.status])
    writer.writerow([]); writer.writerow(["EXPENSE", "", "", "", "", ""])
    for expense in data["expenses"]: writer.writerow([expense.created_at.isoformat() if expense.created_at else "", "", expense.title, expense.amount, expense.category, "expense"])
    return Response(output.getvalue().encode("utf-8-sig"), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=kharidino-accounting-{start}-{end}.csv"})
