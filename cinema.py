"""Kharidino Cinema module: moderated catalog, playback progress and in-person reservations."""
from __future__ import annotations
import os, secrets
from datetime import datetime
from pathlib import Path
from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

VIDEO_SIGNATURES = {
    "mp4": lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
    "webm": lambda data: data.startswith(bytes.fromhex("1a45dfa3")),
}
MAX_VIDEO_BYTES = 100 * 1024 * 1024

def register_cinema(app, db, User, login_required, admin_required):
    if app.extensions.get("kharidino_cinema_registered"):
        return app.extensions["kharidino_cinema_models"]
    class CinemaTitle(db.Model):
        __tablename__ = "cinema_title"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(180), nullable=False, index=True)
        synopsis = db.Column(db.Text, nullable=False, default="")
        genre = db.Column(db.String(80), nullable=False, default="")
        release_year = db.Column(db.Integer)
        poster_url = db.Column(db.String(700), nullable=False, default="")
        video_path = db.Column(db.String(500), nullable=False, default="")
        status = db.Column(db.String(20), nullable=False, default="pending", index=True)
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    class CinemaProgress(db.Model):
        __tablename__ = "cinema_progress"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
        title_id = db.Column(db.Integer, db.ForeignKey("cinema_title.id", ondelete="CASCADE"), nullable=False)
        seconds = db.Column(db.Integer, nullable=False, default=0)
        updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        __table_args__ = (db.UniqueConstraint("user_id", "title_id", name="uq_cinema_progress_user_title"),)
    class CinemaShowtime(db.Model):
        __tablename__ = "cinema_showtime"
        id = db.Column(db.Integer, primary_key=True)
        title_id = db.Column(db.Integer, db.ForeignKey("cinema_title.id", ondelete="CASCADE"), nullable=False, index=True)
        venue = db.Column(db.String(180), nullable=False)
        starts_at = db.Column(db.DateTime, nullable=False, index=True)
        ticket_price = db.Column(db.Integer, nullable=False, default=0)
        capacity = db.Column(db.Integer, nullable=False)
        available_seats = db.Column(db.Integer, nullable=False)
        title = db.relationship(CinemaTitle, backref=db.backref("showtimes", lazy=True, cascade="all, delete-orphan"))
    class CinemaBooking(db.Model):
        __tablename__ = "cinema_booking"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
        showtime_id = db.Column(db.Integer, db.ForeignKey("cinema_showtime.id", ondelete="CASCADE"), nullable=False, index=True)
        ticket_count = db.Column(db.Integer, nullable=False)
        booking_code = db.Column(db.String(40), nullable=False, unique=True, index=True)
        status = db.Column(db.String(20), nullable=False, default="reserved")
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        showtime = db.relationship(CinemaShowtime, backref=db.backref("bookings", lazy=True))
    models = {"title": CinemaTitle, "progress": CinemaProgress, "showtime": CinemaShowtime, "booking": CinemaBooking}
    app.extensions["kharidino_cinema_registered"] = True
    app.extensions["kharidino_cinema_models"] = models
    upload_dir = Path(app.static_folder or "static") / "uploads" / "cinema"
    upload_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/cinema", endpoint="cinema_home")
    def cinema_home():
        titles = CinemaTitle.query.filter_by(status="published").order_by(CinemaTitle.created_at.desc()).all()
        slots = CinemaShowtime.query.join(CinemaTitle).filter(CinemaTitle.status == "published", CinemaShowtime.starts_at >= datetime.utcnow(), CinemaShowtime.available_seats > 0).order_by(CinemaShowtime.starts_at.asc()).limit(30).all()
        pending_titles = []
        if session.get("user_id"):
            viewer = db.session.get(User, session["user_id"])
            if viewer and viewer.role == "admin":
                pending_titles = CinemaTitle.query.filter_by(status="pending").order_by(CinemaTitle.created_at.asc()).limit(50).all()
        return render_template("cinema/index.html", titles=titles, showtimes=slots, pending_titles=pending_titles)

    @app.get("/cinema/title/<int:title_id>", endpoint="cinema_title")
    def cinema_title(title_id):
        title = db.session.get(CinemaTitle, title_id)
        if not title or title.status != "published": abort(404)
        progress = CinemaProgress.query.filter_by(user_id=session["user_id"], title_id=title.id).first() if session.get("user_id") else None
        slots = CinemaShowtime.query.filter(CinemaShowtime.title_id == title.id, CinemaShowtime.starts_at >= datetime.utcnow(), CinemaShowtime.available_seats > 0).order_by(CinemaShowtime.starts_at.asc()).all()
        return render_template("cinema/title.html", title=title, progress=progress, showtimes=slots)

    @app.post("/cinema/title/<int:title_id>/progress", endpoint="cinema_progress")
    @login_required
    def cinema_progress(title_id):
        title = db.session.get(CinemaTitle, title_id)
        if not title or title.status != "published": abort(404)
        raw = request.form.get("seconds")
        if raw is None: raw = (request.get_json(silent=True) or {}).get("seconds", 0)
        try: seconds = max(0, min(int(raw), 86400))
        except (TypeError, ValueError): abort(400)
        row = CinemaProgress.query.filter_by(user_id=session["user_id"], title_id=title.id).first()
        if row is None:
            row = CinemaProgress(user_id=session["user_id"], title_id=title.id)
            db.session.add(row)
        row.seconds = seconds
        row.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "seconds": row.seconds}) if request.is_json else redirect(url_for("cinema_title", title_id=title.id))

    @app.post("/cinema/showtime/<int:showtime_id>/book", endpoint="cinema_book")
    @login_required
    def cinema_book(showtime_id):
        slot = db.session.get(CinemaShowtime, showtime_id)
        if not slot or slot.title.status != "published" or slot.starts_at <= datetime.utcnow(): abort(404)
        count = request.form.get("ticket_count", 1, type=int)
        if count is None or not 1 <= count <= 8: abort(400)
        changed = CinemaShowtime.query.filter(CinemaShowtime.id == slot.id, CinemaShowtime.available_seats >= count).update({CinemaShowtime.available_seats: CinemaShowtime.available_seats - count}, synchronize_session=False)
        if changed != 1:
            db.session.rollback()
            flash("ظرفیت این سانس کافی نیست.", "warning")
            return redirect(url_for("cinema_title", title_id=slot.title_id))
        booking = CinemaBooking(user_id=session["user_id"], showtime_id=slot.id, ticket_count=count, booking_code=secrets.token_hex(10).upper())
        db.session.add(booking)
        db.session.commit()
        return render_template("cinema/ticket.html", booking=booking)

    @app.post("/admin/cinema/title", endpoint="cinema_admin_create")
    @admin_required
    def cinema_admin_create():
        title_text = (request.form.get("title") or "").strip()
        synopsis = (request.form.get("synopsis") or "").strip()
        if not title_text or len(title_text) > 180 or len(synopsis) > 5000: abort(400)
        upload = request.files.get("video")
        video_path = ""
        if upload and upload.filename:
            filename = secure_filename(upload.filename)
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            checker = VIDEO_SIGNATURES.get(ext)
            upload.stream.seek(0, os.SEEK_END)
            size = upload.stream.tell()
            upload.stream.seek(0)
            signature = upload.stream.read(16)
            upload.stream.seek(0)
            if not checker or size <= 0 or size > MAX_VIDEO_BYTES or not checker(signature): abort(400, description="فقط فایل معتبر MP4/WebM تا ۱۰۰ مگابایت پذیرفته می‌شود.")
            stored = secrets.token_hex(20) + "." + ext
            upload.save(upload_dir / stored)
            video_path = "uploads/cinema/" + stored
        year = request.form.get("release_year", type=int)
        if year is not None and not 1888 <= year <= datetime.utcnow().year + 2: abort(400)
        item = CinemaTitle(title=title_text, synopsis=synopsis, genre=(request.form.get("genre") or "").strip()[:80], release_year=year, poster_url=(request.form.get("poster_url") or "").strip()[:700], video_path=video_path, status="pending")
        db.session.add(item)
        db.session.commit()
        flash("عنوان سینمایی ثبت شد و پس از بررسی مدیر منتشر می‌شود.", "success")
        return redirect(url_for("cinema_home"))

    @app.post("/admin/cinema/title/<int:title_id>/<action>", endpoint="cinema_admin_moderate")
    @admin_required
    def cinema_admin_moderate(title_id, action):
        item = db.session.get(CinemaTitle, title_id)
        if not item or action not in {"publish", "reject"}: abort(404)
        item.status = "published" if action == "publish" else "rejected"
        db.session.commit()
        return redirect(url_for("cinema_home"))

    @app.post("/admin/cinema/showtime", endpoint="cinema_admin_showtime")
    @admin_required
    def cinema_admin_showtime():
        item = db.session.get(CinemaTitle, request.form.get("title_id", type=int))
        venue = (request.form.get("venue") or "").strip()
        try: starts = datetime.strptime((request.form.get("starts_at") or "").strip(), "%Y-%m-%dT%H:%M")
        except ValueError: abort(400)
        capacity = request.form.get("capacity", type=int)
        price = request.form.get("ticket_price", 0, type=int)
        if not item or item.status != "published" or not venue or len(venue) > 180 or starts <= datetime.utcnow() or capacity is None or not 1 <= capacity <= 5000 or price is None or price < 0: abort(400)
        db.session.add(CinemaShowtime(title_id=item.id, venue=venue, starts_at=starts, ticket_price=price, capacity=capacity, available_seats=capacity))
        db.session.commit()
        return redirect(url_for("cinema_home"))
    return models
