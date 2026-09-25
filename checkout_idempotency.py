"""Server-side idempotency guard for the checkout submit button.

The UI already disables duplicate submits, but browser retries, double clicks,
network replays, and concurrent requests must also be safe on the server.
"""
from __future__ import annotations

import secrets

from flask import abort, request, session
from sqlalchemy.exc import IntegrityError


_TOKEN_KEY = "checkout_submit_token"


def apply_checkout_idempotency(app, db) -> None:
    if getattr(app, "_kharidino_checkout_idempotency", False):
        return

    class CheckoutSubmission(db.Model):
        __tablename__ = "checkout_submission"
        id = db.Column(db.Integer, primary_key=True)
        token = db.Column(db.String(64), unique=True, nullable=False, index=True)
        user_id = db.Column(db.Integer, nullable=False, index=True)
        created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    app.extensions["kharidino_checkout_submission"] = CheckoutSubmission

    @app.before_request
    def _checkout_idempotency():
        if request.endpoint != "checkout" or not session.get("user_id"):
            return None

        if request.method == "GET":
            token = session.get(_TOKEN_KEY)
            if not isinstance(token, str) or len(token) < 32:
                session[_TOKEN_KEY] = secrets.token_urlsafe(32)
                session.modified = True
            return None

        if request.method != "POST":
            return None

        token = session.get(_TOKEN_KEY)
        if not isinstance(token, str) or len(token) < 32:
            # Direct POSTs without first loading checkout are rejected instead
            # of silently allowing an unprotected order creation.
            abort(409, description="فرم ثبت سفارش منقضی شده است؛ دوباره صفحه پرداخت را باز کنید.")

        claim = CheckoutSubmission(token=token, user_id=int(session["user_id"]))
        db.session.add(claim)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            abort(409, description="این ثبت سفارش قبلاً ارسال شده است؛ از ایجاد سفارش تکراری جلوگیری شد.")

        # Consume the browser token before the order is created. A concurrent
        # request carrying the same cookie is still rejected by the unique DB key.
        session.pop(_TOKEN_KEY, None)
        session.modified = True
        return None

    app._kharidino_checkout_idempotency = True
