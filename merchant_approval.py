"""Dedicated admin workspace for approving and managing seller applications."""
from flask import abort, flash, redirect, render_template, url_for

from app import app, db, admin_required
from merchant_marketplace import MerchantStore


_STATUS_LABELS = {
    "pending": "در انتظار تأیید",
    "approved": "تأیید شده",
    "rejected": "رد شده",
    "suspended": "تعلیق شده",
}


@app.get("/admin/merchant-requests")
@admin_required
def admin_merchant_requests():
    accounts = MerchantStore.query.order_by(MerchantStore.id.desc()).all()
    counts = {
        status: sum(1 for account in accounts if account.status == status)
        for status in _STATUS_LABELS
    }
    return render_template(
        "merchant_approval.html",
        accounts=accounts,
        counts=counts,
        status_labels=_STATUS_LABELS,
    )


def _set_merchant_status(account_id: int, status: str):
    if status not in _STATUS_LABELS:
        abort(400)

    account = MerchantStore.query.get_or_404(account_id)
    account.status = status
    if account.store is not None:
        account.store.active = status == "approved"
    db.session.commit()

    messages = {
        "approved": "فروشنده با موفقیت تأیید و فروشگاه فعال شد. ✅",
        "rejected": "درخواست فروشندگی رد شد.",
        "suspended": "فروشگاه فروشنده تعلیق شد.",
        "pending": "درخواست به حالت در انتظار بازگشت.",
    }
    flash(messages[status], "success")
    return redirect(url_for("admin_merchant_requests"))


@app.post("/admin/merchant-requests/<int:account_id>/approve")
@admin_required
def admin_merchant_request_approve(account_id: int):
    return _set_merchant_status(account_id, "approved")


@app.post("/admin/merchant-requests/<int:account_id>/reject")
@admin_required
def admin_merchant_request_reject(account_id: int):
    return _set_merchant_status(account_id, "rejected")


@app.post("/admin/merchant-requests/<int:account_id>/suspend")
@admin_required
def admin_merchant_request_suspend(account_id: int):
    return _set_merchant_status(account_id, "suspended")


@app.post("/admin/merchant-requests/<int:account_id>/pending")
@admin_required
def admin_merchant_request_pending(account_id: int):
    return _set_merchant_status(account_id, "pending")
