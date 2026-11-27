"""Database-backed, moderated media posts and interaction API.

Media is metadata-only for now: this module does not accept raw file uploads.
"""
from datetime import datetime
from flask import request, jsonify, session, abort
from sqlalchemy import desc


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

    # Expose model references for tests and future moderation workflows.
    app.extensions["kharidino_media_models"]={"post":MediaPost,"like":MediaLike,"bookmark":MediaBookmark,"report":MediaReport}
