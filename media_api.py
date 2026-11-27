"""Database-backed, moderated media posts and interaction API.

Media is metadata-only for now: this module does not accept raw file uploads.
"""
from datetime import datetime
from pathlib import Path
import secrets
from flask import request, jsonify, session, abort
from sqlalchemy import desc
from werkzeug.utils import secure_filename
from PIL import Image
from io import BytesIO


def register_media_api(app, db, User, Product):
    class MediaPost(db.Model):
        __tablename__ = "media_post"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
        kind = db.Column(db.String(16), nullable=False, default="image")
        title = db.Column(db.String(180), nullable=False, default="")
        caption = db.Column(db.Text, nullable=False, default="")
        media_url = db.Column(db.String(700), nullable=False, default="")
        status = db.Column(db.String(20), nullable=False, default="pending")
        created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
        user = db.relationship(User)
        product = db.relationship(Product)

    class MediaLike(db.Model):
        __tablename__ = "media_like"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        post_id = db.Column(db.Integer, db.ForeignKey("media_post.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_media_like"),)

    class MediaBookmark(db.Model):
        __tablename__ = "media_bookmark"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        post_id = db.Column(db.Integer, db.ForeignKey("media_post.id"), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_media_bookmark"),)

    class MediaReport(db.Model):
        __tablename__ = "media_report"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        post_id = db.Column(db.Integer, db.ForeignKey("media_post.id"), nullable=False)
        reason = db.Column(db.String(300), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_media_report"),)

    app.config.setdefault("MEDIA_UPLOAD_DIR", str(Path(app.root_path) / "static" / "uploads" / "media"))
    app.config.setdefault("MEDIA_MAX_IMAGE_BYTES", 8 * 1024 * 1024)
    app.config.setdefault("MEDIA_MAX_VIDEO_BYTES", 80 * 1024 * 1024)
    app.config.setdefault("MEDIA_API_PAGE_SIZE", 20)
    app.config.setdefault("MEDIA_API_MAX_PAGE_SIZE", 40)

    def signed_in():
        uid = session.get("user_id")
        if not uid:
            abort(401, description="Login required")
        return uid

    def serialize(post, uid=None):
        return {
            "id": post.id, "kind": post.kind, "title": post.title,
            "caption": post.caption, "media_url": post.media_url,
            "created_at": post.created_at.isoformat(),
            "author": {"id": post.user.id, "name": post.user.name},
            "product": ({"id": post.product.id, "name": post.product.name,
                        "price": post.product.price} if post.product and post.product.active else None),
            "likes": MediaLike.query.filter_by(post_id=post.id).count(),
            "liked": bool(uid and MediaLike.query.filter_by(post_id=post.id,user_id=uid).first()),
            "bookmarked": bool(uid and MediaBookmark.query.filter_by(post_id=post.id,user_id=uid).first()),
        }

    def feed(reels_only=False):
        try:
            page=max(1,int(request.args.get("page",1)))
            per_page=min(app.config["MEDIA_API_MAX_PAGE_SIZE"],max(1,int(request.args.get("per_page",app.config["MEDIA_API_PAGE_SIZE"]))))
        except (TypeError,ValueError):
            return jsonify(error="invalid_pagination"),400
        query=MediaPost.query.filter_by(status="published")
        if reels_only:
            query=query.filter_by(kind="video")
        query=query.order_by(desc(MediaPost.created_at),desc(MediaPost.id))
        pagination=query.paginate(page=page,per_page=per_page,error_out=False)
        uid=session.get("user_id")
        return jsonify(items=[serialize(p,uid) for p in pagination.items],
                       page=page,per_page=per_page,total=pagination.total,pages=pagination.pages)

    @app.route("/api/media/explore",methods=["GET"])
    def media_explore_feed():
        return feed(False)

    @app.route("/api/media/reels",methods=["GET"])
    def media_reels_feed():
        return feed(True)

    @app.route("/api/media/posts",methods=["POST"])
    def media_create_post():
        uid=signed_in()
        data=request.get_json(silent=True) or request.form
        kind=str(data.get("kind","image")).lower()
        if kind not in {"image","video"}:
            return jsonify(error="invalid_kind"),400
        title=str(data.get("title","")).strip()[:180]
        caption=str(data.get("caption","")).strip()[:4000]
        media_url=str(data.get("media_url","")).strip()
        if not media_url or len(media_url)>700 or not media_url.startswith(("https://","/")):
            return jsonify(error="invalid_media_reference"),400
        product_id=data.get("product_id")
        product=None
        if product_id:
            try: product=db.session.get(Product,int(product_id))
            except (TypeError,ValueError): return jsonify(error="invalid_product"),400
            if not product or not product.active: return jsonify(error="invalid_product"),400
        post=MediaPost(user_id=uid,kind=kind,title=title,caption=caption,media_url=media_url,product=product,status="pending")
        db.session.add(post);db.session.commit()
        return jsonify(id=post.id,status="pending_review"),201

    @app.route("/api/media/upload", methods=["POST"])
    def media_upload():
        uid = signed_in()
        file = request.files.get("file")
        kind = str(request.form.get("kind", "image")).lower()
        if not file or kind not in {"image", "video"}:
            return jsonify(error="file_and_valid_kind_required"), 400
        raw = file.read(app.config["MEDIA_MAX_VIDEO_BYTES"] + 1)
        if not raw:
            return jsonify(error="empty_file"), 400
        if kind == "image":
            if len(raw) > app.config["MEDIA_MAX_IMAGE_BYTES"]:
                return jsonify(error="image_too_large"), 413
            try:
                image = Image.open(BytesIO(raw))
                if image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                    return jsonify(error="unsupported_image"), 400
                image.verify()
            except Exception:
                return jsonify(error="invalid_image"), 400
            ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}[image.format]
        else:
            if len(raw) > app.config["MEDIA_MAX_VIDEO_BYTES"]:
                return jsonify(error="video_too_large"), 413
            if not (raw[4:8] == b"ftyp" or raw[:4] == b"\\x1a\\x45\\xdf\\xa3"):
                return jsonify(error="unsupported_video_container"), 400
            ext = ".mp4" if raw[4:8] == b"ftyp" else ".webm"
        directory = Path(app.config["MEDIA_UPLOAD_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        filename = secrets.token_hex(16) + ext
        target = directory / filename
        target.write_bytes(raw)
        return jsonify(media_url="/static/uploads/media/" + filename, kind=kind), 201

    @app.route("/api/admin/media/pending", methods=["GET"])
    def media_pending_admin():
        uid = signed_in()
        admin = db.session.get(User, uid)
        if not admin or admin.role != "admin":
            abort(403)
        rows = MediaPost.query.filter_by(status="pending").order_by(MediaPost.created_at.asc()).limit(100).all()
        return jsonify(items=[{"id":p.id,"title":p.title,"caption":p.caption,"kind":p.kind,
          "media_url":p.media_url,"user_id":p.user_id,"product_id":p.product_id} for p in rows])

    @app.route("/api/admin/media/posts/<int:post_id>/moderate", methods=["POST"])
    def media_moderate_admin(post_id):
        uid = signed_in()
        admin = db.session.get(User, uid)
        if not admin or admin.role != "admin":
            abort(403)
        post = db.session.get(MediaPost, post_id)
        if not post or post.status != "pending":
            abort(404)
        data = request.get_json(silent=True) or request.form
        decision = str(data.get("decision", "")).lower()
        if decision not in {"publish", "reject"}:
            return jsonify(error="invalid_decision"), 400
        post.status = "published" if decision == "publish" else "rejected"
        db.session.commit()
        return jsonify(id=post.id, status=post.status)

    def get_post(post_id):
        post=db.session.get(MediaPost,post_id)
        if not post or post.status!="published":abort(404)
        return post

    @app.route("/api/media/posts/<int:post_id>/like",methods=["POST"])
    def media_like(post_id):
        uid=signed_in();post=get_post(post_id)
        row=MediaLike.query.filter_by(user_id=uid,post_id=post.id).first()
        if row: db.session.delete(row);liked=False
        else: db.session.add(MediaLike(user_id=uid,post_id=post.id));liked=True
        db.session.commit()
        return jsonify(liked=liked,likes=MediaLike.query.filter_by(post_id=post.id).count())

    @app.route("/api/media/posts/<int:post_id>/bookmark",methods=["POST"])
    def media_bookmark(post_id):
        uid=signed_in();post=get_post(post_id)
        row=MediaBookmark.query.filter_by(user_id=uid,post_id=post.id).first()
        if row: db.session.delete(row);bookmarked=False
        else: db.session.add(MediaBookmark(user_id=uid,post_id=post.id));bookmarked=True
        db.session.commit()
        return jsonify(bookmarked=bookmarked)

    @app.route("/api/media/posts/<int:post_id>/report",methods=["POST"])
    def media_report(post_id):
        uid=signed_in();post=get_post(post_id)
        data=request.get_json(silent=True) or request.form
        reason=str(data.get("reason","")).strip()[:300]
        if not reason:return jsonify(error="reason_required"),400
        if MediaReport.query.filter_by(user_id=uid,post_id=post.id).first():
            return jsonify(status="already_reported"),200
        db.session.add(MediaReport(user_id=uid,post_id=post.id,reason=reason))
        db.session.commit()
        return jsonify(status="reported"),201


    class CinemaTitle(db.Model):
        __tablename__ = "cinema_title"
        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(220), nullable=False)
        synopsis = db.Column(db.Text, default="", nullable=False)
        kind = db.Column(db.String(20), default="movie", nullable=False)
        genre = db.Column(db.String(100), default="", nullable=False)
        year = db.Column(db.Integer, nullable=True)
        poster_url = db.Column(db.String(700), default="", nullable=False)
        trailer_url = db.Column(db.String(700), default="", nullable=False)
        age_rating = db.Column(db.String(30), default="", nullable=False)
        territory = db.Column(db.String(120), default="", nullable=False)
        license_start = db.Column(db.DateTime, nullable=True)
        license_end = db.Column(db.DateTime, nullable=True)
        licensed = db.Column(db.Boolean, default=False, nullable=False)
        published = db.Column(db.Boolean, default=False, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @app.route("/api/cinema/catalog", methods=["GET"])
    def cinema_catalog():
        now=datetime.utcnow()
        rows=CinemaTitle.query.filter_by(published=True,licensed=True).filter(
            db.or_(CinemaTitle.license_start.is_(None),CinemaTitle.license_start<=now),
            db.or_(CinemaTitle.license_end.is_(None),CinemaTitle.license_end>=now)
        ).order_by(CinemaTitle.title.asc()).limit(100).all()
        return jsonify(items=[{"id":x.id,"title":x.title,"synopsis":x.synopsis,
          "kind":x.kind,"genre":x.genre,"year":x.year,"poster_url":x.poster_url,
          "trailer_url":x.trailer_url,"age_rating":x.age_rating,"territory":x.territory}
          for x in rows])

    @app.route("/api/admin/cinema/titles", methods=["POST"])
    def cinema_admin_create():
        uid=signed_in()
        admin=db.session.get(User,uid)
        if not admin or admin.role!="admin":abort(403)
        data=request.get_json(silent=True) or request.form
        title=str(data.get("title","")).strip()[:220]
        kind=str(data.get("kind","movie")).strip().lower()
        if not title or kind not in {"movie","series"}:return jsonify(error="invalid_title"),400
        row=CinemaTitle(title=title,synopsis=str(data.get("synopsis",""))[:6000],
          kind=kind,genre=str(data.get("genre",""))[:100],year=int(data["year"]) if str(data.get("year","")).isdigit() else None,
          poster_url=str(data.get("poster_url",""))[:700],trailer_url=str(data.get("trailer_url",""))[:700],
          age_rating=str(data.get("age_rating",""))[:30],territory=str(data.get("territory",""))[:120],
          licensed=False,published=False)
        db.session.add(row);db.session.commit()
        return jsonify(id=row.id,status="unlicensed_unpublished"),201

    # Expose model references for tests and future moderation workflows.
    app.extensions["kharidino_media_models"]={"post":MediaPost,"like":MediaLike,"bookmark":MediaBookmark,"report":MediaReport,"cinema_title":CinemaTitle}
