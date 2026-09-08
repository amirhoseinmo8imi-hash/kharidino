"""Production-ready password recovery for Kharidino.

The recovery link is signed, short-lived and single-use. Delivery uses standard
SMTP so Kharidino can use a free mailbox such as Gmail/Outlook without a paid
SMS gateway. SMTP credentials must stay in environment variables.
"""
import os
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urljoin

from flask import flash, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import generate_password_hash

from app import app, db, User, Setting

TOKEN_MAX_AGE = 1800
RESET_VERSION_PREFIX = "password_reset_version:"


def _serializer():
    return URLSafeTimedSerializer(
        app.config["SECRET_KEY"],
        salt="kharidino-password-reset-v2",
    )


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


def _reset_link(token):
    path = url_for("reset_password", token=token)
    base_url = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if base_url:
        return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    return url_for("reset_password", token=token, _external=True)


def _send_reset_email(user, link):
    """Send a real reset email over SMTP.

    Defaults are compatible with Gmail SMTP. For Gmail, use a free Google
    account with 2-Step Verification enabled and a Google App Password.
    """
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("MAIL_FROM", username).strip()

    try:
        port = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError:
        port = 465

    use_ssl = os.environ.get("SMTP_USE_SSL", "1").strip().lower() in {
        "1", "true", "yes", "on"
    }

    if not host or not sender or not username or not password:
        app.logger.error(
            "Password reset SMTP is not configured: host=%s sender=%s username_set=%s password_set=%s",
            bool(host), bool(sender), bool(username), bool(password),
        )
        return False

    message = EmailMessage()
    message["Subject"] = "بازیابی رمز عبور حساب خریدینو"
    message["From"] = sender
    message["To"] = user.email
    message.set_content(
        f"سلام {user.name or ''}\n\n"
        "درخواست بازیابی رمز عبور حساب خریدینو ثبت شده است.\n\n"
        "برای انتخاب رمز جدید از لینک زیر استفاده کنید:\n"
        f"{link}\n\n"
        "این لینک فقط ۳۰ دقیقه معتبر است و پس از تغییر موفق رمز، دیگر قابل استفاده نیست.\n\n"
        "اگر این درخواست توسط شما انجام نشده است، این پیام را نادیده بگیرید."
    )

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)

    return True


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first() if email else None
        sent = False
        app.logger.info("Password reset requested: account_found=%s", bool(user))

        if user:
            token = _token_for(user)
            link = _reset_link(token)
            try:
                sent = _send_reset_email(user, link)
                app.logger.info("Password reset email delivery result: sent=%s", sent)
            except (OSError, smtplib.SMTPException):
                app.logger.exception("Password reset email delivery failed")
            except Exception:
                app.logger.exception("Unexpected password reset delivery failure")

            if not sent and app.debug:
                return render_template(
                    "forgot_password.html",
                    dev_reset_url=link,
                )

        # Deliberately identical for known/unknown addresses: no account
        # enumeration through the recovery endpoint.
        flash(
            "اگر این ایمیل در خریدینو ثبت شده باشد، لینک بازیابی رمز عبور برای شما ارسال می‌شود.",
            "success",
        )
        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _user_from_token(token)
    if not user:
        flash(
            "لینک بازیابی نامعتبر، منقضی یا قبلاً استفاده شده است. دوباره درخواست بازیابی کنید.",
            "danger",
        )
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
        flash(
            "رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد حساب خود شوید. ✅",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("reset_password.html")
