"""Auditable reconciliation workflow for seller clawback debts.

Refunds that happen after a seller payout create SellerClawback debt records.
This module gives administrators an explicit, idempotent way to reconcile
those debts without silently mutating a paid settlement.
"""
from __future__ import annotations

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import event
from sqlalchemy.orm import Session


def _money(value) -> int:
    return max(0, int(round(value or 0)))


def apply_clawback_reconciliation(app, db, Store):
    if getattr(app, "_kharidino_clawback_reconciliation", False):
        return

    SellerClawback = app.extensions.get("kharidino_seller_clawback")
    if SellerClawback is None:
        return

    class SellerClawbackResolution(db.Model):
        __tablename__ = "kharidino_seller_clawback_resolution"
        id = db.Column(db.Integer, primary_key=True)
        clawback_id = db.Column(db.Integer, db.ForeignKey("kharidino_seller_clawback.id"), nullable=False, index=True)
        amount = db.Column(db.Integer, nullable=False)
        reference = db.Column(db.String(180), nullable=False, unique=True, index=True)
        note = db.Column(db.String(1000), nullable=False, default="")
        processed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
        clawback = db.relationship("SellerClawback", backref=db.backref("resolutions", lazy=True, cascade="all, delete-orphan"))

    app.extensions["kharidino_seller_clawback_resolution"] = SellerClawbackResolution

    def _resolved_total(clawback):
        return sum(_money(x.amount) for x in list(getattr(clawback, "resolutions", []) or []))

    def _refresh_status(clawback):
        resolved = _resolved_total(clawback)
        target = _money(clawback.amount)
        if resolved >= target and target > 0:
            clawback.status = "settled"
            clawback.settled_at = clawback.settled_at or datetime.utcnow()
        elif resolved > 0:
            clawback.status = "partial"
            clawback.settled_at = None
        else:
            clawback.status = "open"
            clawback.settled_at = None

    @event.listens_for(Session, "before_flush")
    def _validate_clawback_resolution(session_obj, flush_context, instances):
        pending_resolutions = session_obj.info.setdefault("kharidino_pending_clawback_resolutions", [])
        for resolution in list(session_obj.new):
            if not isinstance(resolution, SellerClawbackResolution):
                continue
            if resolution not in pending_resolutions:
                pending_resolutions.append(resolution)
            amount = _money(resolution.amount)
            if amount <= 0:
                raise ValueError("مبلغ وصول بدهی باید بیشتر از صفر باشد.")
            resolution.amount = amount
            clawback = session_obj.get(SellerClawback, resolution.clawback_id)
            if not clawback:
                raise ValueError("بدهی فروشنده پیدا نشد.")
            already = sum(
                _money(x.amount)
                for x in session_obj.query(SellerClawbackResolution)
                .filter(SellerClawbackResolution.clawback_id == clawback.id)
                .all()
                if x.id != resolution.id
            )
            pending_amount = sum(
                _money(x.amount)
                for x in pending_resolutions
                if x is not resolution and x.clawback_id == clawback.id
            )
            if already + pending_amount + amount > _money(clawback.amount):
                raise ValueError("مبلغ وصول از بدهی باقی‌مانده بیشتر است.")

    @event.listens_for(Session, "after_flush_postexec")
    def _refresh_clawback_status(session_obj, flush_context):
        if session_obj.info.get("kharidino_clawback_status_running"):
            return
        pending_resolutions = session_obj.info.pop("kharidino_pending_clawback_resolutions", [])
        if not pending_resolutions:
            return
        session_obj.info["kharidino_clawback_status_running"] = True
        try:
            clawback_ids = {
                int(x.clawback_id)
                for x in pending_resolutions
                if x.id is not None
            }
            for clawback_id in clawback_ids:
                clawback = session_obj.get(SellerClawback, clawback_id)
                if clawback:
                    _refresh_status(clawback)
        finally:
            session_obj.info["kharidino_clawback_status_running"] = False

    @app.get("/admin/accounting/clawbacks")
    def admin_clawbacks():
        user_id = session.get("user_id")
        if not user_id:
            abort(401)
        user = db.session.get(__import__("app").User, user_id)
        if not user or user.role != "admin":
            abort(403)
        rows = SellerClawback.query.order_by(SellerClawback.id.desc()).all()
        items = []
        for clawback in rows:
            resolved = _resolved_total(clawback)
            items.append({
                "clawback": clawback,
                "resolved": resolved,
                "remaining": max(0, _money(clawback.amount) - resolved),
            })
        return render_template("clawbacks_dashboard.html", items=items)

    @app.post("/admin/accounting/clawbacks/<int:clawback_id>/resolve")
    def admin_resolve_clawback(clawback_id):
        user_id = session.get("user_id")
        if not user_id:
            abort(401)
        user = db.session.get(__import__("app").User, user_id)
        if not user or user.role != "admin":
            abort(403)
        clawback = SellerClawback.query.get_or_404(clawback_id)
        try:
            amount = int(request.form.get("amount", "0"))
        except (TypeError, ValueError):
            abort(400, description="مبلغ وصول نامعتبر است.")
        amount = _money(amount)
        remaining = max(0, _money(clawback.amount) - _resolved_total(clawback))
        if amount <= 0 or amount > remaining:
            abort(409, description="مبلغ وصول از بدهی باقی‌مانده بیشتر است یا نامعتبر است.")
        reference = request.form.get("reference", "").strip()[:180]
        if not reference:
            abort(400, description="شماره مرجع وصول الزامی است.")
        if SellerClawbackResolution.query.filter_by(reference=reference).first():
            return redirect(url_for("admin_clawbacks"))
        db.session.add(SellerClawbackResolution(
            clawback_id=clawback.id,
            amount=amount,
            reference=reference,
            note=request.form.get("note", "").strip()[:1000],
            processed_by=user.id,
        ))
        try:
            db.session.flush()
            _refresh_status(clawback)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            abort(409, description=str(exc))
        flash("وصول بدهی فروشنده در دفتر تسویه ثبت شد. ✅", "success")
        return redirect(url_for("admin_clawbacks"))

    app._kharidino_clawback_reconciliation = True
