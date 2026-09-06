"""Dedicated admin workspace for approving and managing seller applications."""
from flask import abort, flash, redirect, render_template, url_for, request

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


@app.after_request
def inject_seller_approval_into_admin_sidebar(response):
    """Add seller approval as a real item inside the main admin sidebar."""
    if request.path.rstrip("/") != "/admin" or not response.content_type or "text/html" not in response.content_type:
        return response

    try:
        body = response.get_data(as_text=True)
        marker = "</nav>"
        entry_id = "kharidino-seller-approval-nav-entry"
        if marker not in body or entry_id in body:
            return response

        pending_count = MerchantStore.query.filter_by(status="pending").count()
        badge = (
            f"<span class='ksa-nav-badge'>{pending_count}</span>"
            if pending_count
            else ""
        )
        entry = """
<a id="kharidino-seller-approval-nav-entry" href="/admin/merchant-requests" class="kharidino-seller-approval-nav" aria-label="تأیید فروشندگان">
    <i class="fa-solid fa-user-check"></i>
    <span>تأیید فروشندگان</span>
    {badge}
</a>
<style>
.kharidino-seller-approval-nav{position:relative}
.kharidino-seller-approval-nav .ksa-nav-badge{margin-right:auto;min-width:24px;height:24px;padding:0 7px;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;background:#ef4444;color:#fff;font-size:11px;font-weight:800;line-height:1}
.kharidino-seller-approval-nav:hover{transform:translateX(-2px)}
</style>
""".format(badge=badge)
        response.set_data(body.replace(marker, entry + marker, 1))
        return response
    except Exception:
        return response
