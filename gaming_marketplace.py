from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash, abort
from sqlalchemy import or_

def register_gaming_marketplace(app, db, User, Product, Category):
    # Keep registration idempotent: app.py can be imported repeatedly by pytest
    # and development reloaders, while SQLAlchemy metadata must only register
    # these models/tables once per Flask app instance.
    if getattr(app, "_kharidino_gaming_marketplace_registered", False):
        return getattr(app, "_kharidino_gaming_marketplace_result", None)

    class GamingProductMeta(db.Model):
        __tablename__ = "gaming_product_meta"
        id = db.Column(db.Integer, primary_key=True)
        product_id = db.Column(db.Integer, db.ForeignKey("product.id"), unique=True, nullable=False)
        seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        item_type = db.Column(db.String(50), default="game")
        game = db.Column(db.String(160), default="")
        platform = db.Column(db.String(50), default="PC")
        edition = db.Column(db.String(120), default="")
        condition = db.Column(db.String(30), default="new")
        delivery = db.Column(db.String(40), default="physical")
        region = db.Column(db.String(80), default="")
        activation = db.Column(db.String(120), default="")
        warranty = db.Column(db.String(160), default="")
        stock = db.Column(db.Integer, default=1)
        seller_verified = db.Column(db.Boolean, default=False)
        status = db.Column(db.String(30), default="pending", nullable=False)
        specs = db.Column(db.Text, default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        product = db.relationship("Product", backref=db.backref("gaming_meta", uselist=False))
        seller = db.relationship("User")

    class GamingSellerProfile(db.Model):
        __tablename__ = "gaming_seller_profile"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
        store_name = db.Column(db.String(160), default="")
        bio = db.Column(db.Text, default="")
        verified = db.Column(db.Boolean, default=False)
        rating = db.Column(db.Float, default=5.0)
        sales_count = db.Column(db.Integer, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        user = db.relationship("User")

    def logged_user():
        uid = session.get("user_id")
        return db.session.get(User, uid) if uid else None

    def gaming_category():
        cat = Category.query.filter(Category.name.ilike("گیمینگ")).first()
        if not cat:
            cat = Category(name="گیمینگ", icon="fa-gamepad", description="بازی، کنسول، تجهیزات و کالاهای تخصصی گیمرها", active=True)
            db.session.add(cat)
            db.session.flush()
        return cat

    def public_query():
        return (GamingProductMeta.query.join(Product, GamingProductMeta.product_id == Product.id)
                .filter(GamingProductMeta.status == "approved", Product.active.is_(True)))

    @app.get("/gaming/store")
    def gaming_store():
        q = request.args.get("q", "").strip()
        item_type = request.args.get("type", "").strip()
        platform = request.args.get("platform", "").strip()
        delivery = request.args.get("delivery", "").strip()
        condition = request.args.get("condition", "").strip()
        sort = request.args.get("sort", "newest").strip()
        query = public_query()
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Product.name.ilike(like), GamingProductMeta.game.ilike(like), GamingProductMeta.platform.ilike(like)))
        if item_type: query = query.filter(GamingProductMeta.item_type == item_type)
        if platform: query = query.filter(GamingProductMeta.platform == platform)
        if delivery: query = query.filter(GamingProductMeta.delivery == delivery)
        if condition: query = query.filter(GamingProductMeta.condition == condition)
        if sort == "price_low": query = query.order_by(Product.price.asc())
        elif sort == "price_high": query = query.order_by(Product.price.desc())
        else: query = query.order_by(GamingProductMeta.id.desc())
        return render_template("gaming/store.html", listings=query.limit(80).all(), q=q, item_type=item_type,
                               platform=platform, delivery=delivery, condition=condition, sort=sort)

    @app.get("/gaming/store/<int:listing_id>")
    def gaming_store_detail(listing_id):
        meta = GamingProductMeta.query.filter_by(id=listing_id, status="approved").first_or_404()
        product = db.session.get(Product, meta.product_id)
        if not product or not product.active: abort(404)
        offers = [o for o in getattr(product, "offers", []) if o.in_stock and o.store and o.store.active]
        offers.sort(key=lambda x: int(x.price or 0))
        return render_template("gaming/store_detail.html", meta=meta, product=product, offers=offers[:12])

    @app.route("/gaming/store/create", methods=["GET", "POST"])
    def gaming_store_create():
        user = logged_user()
        if not user: return redirect(url_for("login", next="/gaming/store/create"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            try: price = max(0, int(request.form.get("price", "0") or 0))
            except (TypeError, ValueError): price = 0
            if not name or price <= 0:
                flash("نام کالا و قیمت معتبر الزامی است.", "danger")
                return redirect(url_for("gaming_store_create"))
            category = gaming_category()
            product = Product(name=name, description=request.form.get("description", "").strip(),
                              price=price, category_id=category.id, active=True)
            db.session.add(product); db.session.flush()
            meta = GamingProductMeta(
                product_id=product.id, seller_id=user.id,
                item_type=request.form.get("item_type", "game").strip(),
                game=request.form.get("game", "").strip(),
                platform=request.form.get("platform", "PC").strip(),
                edition=request.form.get("edition", "").strip(),
                condition=request.form.get("condition", "new").strip(),
                delivery=request.form.get("delivery", "physical").strip(),
                region=request.form.get("region", "").strip(),
                activation=request.form.get("activation", "").strip(),
                warranty=request.form.get("warranty", "").strip(),
                stock=max(0, int(request.form.get("stock", "1") or 1)),
                status="pending", specs=request.form.get("specs", "").strip())
            db.session.add(meta); db.session.commit()
            flash("آگهی گیمینگ با موفقیت در بازار خریدینو ثبت شد.", "success")
            return redirect(url_for("gaming_store_detail", listing_id=meta.id))
        return render_template("gaming/store_create.html")

    @app.get("/gaming/seller")
    def gaming_seller():
        user = logged_user()
        if not user: return redirect(url_for("login", next="/gaming/seller"))
        profile = GamingSellerProfile.query.filter_by(user_id=user.id).first()
        listings = GamingProductMeta.query.filter_by(seller_id=user.id).order_by(GamingProductMeta.id.desc()).all()
        return render_template("gaming/seller.html", profile=profile, listings=listings)

    @app.post("/gaming/seller/profile")
    def gaming_seller_profile():
        user = logged_user()
        if not user: return redirect(url_for("login", next="/gaming/seller"))
        profile = GamingSellerProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = GamingSellerProfile(user_id=user.id); db.session.add(profile)
        profile.store_name = request.form.get("store_name", "").strip()[:160]
        profile.bio = request.form.get("bio", "").strip()
        db.session.commit()
        return redirect(url_for("gaming_seller"))

    @app.post("/gaming/store/<int:listing_id>/status")
    def gaming_listing_status(listing_id):
        user = logged_user(); meta = db.session.get(GamingProductMeta, listing_id)
        if not user or not meta: return redirect(url_for("gaming_store"))
        if meta.seller_id != user.id and user.role != "admin": abort(403)
        requested = request.form.get("status", "").strip().lower()
        if user.role == "admin":
            if requested not in {"pending", "approved", "rejected", "paused"}:
                requested = meta.status
        else:
            # Sellers may pause/resume their own listing, but publication is moderated.
            if requested not in {"paused", "pending"}:
                requested = "paused"
        meta.status = requested
        db.session.commit()
        return redirect(request.referrer or url_for("gaming_seller"))

    @app.get("/admin/gaming")
    def gaming_admin():
        user = logged_user()
        if not user or user.role != "admin":
            flash("دسترسی فقط برای مدیر سایت است.", "danger"); return redirect(url_for("login"))
        stats = {"listings": GamingProductMeta.query.count(),
                 "approved": GamingProductMeta.query.filter_by(status="approved").count(),
                 "pending": GamingProductMeta.query.filter_by(status="pending").count(),
                 "sellers": GamingSellerProfile.query.count(), "reports": 0}
        try:
            report_model = db.Model.registry._class_registry.get("GamingReport")
            if report_model: stats["reports"] = report_model.query.filter_by(status="open").count()
        except Exception: pass
        return render_template("gaming/admin.html", stats=stats,
                               recent=GamingProductMeta.query.order_by(GamingProductMeta.id.desc()).limit(30).all())

    @app.post("/admin/gaming/listing/<int:listing_id>")
    def gaming_admin_listing(listing_id):
        user = logged_user()
        if not user or user.role != "admin": abort(403)
        meta = db.session.get(GamingProductMeta, listing_id)
        if not meta: abort(404)
        meta.status = request.form.get("status", meta.status).strip()
        meta.seller_verified = request.form.get("seller_verified") == "1"
        db.session.commit()
        return redirect(url_for("gaming_admin"))

    app.jinja_env.globals["gaming_product_meta_model"] = GamingProductMeta
    app._kharidino_gaming_marketplace_registered = True
    app._kharidino_gaming_marketplace_result = GamingProductMeta
    return GamingProductMeta
