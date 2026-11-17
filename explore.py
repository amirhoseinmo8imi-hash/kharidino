"""Moderated image/video Explore feed for Kharidino.

This first delivery keeps the existing Flask modular-monolith architecture.
Uploads are validated and stored under static/uploads/explore for development;
production object storage/transcoding/CDN is deliberately a separate rollout.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename


IMAGE_SIGNATURES = {
    "jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    "webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}
VIDEO_SIGNATURES = {
    "mp4": lambda data: len(data) >= 12 and data[4:8] == b"ftyp",
    "webm": lambda data: data.startswith(b"\x1a\x45\xdf\xa3"),
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024


def _validated_upload(upload):
    """Return (extension, media_type, size) or raise ValueError."""
    if not upload or not upload.filename:
        raise ValueError("یک فایل تصویر یا ویدئو انتخاب کن.")
    original = secure_filename(upload.filename)
    if "." not in original:
        raise ValueError("پسوند فایل معتبر نیست.")
    extension = original.rsplit(".", 1)[1].lower()
    checker = IMAGE_SIGNATURES.get(extension) or VIDEO_SIGNATURES.get(extension)
    if checker is None:
        raise ValueError("فقط تصویرهای PNG/JPG/WEBP/GIF و ویدئوی MP4/WEBM مجاز هستند.")
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    media_type = "image" if extension in IMAGE_SIGNATURES else "video"
    limit = MAX_IMAGE_BYTES if media_type == "image" else MAX_VIDEO_BYTES
    if size <= 0 or size > limit:
        raise ValueError("حجم فایل از محدودیت مجاز این نوع رسانه بیشتر است.")
    signature = upload.stream.read(16)
    upload.stream.seek(0)
    if not checker(signature):
        raise ValueError("محتوای فایل با پسوند آن مطابقت ندارد.")
    return extension, media_type, size


def register_explore(app, db, User, Product, login_required, admin_required):
    """Register Explore models and routes on the existing Flask application."""
    if app.extensions.get("kharidino_explore_registered"):
        return app.extensions["kharidino_explore_models"]

    class ExplorePost(db.Model):
        __tablename__ = "explore_post"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
        product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True, index=True)
        caption = db.Column(db.String(1200), nullable=False, default="")
        media_path = db.Column(db.String(500), nullable=False)
        media_type = db.Column(db.String(10), nullable=False)
        status = db.Column(db.String(20), nullable=False, default="pending", index=True)
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
        user = db.relationship(User, backref=db.backref("explore_posts", lazy=True))
        product = db.relationship(Product)
        likes = db.relationship("ExploreLike", back_populates="post", cascade="all, delete-orphan", lazy=True)
        reports = db.relationship("ExploreReport", back_populates="post", cascade="all, delete-orphan", lazy=True)

    class ExploreLike(db.Model):
        __tablename__ = "explore_like"
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey("explore_post.id", ondelete="CASCADE"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        post = db.relationship(ExplorePost, back_populates="likes")
        __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_explore_like_post_user"),)

    class ExploreReport(db.Model):
        __tablename__ = "explore_report"
        id = db.Column(db.Integer, primary_key=True)
        post_id = db.Column(db.Integer, db.ForeignKey("explore_post.id", ondelete="CASCADE"), nullable=False)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
        reason = db.Column(db.String(500), nullable=False, default="")
        status = db.Column(db.String(20), nullable=False, default="open", index=True)
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        post = db.relationship(ExplorePost, back_populates="reports")
        __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_explore_report_post_user"),)

    app.extensions["kharidino_explore_registered"] = True
    app.extensions["kharidino_explore_models"] = {
        "post": ExplorePost, "like": ExploreLike, "report": ExploreReport,
    }

    upload_dir = Path(app.static_folder or "static") / "uploads" / "explore"
    upload_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/explore", endpoint="explore")
    def explore_feed():
        page = request.args.get("page", 1, type=int) or 1
        page = max(1, min(page, 100000))
        posts = (ExplorePost.query.filter_by(status="published")
                 .order_by(ExplorePost.created_at.desc(), ExplorePost.id.desc())
                 .offset((page - 1) * 12).limit(12).all())
        liked_ids = set()
        pending_posts = []
        current_user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
        if current_user:
            liked_ids = {row.post_id for row in ExploreLike.query.filter_by(
                user_id=current_user.id
            ).filter(ExploreLike.post_id.in_([post.id for post in posts])).all()} if posts else set()
            if current_user.role == "admin":
                pending_posts = ExplorePost.query.filter_by(status="pending").order_by(
                    ExplorePost.created_at.asc()
                ).limit(30).all()
        return render_template(
            "explore/index.html", posts=posts, liked_ids=liked_ids,
            pending_posts=pending_posts, page=page,
        )

    @app.post("/explore/create", endpoint="explore_create")
    @login_required
    def explore_create():
        caption = (request.form.get("caption") or "").strip()
        if len(caption) > 1200:
            abort(400, description="متن پست بیش از حد مجاز است.")
        upload = request.files.get("media")
        saved_path = None
        try:
            extension, media_type, _size = _validated_upload(upload)
            filename = f"{secrets.token_hex(20)}.{extension}"
            saved_path = upload_dir / filename
            upload.save(saved_path)
            product_id = request.form.get("product_id", type=int)
            product = db.session.get(Product, product_id) if product_id else None
            if product_id and (not product or not product.active):
                raise ValueError("محصول انتخاب‌شده معتبر یا فعال نیست.")
            post = ExplorePost(
                user_id=session["user_id"],
                product_id=product.id if product else None,
                caption=caption,
                media_path=f"uploads/explore/{filename}",
                media_type=media_type,
                status="pending",
            )
            db.session.add(post)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink(missing_ok=True)
            flash(str(exc), "warning")
            return redirect(url_for("explore"))
        except Exception:
            db.session.rollback()
            if saved_path and saved_path.exists():
                saved_path.unlink(missing_ok=True)
            app.logger.exception("Explore upload failed")
            abort(500)
        flash("محتوا ثبت شد و پس از بررسی مدیر منتشر می‌شود.", "success")
        return redirect(url_for("explore"))

    @app.post("/explore/<int:post_id>/like", endpoint="explore_like")
    @login_required
    def explore_like(post_id):
        post = db.session.get(ExplorePost, post_id)
        if not post or post.status != "published":
            abort(404)
        user_id = session["user_id"]
        existing = ExploreLike.query.filter_by(post_id=post.id, user_id=user_id).first()
        if existing:
            db.session.delete(existing)
        else:
            db.session.add(ExploreLike(post_id=post.id, user_id=user_id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        return redirect(request.referrer if request.referrer and request.referrer.startswith("/") and not request.referrer.startswith("//") else url_for("explore"))

    @app.post("/explore/<int:post_id>/report", endpoint="explore_report")
    @login_required
    def explore_report(post_id):
        post = db.session.get(ExplorePost, post_id)
        if not post or post.status != "published":
            abort(404)
        report = ExploreReport.query.filter_by(
            post_id=post.id, user_id=session["user_id"]
        ).first()
        if not report:
            db.session.add(ExploreReport(
                post_id=post.id,
                user_id=session["user_id"],
                reason=(request.form.get("reason") or "گزارش کاربر").strip()[:500],
            ))
            db.session.commit()
        flash("گزارش شما برای بررسی ثبت شد.", "success")
        return redirect(url_for("explore"))

    @app.post("/admin/explore/<int:post_id>/<action>", endpoint="explore_moderate")
    @admin_required
    def explore_moderate(post_id, action):
        post = db.session.get(ExplorePost, post_id)
        if not post:
            abort(404)
        if action not in {"publish", "reject"}:
            abort(400)
        post.status = "published" if action == "publish" else "rejected"
        db.session.commit()
        flash("وضعیت محتوای اکسپلور به‌روزرسانی شد.", "success")
        return redirect(url_for("explore"))

    return app.extensions["kharidino_explore_models"]
