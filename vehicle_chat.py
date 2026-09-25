"""
Kharidino vehicle chat + contact verification.

The verification records live in separate tables so existing User rows and
SQLite databases remain compatible with db.create_all().
"""

import os
import secrets
import smtplib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, flash, abort, session, jsonify


def register_vehicle_chat(app, db, User, login_required):
    class UserVerification(db.Model):
        __tablename__ = "user_verification"

        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
        phone = db.Column(db.String(30), default="")
        phone_verified = db.Column(db.Boolean, default=False, nullable=False)
        email_verified = db.Column(db.Boolean, default=False, nullable=False)
        phone_code_hash = db.Column(db.String(300), default="")
        email_code_hash = db.Column(db.String(300), default="")
        phone_code_expires_at = db.Column(db.DateTime, nullable=True)
        email_code_expires_at = db.Column(db.DateTime, nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(
            db.DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )

        user = db.relationship("User", backref=db.backref("verification", uselist=False))

    class VehicleChat(db.Model):
        __tablename__ = "vehicle_chat"

        id = db.Column(db.Integer, primary_key=True)
        vehicle_ad_id = db.Column(db.Integer, db.ForeignKey("vehicle_ad.id"), nullable=False)
        buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

        __table_args__ = (
            db.UniqueConstraint(
                "vehicle_ad_id",
                "buyer_id",
                "seller_id",
                name="unique_vehicle_chat",
            ),
        )

    class VehicleChatMessage(db.Model):
        __tablename__ = "vehicle_chat_message"

        id = db.Column(db.Integer, primary_key=True)
        chat_id = db.Column(db.Integer, db.ForeignKey("vehicle_chat.id"), nullable=False)
        sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        body = db.Column(db.Text, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        read_at = db.Column(db.DateTime, nullable=True)

        chat = db.relationship(
            "VehicleChat",
            backref=db.backref(
                "messages",
                lazy=True,
                cascade="all, delete-orphan",
                order_by="VehicleChatMessage.created_at.asc()",
            ),
        )
        sender = db.relationship("User")

    app.jinja_env.globals["vehicle_user_verified"] = (
        lambda user: _is_verified(db, UserVerification, user)
    )

    def verification_for(user_id):
        row = UserVerification.query.filter_by(user_id=user_id).first()
        if not row:
            row = UserVerification(user_id=user_id)
            db.session.add(row)
            db.session.commit()
        return row

    def current_verification():
        user_id = session.get("user_id")
        if not user_id:
            return None
        return verification_for(user_id)

    def hash_code(code):
        from werkzeug.security import generate_password_hash
        return generate_password_hash(str(code))

    def check_code(stored, code):
        from werkzeug.security import check_password_hash
        return bool(stored and code and check_password_hash(stored, str(code)))

    def send_email(to_email, code):
        host = os.environ.get("KHARIDINO_SMTP_HOST", "").strip()
        user = os.environ.get("KHARIDINO_SMTP_USER", "").strip()
        password = os.environ.get("KHARIDINO_SMTP_PASSWORD", "")
        if not host or not user or not password or not to_email:
            return False
        port = int(os.environ.get("KHARIDINO_SMTP_PORT", "587"))
        sender = os.environ.get("KHARIDINO_SMTP_FROM", user).strip()
        use_ssl = os.environ.get("KHARIDINO_SMTP_SSL", "0").lower() in {"1", "true", "yes"}
        subject = "کد تأیید حساب خریدینو"
        body = f"کد تأیید ایمیل خریدینو: {code}\nاین کد 10 دقیقه اعتبار دارد."
        try:
            msg = __import__("email.message", fromlist=["EmailMessage"]).EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email
            msg.set_content(body)
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                    server.login(user, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(user, password)
                    server.send_message(msg)
            return True
        except Exception:
            app.logger.exception("Vehicle verification email failed")
            return False

    def send_sms(phone, code):
        # Kavenegar-compatible configuration for Iranian phone verification.
        api_key = os.environ.get("KHARIDINO_KAVENEGAR_API_KEY", "").strip()
        sender = os.environ.get("KHARIDINO_KAVENEGAR_SENDER", "").strip()
        if not api_key or not sender:
            return False
        try:
            params = urllib.parse.urlencode({
                "receptor": phone,
                "sender": sender,
                "message": f"کد تأیید خریدینو: {code} - اعتبار 10 دقیقه",
            }).encode()
            url = f"https://api.kavenegar.com/v1/{urllib.parse.quote(api_key)}/sms/send.json"
            req = urllib.request.Request(url, data=params, method="POST")
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            return int(payload.get("return", {}).get("status", 0)) in {200, 201}
        except Exception:
            app.logger.exception("Vehicle verification SMS failed")
            return False

    def new_code():
        return f"{secrets.randbelow(1000000):06d}"

    def verified(user_id):
        row = UserVerification.query.filter_by(user_id=user_id).first()
        return bool(row and row.email_verified and row.phone_verified)

    def gate():
        row = current_verification()
        if not row or not row.email_verified or not row.phone_verified:
            flash("برای استفاده از چت، ابتدا ایمیل و شماره تلفن خود را در پروفایل تأیید کنید.", "warning")
            return redirect(url_for("profile", next=request.path))
        return None

    @app.context_processor
    def inject_vehicle_verification():
        user = db.session.get(User, session["user_id"]) if session.get("user_id") else None
        row = UserVerification.query.filter_by(user_id=user.id).first() if user else None
        return {
            "vehicle_verification": row,
            "vehicle_chat_enabled": bool(row and row.email_verified and row.phone_verified),
        }

    @app.get("/profile/verification")
    @login_required
    def vehicle_verification():
        row = verification_for(session["user_id"])
        return render_template("vehicle_verification.html", verification=row)

    @app.post("/profile/verification/email/send")
    @login_required
    def vehicle_email_send():
        row = verification_for(session["user_id"])
        code = new_code()
        if not send_email(db.session.get(User, session["user_id"]).email, code):
            flash("ارسال ایمیل انجام نشد. تنظیمات SMTP خریدینو را بررسی کنید.", "danger")
            return redirect(url_for("profile"))
        row.email_code_hash = hash_code(code)
        row.email_code_expires_at = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        flash("کد تأیید به ایمیل شما ارسال شد.", "success")
        return redirect(url_for("vehicle_verification"))

    @app.post("/profile/verification/email/confirm")
    @login_required
    def vehicle_email_confirm():
        row = verification_for(session["user_id"])
        code = request.form.get("code", "").strip()
        if (
            not code
            or not row.email_code_expires_at
            or row.email_code_expires_at < datetime.utcnow()
            or not check_code(row.email_code_hash, code)
        ):
            flash("کد تأیید ایمیل نامعتبر یا منقضی شده است.", "danger")
            return redirect(url_for("vehicle_verification"))
        row.email_verified = True
        row.email_code_hash = ""
        row.email_code_expires_at = None
        db.session.commit()
        flash("ایمیل شما با موفقیت تأیید شد.", "success")
        return redirect(url_for("vehicle_verification"))

    @app.post("/profile/verification/phone/send")
    @login_required
    def vehicle_phone_send():
        row = verification_for(session["user_id"])
        phone = request.form.get("phone", "").strip()
        if not phone or len(phone) < 10:
            flash("شماره تلفن معتبر وارد کنید.", "warning")
            return redirect(url_for("vehicle_verification"))
        code = new_code()
        if not send_sms(phone, code):
            flash("ارسال پیامک انجام نشد. تنظیمات سرویس پیامک خریدینو را بررسی کنید.", "danger")
            return redirect(url_for("vehicle_verification"))
        row.phone = phone
        row.phone_code_hash = hash_code(code)
        row.phone_code_expires_at = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        flash("کد تأیید پیامکی ارسال شد.", "success")
        return redirect(url_for("vehicle_verification"))

    @app.post("/profile/verification/phone/confirm")
    @login_required
    def vehicle_phone_confirm():
        row = verification_for(session["user_id"])
        code = request.form.get("code", "").strip()
        if (
            not code
            or not row.phone_code_expires_at
            or row.phone_code_expires_at < datetime.utcnow()
            or not check_code(row.phone_code_hash, code)
        ):
            flash("کد تأیید شماره تلفن نامعتبر یا منقضی شده است.", "danger")
            return redirect(url_for("vehicle_verification"))
        row.phone_verified = True
        row.phone_code_hash = ""
        row.phone_code_expires_at = None
        db.session.commit()
        flash("شماره تلفن شما با موفقیت تأیید شد.", "success")
        return redirect(url_for("vehicle_verification"))

    def get_chat(chat_id):
        chat = db.session.get(VehicleChat, chat_id)
        if not chat:
            abort(404)
        user_id = session.get("user_id")
        if user_id not in {chat.buyer_id, chat.seller_id}:
            abort(403)
        return chat

    @app.get("/vehicle/<int:ad_id>/chat")
    @login_required
    def vehicle_chat(ad_id):
        gate_result = gate()
        if gate_result:
            return gate_result
        from vehicle_marketplace import VehicleAdModel
        ad = db.session.get(VehicleAdModel, ad_id)
        if not ad or ad.status != "approved":
            abort(404)
        user_id = session["user_id"]
        if user_id == ad.user_id:
            requested_chat_id = request.args.get("chat_id", "").strip()
            try:
                requested_chat_id = int(requested_chat_id) if requested_chat_id else None
            except ValueError:
                requested_chat_id = None
            chat = db.session.get(VehicleChat, requested_chat_id) if requested_chat_id else None
            if chat and (chat.vehicle_ad_id != ad.id or chat.seller_id != user_id):
                abort(403)
            if not chat:
                chat = VehicleChat.query.filter_by(
                    vehicle_ad_id=ad.id,
                    seller_id=user_id,
                ).order_by(VehicleChat.updated_at.desc()).first()
            if not chat:
                flash("هنوز گفت‌وگویی برای این آگهی ایجاد نشده است.", "info")
                return redirect(url_for("vehicle_detail", ad_id=ad.id))
            
        else:
            chat = VehicleChat.query.filter_by(
                vehicle_ad_id=ad.id,
                buyer_id=user_id,
                seller_id=ad.user_id,
            ).first()
            if not chat:
                chat = VehicleChat(
                    vehicle_ad_id=ad.id,
                    buyer_id=user_id,
                    seller_id=ad.user_id,
                )
                db.session.add(chat)
                db.session.commit()
        messages = VehicleChatMessage.query.filter_by(chat_id=chat.id).order_by(VehicleChatMessage.created_at.asc()).all()
        for message in messages:
            if message.sender_id != user_id and message.read_at is None:
                message.read_at = datetime.utcnow()
        db.session.commit()
        return render_template("vehicle_chat.html", chat=chat, ad=ad, messages=messages)

    @app.post("/vehicle/<int:ad_id>/chat/send")
    @login_required
    def vehicle_chat_send(ad_id):
        gate_result = gate()
        if gate_result:
            return gate_result
        from vehicle_marketplace import VehicleAdModel
        ad = db.session.get(VehicleAdModel, ad_id)
        if not ad or ad.status != "approved":
            abort(404)
        user_id = session["user_id"]
        body = request.form.get("body", "").strip()
        if not body:
            flash("متن پیام نمی‌تواند خالی باشد.", "warning")
            return redirect(url_for("vehicle_chat", ad_id=ad.id))
        if len(body) > 4000:
            flash("پیام خیلی طولانی است.", "warning")
            return redirect(url_for("vehicle_chat", ad_id=ad.id))
        if user_id == ad.user_id:
            # Seller must reply inside an existing conversation.
            chat_id = request.form.get("chat_id", "").strip()
            try:
                chat = db.session.get(VehicleChat, int(chat_id))
            except (TypeError, ValueError):
                chat = None
            if not chat or chat.vehicle_ad_id != ad.id or chat.seller_id != user_id:
                abort(403)
        else:
            chat = VehicleChat.query.filter_by(
                vehicle_ad_id=ad.id,
                buyer_id=user_id,
                seller_id=ad.user_id,
            ).first()
            if not chat:
                chat = VehicleChat(
                    vehicle_ad_id=ad.id,
                    buyer_id=user_id,
                    seller_id=ad.user_id,
                )
                db.session.add(chat)
                db.session.flush()
        db.session.add(VehicleChatMessage(chat_id=chat.id, sender_id=user_id, body=body))
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("vehicle_chat", ad_id=ad.id))


    def serialize_message(message, current_user_id):
        return {
            "id": message.id,
            "body": message.body,
            "sender_id": message.sender_id,
            "mine": message.sender_id == current_user_id,
            "created_at": message.created_at.strftime("%Y/%m/%d %H:%M") if message.created_at else "",
        }

    def unread_total(user_id):
        return (
            VehicleChatMessage.query
            .join(VehicleChat, VehicleChat.id == VehicleChatMessage.chat_id)
            .filter(
                db.or_(VehicleChat.buyer_id == user_id, VehicleChat.seller_id == user_id),
                VehicleChatMessage.sender_id != user_id,
                VehicleChatMessage.read_at.is_(None),
            )
            .count()
        )

    @app.get("/api/vehicle-chats/unread")
    @login_required
    def vehicle_chat_unread_api():
        user_id = session["user_id"]
        return jsonify({"count": unread_total(user_id)})

    @app.get("/api/vehicle-chat/<int:chat_id>/messages")
    @login_required
    def vehicle_chat_messages_api(chat_id):
        user_id = session["user_id"]
        chat = db.session.get(VehicleChat, chat_id)
        if not chat:
            abort(404)
        if user_id not in {chat.buyer_id, chat.seller_id}:
            abort(403)

        try:
            after_id = max(0, int(request.args.get("after_id", "0")))
        except (TypeError, ValueError):
            after_id = 0

        query = VehicleChatMessage.query.filter(
            VehicleChatMessage.chat_id == chat.id,
            VehicleChatMessage.id > after_id,
        ).order_by(VehicleChatMessage.id.asc())
        messages = query.all()

        # Opening/polling the active conversation counts incoming messages as read.
        unread = [m for m in messages if m.sender_id != user_id and m.read_at is None]
        if unread:
            now = datetime.utcnow()
            for message in unread:
                message.read_at = now
            db.session.commit()

        return jsonify({
            "messages": [serialize_message(m, user_id) for m in messages],
            "unread_count": unread_total(user_id),
            "chat_updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        })

    @app.get("/my-chats")
    @login_required
    def my_vehicle_chats():
        user_id = session["user_id"]
        chats = VehicleChat.query.filter(
            db.or_(VehicleChat.buyer_id == user_id, VehicleChat.seller_id == user_id)
        ).order_by(VehicleChat.updated_at.desc()).all()
        return render_template("my_vehicle_chats.html", chats=chats)


def _is_verified(db, model, user):
    if not user:
        return False
    row = model.query.filter_by(user_id=user.id).first()
    return bool(row and row.email_verified and row.phone_verified)
