"""Catalog extensions inspired by the useful modular patterns in Django-Shop.

Security rule: all mutations remain POST-only and rely on Kharidino's global CSRF layer.
"""
from datetime import datetime
from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import Table, Column, Integer, ForeignKey
from app import app, db, Product, Category, admin_required, validate_external_url

product_brand = Table(
    "kharidino_product_brand",
    db.metadata,
    Column("product_id", Integer, ForeignKey("product.id", ondelete="CASCADE"), primary_key=True),
    Column("brand_id", Integer, ForeignKey("kharidino_brand.id", ondelete="CASCADE"), primary_key=True),
)


class Brand(db.Model):
    __tablename__ = "kharidino_brand"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    products = db.relationship("Product", secondary=product_brand, backref="brands")


class ArticleCategory(db.Model):
    __tablename__ = "kharidino_article_category"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)


article_product = Table(
    "kharidino_article_product",
    db.metadata,
    Column("article_id", Integer, ForeignKey("kharidino_article.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Integer, ForeignKey("product.id", ondelete="CASCADE"), primary_key=True),
)


class Article(db.Model):
    __tablename__ = "kharidino_article"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("kharidino_article_category.id"), nullable=True, index=True)
    title = db.Column(db.String(240), nullable=False)
    slug = db.Column(db.String(260), unique=True, nullable=False, index=True)
    excerpt = db.Column(db.String(500), default="")
    body = db.Column(db.Text, default="")
    image = db.Column(db.String(500), default="")
    seo_title = db.Column(db.String(240), default="")
    seo_description = db.Column(db.String(320), default="")
    published_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.relationship("ArticleCategory", backref=db.backref("articles", lazy=True))
    products = db.relationship("Product", secondary=article_product, backref="related_articles")


class SiteBanner(db.Model):
    __tablename__ = "kharidino_site_banner"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False, default="بنر")
    position = db.Column(db.String(40), nullable=False, default="home")
    image = db.Column(db.String(500), nullable=False)
    target_url = db.Column(db.String(700), default="")
    starts_at = db.Column(db.DateTime)
    ends_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, nullable=False, default=True)


def _slug(value):
    value = "-".join((value or "").strip().lower().split())
    return "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:140]


def _active_banners(position):
    now = datetime.utcnow()
    return SiteBanner.query.filter(
        SiteBanner.position == position,
        SiteBanner.active.is_(True),
        db.or_(SiteBanner.starts_at.is_(None), SiteBanner.starts_at <= now),
        db.or_(SiteBanner.ends_at.is_(None), SiteBanner.ends_at >= now),
    ).order_by(SiteBanner.id.desc()).all()


@app.context_processor
def inject_catalog_globals():
    return {"home_banners": _active_banners("home")}


@app.get("/products")
def catalog_products():
    q = (request.args.get("q") or "").strip()[:100]
    brand_slug = (request.args.get("brand") or "").strip()[:140]
    category_id = (request.args.get("category") or "").strip()
    store_id = (request.args.get("store") or "").strip()
    stock = (request.args.get("stock") or "").strip()
    sort = (request.args.get("sort") or "newest").strip()
    try:
        min_price = max(0, int(request.args.get("min_price", "0") or 0))
        max_price = max(0, int(request.args.get("max_price", "0") or 0))
    except ValueError:
        min_price = max_price = 0

    query = Product.query.filter(Product.active.is_(True))
    if q:
        needle = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(needle), Product.description.ilike(needle)))
    if brand_slug:
        brand = Brand.query.filter_by(slug=brand_slug, active=True).first()
        if brand:
            query = query.join(product_brand, product_brand.c.product_id == Product.id).filter(product_brand.c.brand_id == brand.id)
        else:
            query = query.filter(db.false())
    if category_id.isdigit():
        query = query.filter(Product.category_id == int(category_id))
    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)
    if sort == "price_low":
        query = query.order_by(Product.price.asc(), Product.id.desc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc(), Product.id.desc())
    elif sort == "name":
        query = query.order_by(Product.name.asc())
    else:
        sort = "newest"
        query = query.order_by(Product.id.desc())

    return render_template(
        "catalog_products.html",
        products=query.all(),
        brands=Brand.query.filter_by(active=True).order_by(Brand.name.asc()).all(),
        categories=Category.query.filter_by(active=True).order_by(Category.name.asc()).all(),
        q=q, brand_slug=brand_slug, category_id=category_id, store_id=store_id,
        stock=stock, min_price=min_price, max_price=max_price, sort=sort,
    )


