"""Seller staff authorization and management APIs.

Staff membership is scoped to exactly one Store. The seller account owner remains
implicitly authorized; staff never inherit admin privileges and can only act within
their assigned store.
"""
from functools import wraps

from flask import jsonify, request, session

from app import app, db, User
from marketplace_ultimate import SellerStaff
from merchant_marketplace import MerchantStore, _seller_account


ROLE_PERMISSIONS = {
    "owner": {"all"},
    "manager": {"catalog", "orders", "shipping", "support", "reports", "staff"},
    "catalog": {"catalog"},
    "orders": {"orders", "shipping"},
    "finance": {"reports"},
    "support": {"support"},
    "operator": {"orders", "shipping", "support"},
}
VALID_ROLES = set(ROLE_PERMISSIONS) - {"owner"}


def _current_membership():
    uid = session.get("user_id")
    if not uid:
        return None, None

    # Store owners are the MerchantStore owner and implicitly have full access.
    owner_account = _seller_account(uid)
    if owner_account:
        if owner_account.status != "approved" or not owner_account.store.active:
            return None, None
        return owner_account, {"all"}

    # Staff users do not need role="seller"; membership itself grants scoped access.
    staff = SellerStaff.query.filter_by(user_id=uid, active=True).first()
    if not staff:
        return None, None
    account = MerchantStore.query.filter_by(store_id=staff.store_id).first()
    if not account or account.status != "approved" or not account.store.active:
        return None, None
    return account, ROLE_PERMISSIONS.get(staff.role, set())


def seller_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            account, permissions = _current_membership()
            if not account:
                return jsonify({"ok": False, "error": "seller_access_denied"}), 403
            if "all" not in permissions and permission not in permissions:
                return jsonify({"ok": False, "error": "permission_denied"}), 403
            return view(account, *args, **kwargs)
        return wrapped
    return decorator


def _staff_payload(row):
    return {
        "id": row.id,
        "store_id": row.store_id,
        "user_id": row.user_id,
        "name": row.user.name if row.user else "",
        "email": row.user.email if row.user else "",
        "role": row.role,
        "active": bool(row.active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def apply_seller_staff(app_obj=None):
    app_obj = app_obj or app
    if app_obj.extensions.get("kharidino_seller_staff"):
        return

    @app_obj.get("/api/seller/staff")
    @seller_permission("staff")
    def seller_staff_list(account):
        rows = SellerStaff.query.filter_by(store_id=account.store_id).order_by(SellerStaff.id.asc()).all()
        return jsonify({"ok": True, "items": [_staff_payload(row) for row in rows]})

    @app_obj.post("/api/seller/staff")
    @seller_permission("staff")
    def seller_staff_add(account):
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        role = str(data.get("role", "operator")).strip().lower()
        if not email or role not in VALID_ROLES:
            return jsonify({"ok": False, "error": "invalid_staff_payload"}), 400
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({"ok": False, "error": "user_not_found"}), 404
        if user.id == account.user_id:
            return jsonify({"ok": False, "error": "owner_cannot_be_staff"}), 409
        existing = SellerStaff.query.filter_by(store_id=account.store_id, user_id=user.id).first()
        if existing:
            if existing.active:
                return jsonify({"ok": False, "error": "staff_already_exists"}), 409
            existing.role = role
            existing.active = True
            db.session.commit()
            return jsonify({"ok": True, "item": _staff_payload(existing)})
        row = SellerStaff(store_id=account.store_id, user_id=user.id, role=role, active=True)
        db.session.add(row)
        db.session.commit()
        return jsonify({"ok": True, "item": _staff_payload(row)}), 201

    @app_obj.patch("/api/seller/staff/<int:staff_id>")
    @seller_permission("staff")
    def seller_staff_update(account, staff_id):
        row = SellerStaff.query.filter_by(id=staff_id, store_id=account.store_id).first()
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        data = request.get_json(silent=True) or {}
        if "role" in data:
            role = str(data.get("role", "")).strip().lower()
            if role not in VALID_ROLES:
                return jsonify({"ok": False, "error": "invalid_role"}), 400
            row.role = role
        if "active" in data:
            row.active = bool(data.get("active"))
        db.session.commit()
        return jsonify({"ok": True, "item": _staff_payload(row)})

    @app_obj.delete("/api/seller/staff/<int:staff_id>")
    @seller_permission("staff")
    def seller_staff_remove(account, staff_id):
        row = SellerStaff.query.filter_by(id=staff_id, store_id=account.store_id).first()
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        # Soft revoke preserves the audit trail and unique membership constraint.
        row.active = False
        db.session.commit()
        return jsonify({"ok": True, "revoked": True})

    app_obj.extensions["kharidino_seller_staff"] = True
