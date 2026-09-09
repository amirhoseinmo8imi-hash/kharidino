"""Checkout validation that must run before inventory reservation."""
from __future__ import annotations

import re

from flask import abort, request, session


_MAX_NAME_LENGTH = 120
_MAX_PHONE_LENGTH = 30
_MAX_ADDRESS_LENGTH = 2000
_MAX_NOTE_LENGTH = 2000
_PHONE_RE = re.compile(r"^[0-9۰-۹+()\-\s]{7,30}$")


def _validate_customer_fields() -> None:
    name = request.form.get("customer_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    note = request.form.get("note", "").strip()

    if not name or not phone or not address:
        abort(400, description="نام، شماره تماس و آدرس الزامی است.")

    if len(name) < 2 or len(name) > _MAX_NAME_LENGTH:
        abort(400, description="نام واردشده نامعتبر است.")

    if len(phone) > _MAX_PHONE_LENGTH or not _PHONE_RE.fullmatch(phone):
        abort(400, description="شماره تماس واردشده نامعتبر است.")

    if len(address) < 5 or len(address) > _MAX_ADDRESS_LENGTH:
        abort(400, description="آدرس واردشده نامعتبر است.")

    if len(note) > _MAX_NOTE_LENGTH:
        abort(400, description="توضیحات سفارش بیش از حد طولانی است.")


def _validate_cart_shape() -> None:
    cart = session.get("cart", {})
    if not isinstance(cart, dict) or not cart:
        abort(400, description="سبد خرید خالی یا نامعتبر است.")

    for raw_product_id, raw_quantity in cart.items():
        try:
            product_id = int(raw_product_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            abort(400, description="سبد خرید نامعتبر است.")

        if product_id <= 0 or quantity < 1 or quantity > 99:
            abort(400, description="تعداد کالا نامعتبر است.")


def apply_checkout_preflight(app) -> None:
    if getattr(app, "_kharidino_checkout_preflight", False):
        return

    @app.before_request
    def _checkout_preflight():
        if request.endpoint != "checkout" or request.method != "POST":
            return None
        if not session.get("user_id"):
            return None
        _validate_customer_fields()
        _validate_cart_shape()
        return None

    app._kharidino_checkout_preflight = True