@app.get("/magazine")
def magazine():
    articles = Article.query.filter(
        Article.active.is_(True),
        db.or_(Article.published_at.is_(None), Article.published_at <= datetime.utcnow()),
    ).order_by(Article.published_at.desc().nullslast(), Article.id.desc()).all()
    return render_template("magazine.html", articles=articles)


@app.get("/magazine/<slug>")
def magazine_article(slug):
    article = Article.query.filter_by(slug=slug, active=True).first_or_404()
    if article.published_at and article.published_at > datetime.utcnow():
        return ("Not Found", 404)
    return render_template("magazine_article.html", article=article)


@app.route("/admin/catalog/brands", methods=["GET", "POST"])
@admin_required
def admin_brands():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()[:120]
        slug = _slug(request.form.get("slug") or name)
        if not name or not slug or Brand.query.filter(db.or_(Brand.name == name, Brand.slug == slug)).first():
            flash("نام یا شناسه برند نامعتبر یا تکراری است.", "danger")
            return redirect(url_for("admin_brands"))
        db.session.add(Brand(name=name, slug=slug))
        db.session.commit()
        flash("برند ایجاد شد.", "success")
    return render_template("admin_brands.html", brands=Brand.query.order_by(Brand.id.desc()).all())


@app.post("/admin/catalog/brands/<int:brand_id>/toggle")
@admin_required
def toggle_brand(brand_id):
    brand = db.session.get(Brand, brand_id)
    if not brand:
        return ("Not Found", 404)
    brand.active = not brand.active
    db.session.commit()
    return redirect(url_for("admin_brands"))


@app.route("/admin/catalog/articles", methods=["GET", "POST"])
@admin_required
def admin_articles():
    categories = ArticleCategory.query.order_by(ArticleCategory.name.asc()).all()
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()[:240]
        slug = _slug(request.form.get("slug") or title)
        body = (request.form.get("body") or "").strip()
        category_id = request.form.get("category_id")
        if not title or not slug or not body or Article.query.filter_by(slug=slug).first():
            flash("عنوان، شناسه و متن مقاله الزامی و شناسه باید یکتا باشد.", "danger")
            return redirect(url_for("admin_articles"))
        category = db.session.get(ArticleCategory, int(category_id)) if category_id and category_id.isdigit() else None
        db.session.add(Article(title=title, slug=slug, body=body, excerpt=(request.form.get("excerpt") or "").strip()[:500], category=category, published_at=datetime.utcnow()))
        db.session.commit()
        flash("مقاله منتشر شد.", "success")
    return render_template("admin_articles.html", articles=Article.query.order_by(Article.id.desc()).all(), categories=categories)


@app.post("/admin/catalog/articles/category")
@admin_required
def admin_article_category():
    name = (request.form.get("name") or "").strip()[:120]
    slug = _slug(request.form.get("slug") or name)
    if not name or not slug or ArticleCategory.query.filter(db.or_(ArticleCategory.name == name, ArticleCategory.slug == slug)).first():
        flash("دسته مقاله نامعتبر یا تکراری است.", "danger")
    else:
        db.session.add(ArticleCategory(name=name, slug=slug))
        db.session.commit()
        flash("دسته مقاله ایجاد شد.", "success")
    return redirect(url_for("admin_articles"))


@app.route("/admin/catalog/banners", methods=["GET", "POST"])
@admin_required
def admin_banners():
    if request.method == "POST":
        title = (request.form.get("title") or "بنر").strip()[:160]
        position = (request.form.get("position") or "home").strip()[:40]
        image = (request.form.get("image") or "").strip()[:500]
        try:
            target_url = validate_external_url(request.form.get("target_url") or "")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin_banners"))
        if not image or position not in {"home", "category", "product", "campaign"}:
            flash("تصویر و جایگاه بنر الزامی است.", "danger")
            return redirect(url_for("admin_banners"))
        db.session.add(SiteBanner(title=title, position=position, image=image, target_url=target_url, active=True))
        db.session.commit()
        flash("بنر ذخیره شد.", "success")
    return render_template("admin_banners.html", banners=SiteBanner.query.order_by(SiteBanner.id.desc()).all())


@app.post("/admin/catalog/banners/<int:banner_id>/toggle")
@admin_required
def toggle_banner(banner_id):
    banner = db.session.get(SiteBanner, banner_id)
    if not banner:
        return ("Not Found", 404)
    banner.active = not banner.active
    db.session.commit()
    return redirect(url_for("admin_banners"))


def apply_catalog_extensions(flask_app):
    flask_app.jinja_env.globals["catalog_brand_count"] = lambda: Brand.query.filter_by(active=True).count()
