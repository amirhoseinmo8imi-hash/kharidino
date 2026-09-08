"""Secure password reset flow for Kharidino.

Reset tokens are short-lived, signed, and single-use. SMTP delivery is optional
for local development; when SMTP is not configured, a reset link is exposed
only while FLASK_DEBUG=1.
"""
import os
import secrets
import smtplib
from email.message import EmailMessage

from flask import flash, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

from app import app, db, User, Setting

TOKEN_MAX_AGE = 1800
RESET_VERSION_PREFIX = "password_reset_version:"


def _serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="kharidino-password-reset-v2")


def _version_key(user_id):
    return f"{RESET_VERSION_PREFIX}{int(user_id)}"


def _current_version(user):
    row = Setting.query.filter_by(key=_version_key(user.id)).first()
    try:
        return int(row.value) if row else 0
    except (TypeError, ValueError):
        return 0


def _bump_version(user):
    key = _version_key(user.id)
    row = Setting.query.filter_by(key=key).first()
    if not row:
        db.session.add(Setting(key=key, value="1"))
    else:
        row.value = str(_current_version(user) + 1)


def _token_for(user):
    return _serializer().dumps({
        "uid": user.id,
        "nonce": secrets.token_urlsafe(12),
        "ver": _current_version(user),
    })


def _user_from_token(token, max_age=TOKEN_MAX_AGE):
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    try:
        user = db.session.get(User, int(data.get("uid")))
        if not user or int(data.get("ver", -1)) != _current_version(user):
            return None
        return user
    except (TypeError, ValueError):
        return None


def _send_reset_email(user, link):
    host = os.environ.get("SMTP_HOST", "").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("MAIL_FROM", username).strip()
    if not host or not sender:
        return False

    message = EmailMessage()
    message["Subject"] = "بازیابی رمز عبور حساب خریدینو"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        f"سلام {user.name or ''}\n\n"
        "برای تغییر رمز عبور حساب خریدینو روی لینک زیر کلیک کنید. "
        "این لینک فقط ۳۰ دقیقه معتبر و پس از استفاده یک‌بارمصرف است:\n"
        f"{link}\n\n"
        "اگر این درخواست توسط شما انجام نشده است، این پیام را نادیده بگیرید."
    )
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
    return True


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        token = _token_for(user) if user else None
        sent = False
        if user and token:
            link = url_for("reset_password", token=token, _external=True)
            try:
                sent = _send_reset_email(user, link)
            except Exception:
                app.logger.exception("Password reset email delivery failed")
            if not sent and app.debug:
                return render_template("forgot_password.html", dev_reset_url=link)

        flash("اگر این ایمیل در خریدینو ثبت شده باشد، لینک بازیابی رمز عبور برای شما ارسال می‌شود.", "success")
        return redirect(url_for("forgot_password"))
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _user_from_token(token)
    if not user:
        flash("لینک بازیابی نامعتبر، منقضی یا قبلاً استفاده شده است. دوباره درخواست بازیابی کنید.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("رمز عبور باید حداقل ۸ کاراکتر باشد.", "warning")
            return render_template("reset_password.html")
        if password != confirm:
            flash("تکرار رمز عبور با رمز جدید یکسان نیست.", "warning")
            return render_template("reset_password.html")

        user.password = generate_password_hash(password)
        _bump_version(user)
        db.session.commit()
        flash("رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد حساب خود شوید. ✅", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")
