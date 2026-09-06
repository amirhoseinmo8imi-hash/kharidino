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
def inject_seller_approval_button(response):
    """Make the dedicated approval area impossible to miss from the main admin UI."""
    if request.path.rstrip("/") != "/admin" or not response.content_type or "text/html" not in response.content_type:
        return response

    try:
        body = response.get_data(as_text=True)
        marker = "</body>"
        if marker not in body or "kharidino-seller-approval-entry" in body:
            return response

        pending_count = MerchantStore.query.filter_by(status="pending").count()
        badge = f"<span class='ksa-badge'>{pending_count}</span>" if pending_count else ""
        entry = """
<div id="kharidino-seller-approval-entry" dir="rtl">
  <a href="/admin/merchant-requests" class="ksa-link" aria-label="تأیید فروشندگان">
    <span class="ksa-icon">✓</span>
    <span class="ksa-text"><strong>تأیید فروشندگان</strong><small>بررسی درخواست‌های فروشندگی</small></span>
    {badge}
  </a>
</div>
<style>
#kharidino-seller-approval-entry{position:fixed;right:24px;bottom:24px;z-index:99999;font-family:inherit}
#kharidino-seller-approval-entry .ksa-link{display:flex;align-items:center;gap:12px;min-width:270px;padding:14px 17px;border-radius:18px;background:#111827;color:#fff;text-decoration:none;box-shadow:0 14px 40px rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.12);transition:.2s ease}
#kharidino-seller-approval-entry .ksa-link:hover{transform:translateY(-2px);box-shadow:0 18px 48px rgba(0,0,0,.28)}
#kharidino-seller-approval-entry .ksa-icon{width:40px;height:40px;border-radius:13px;display:grid;place-items:center;background:#16a34a;color:#fff;font-size:22px;font-weight:900}
#kharidino-seller-approval-entry .ksa-text{display:flex;flex-direction:column;gap:3px;flex:1}
#kharidino-seller-approval-entry .ksa-text strong{font-size:15px}
#kharidino-seller-approval-entry .ksa-text small{font-size:11px;color:#cbd5e1}
#kharidino-seller-approval-entry .ksa-badge{min-width:27px;height:27px;padding:0 7px;border-radius:99px;display:grid;place-items:center;background:#ef4444;color:#fff;font-size:12px;font-weight:900}
@media(max-width:700px){#kharidino-seller-approval-entry{right:12px;bottom:12px;left:12px}#kharidino-seller-approval-entry .ksa-link{min-width:0;width:100%}}
</style>
""".format(badge=badge)
        response.set_data(body.replace(marker, entry + marker))
        return response
    except Exception:
        return response
