"""Merchant marketplace extension for Kharidino.

Each seller owns one isolated Store workspace. Seller-created products are linked
through SellerProduct so global catalog products and other merchants remain safe.
"""
from functools import wraps

from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from app import (
    app, db, User, Store, Product, Offer, Category,
    admin_required, save_image, remove_upload, lowest_price,
)


class MerchantStore(db.Model):
    __tablename__ = "kharidino_merchant_store"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), unique=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship("User", backref=db.backref("merchant_account", uselist=False))
    store = db.relationship("Store", backref=db.backref("merchant_account", uselist=False))


class SellerProduct(db.Model):
    __tablename__ = "kharidino_seller_product"
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    __table_args__ = (db.UniqueConstraint("store_id", "product_id", name="uq_seller_product_store_product"),)
    store = db.relationship("Store", backref=db.backref("seller_products", lazy=True))
    product = db.relationship("Product", backref=db.backref("seller_links", lazy=True))


def _seller_account(user_id=None):
    uid = user_id or session.get("user_id")
    if not uid:
        return None
    user = db.session.get(User, uid)
    if not user or user.role != "seller":
        return None
    return MerchantStore.query.filter_by(user_id=user.id).first()


def seller_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        account = _seller_account()
        if not account:
            flash("این بخش فقط برای فروشندگان است.", "warning")
            return redirect(url_for("seller_register"))
        if account.status != "approved" or not account.store.active:
            flash("فروشگاه شما هنوز تأیید نشده است.", "warning")
            return redirect(url_for("seller_register"))
        return fn(*args, **kwargs)
    return wrapper


def _seller_products(store_id):
    links = SellerProduct.query.filter_by(store_id=store_id).order_by(SellerProduct.id.desc()).all()
    return [link.product for link in links if link.product]


def _owned_product(store_id, product_id):
    link = SellerProduct.query.filter_by(store_id=store_id, product_id=product_id).first()
    if not link:
        abort(404)
    return link.product


def _store_name(name):
    return " ".join((name or "").split())[:200]


@app.route("/seller/register", methods=["GET", "POST"])
def seller_register():
    if session.get("user_id"):
        account = _seller_account()
        if account:
            return render_template("seller_register.html")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        store_name = _store_name(request.form.get("store_name", ""))
        website = request.form.get("website", "").strip()
        if not name or not email or not password or not store_name:
            flash("نام، ایمیل، رمز عبور و نام فروشگاه الزامی است.", "warning")
            return render_template("seller_register.html")
        if len(password) < 8:
            flash("رمز عبور باید حداقل ۸ کاراکتر باشد.", "warning")
            return render_template("seller_register.html")
        if User.query.filter_by(email=email).first():
            flash("این ایمیل قبلاً ثبت شده است. وارد حساب شوید یا ایمیل دیگری انتخاب کنید.", "danger")
            return render_template("seller_register.html")
        if website and not website.startswith(("http://", "https://")):
            flash("لینک وب‌سایت باید با http:// یا https:// شروع شود.", "warning")
            return render_template("seller_register.html")
        user = User(name=name, email=email, password=generate_password_hash(password), role="seller")
        store = Store(name=store_name, website=website, active=False)
        db.session.add_all([user, store])
        db.session.flush()
        db.session.add(MerchantStore(user_id=user.id, store_id=store.id, status="pending"))
        db.session.commit()
        session.clear()
        session["user_id"] = user.id
        session.modified = True
        flash("درخواست فروشگاه ثبت شد. بعد از تأیید مدیر می‌توانید فروشگاه را مدیریت کنید. 🏪", "success")
    return render_template("seller_register.html")


@app.route("/seller")
seller_required
def seller_dashboard():
    account = _seller_account()
    products = _seller_products(account.store_id)
    product_ids = [p.id for p in products]
    offers = Offer.query.filter_by(store_id=account.store_id).order_by(Offer.id.desc()).all()
    categories = Category.query.filter_by(active=True).order_by(Category.name.asc()).all()
    order_items = []
    from app import OrderItem, Order
    if product_ids:
        order_items = (OrderItem.query.join(Order, OrderItem.order_id == Order.id)
                       .filter(OrderItem.product_id.in_(product_ids)).order_by(Order.id.desc()).limit(100).all())
    stats = {"products": len(products), "offers": len(offers), "in_stock": sum(1 for o in offers if o.in_stock), "orders": len(order_items)}
    return render_template("seller_dashboard.html", account=account, store=account.store, products=products,
                           offers=offers, order_items=order_items, stats=stats, categories=categories,
                           lowest_price=lowest_price)


@app.post("/seller/store/save")
seller_required
def seller_store_save():
    account = _seller_account(); store = account.store
    name = _store_name(request.form.get("name", "")); website = request.form.get("website", "").strip()
    if not name:
        flash("نام فروشگاه الزامی است.", "warning"); return redirect(url_for("seller_dashboard"))
    if website and not website.startswith(("http://", "https://")):
        flash("لینک وب‌سایت نامعتبر است.", "warning"); return redirect(url_for("seller_dashboard"))
    store.name, store.website = name, website
    uploaded = request.files.get("logo")
    if uploaded and uploaded.filename:
        old = store.logo
        try:
            from app import save_store_logo
            store.logo = save_store_logo(uploaded)
            if old: remove_upload(old)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), "danger"); return redirect(url_for("seller_dashboard"))
    db.session.commit(); flash("اطلاعات فروشگاه ذخیره شد. ✅", "success")
    return redirect(url_for("seller_dashboard"))


@app.post("/seller/product/save")
seller_required
def seller_product_save():
    account = _seller_account()
    pid = request.form.get("id", "").strip(); name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip(); category_id = request.form.get("category_id", "").strip()
    price_raw = request.form.get("price", "0").strip(); stock = request.form.get("in_stock") == "1"; url = request.form.get("url", "").strip()
    if not name:
        flash("نام محصول الزامی است.", "warning"); return redirect(url_for("seller_dashboard"))
    try:
        price = max(0, int(price_raw or 0)); category = db.session.get(Category, int(category_id)) if category_id else None
    except (TypeError, ValueError):
        flash("قیمت یا دسته‌بندی نامعتبر است.", "danger"); return redirect(url_for("seller_dashboard"))
    if category_id and not category:
        flash("دسته‌بندی پیدا نشد.", "danger"); return redirect(url_for("seller_dashboard"))
    if url and not url.startswith(("http://", "https://")):
        flash("لینک خرید نامعتبر است.", "danger"); return redirect(url_for("seller_dashboard"))
    if pid:
        product = _owned_product(account.store_id, int(pid))
    else:
        product = Product(name=name, description=description, price=price, category_id=category.id if category else None, active=True)
        db.session.add(product); db.session.flush(); db.session.add(SellerProduct(store_id=account.store_id, product_id=product.id))
    product.name, product.description, product.price = name, description, price
    product.category_id, product.active = (category.id if category else None), True
    uploaded = request.files.get("image")
    if uploaded and uploaded.filename:
        old = product.image
        try:
            product.image = save_image(uploaded)
            if old: remove_upload(old)
        except ValueError as exc:
            db.session.rollback(); flash(str(exc), "danger"); return redirect(url_for("seller_dashboard"))
    offer = Offer.query.filter_by(product_id=product.id, store_id=account.store_id).first()
    if not offer:
        offer = Offer(product_id=product.id, store_id=account.store_id); db.session.add(offer)
    offer.price, offer.url, offer.in_stock = price, url, stock
    db.session.commit(); flash("محصول و قیمت فروشگاه ذخیره شد. ✅", "success")
    return redirect(url_for("seller_dashboard") + "#products")


@app.post("/seller/product/delete/<int:product_id>")
seller_required
def seller_product_delete(product_id):
    account = _seller_account(); product = _owned_product(account.store_id, product_id)
    if Offer.query.filter(Offer.product_id == product.id, Offer.store_id != account.store_id).count():
        flash("این محصول در فروشگاه‌های دیگر هم استفاده شده و حذف کامل آن مجاز نیست.", "warning")
        return redirect(url_for("seller_dashboard") + "#products")
    if product.image: remove_upload(product.image)
    SellerProduct.query.filter_by(store_id=account.store_id, product_id=product.id).delete()
    Offer.query.filter_by(store_id=account.store_id, product_id=product.id).delete()
    db.session.delete(product); db.session.commit()
    flash("محصول از فروشگاه حذف شد. 🗑️", "success")
    return redirect(url_for("seller_dashboard") + "#products")


@app.post("/seller/offer/toggle/<int:product_id>")
seller_required
def seller_offer_toggle(product_id):
    account = _seller_account(); product = _owned_product(account.store_id, product_id)
    offer = Offer.query.filter_by(product_id=product.id, store_id=account.store_id).first()
    if not offer: abort(404)
    offer.in_stock = not offer.in_stock; db.session.commit()
    flash("وضعیت موجودی تغییر کرد.", "success")
    return redirect(url_for("seller_dashboard") + "#products")


@app.route("/admin/merchants")
@admin_required
def admin_merchants():
    return render_template("admin_merchants.html", accounts=MerchantStore.query.order_by(MerchantStore.id.desc()).all())


@app.post("/admin/merchant/status/<int:account_id>")
@admin_required
def admin_merchant_status(account_id):
    account = MerchantStore.query.get_or_404(account_id); status = request.form.get("status", "pending")
    if status not in {"pending", "approved", "rejected", "suspended"}: abort(400)
    account.status = status; account.store.active = status == "approved"; db.session.commit()
    flash("وضعیت فروشگاه به‌روزرسانی شد. ✅", "success"); return redirect(url_for("admin_merchants"))


@app.post("/admin/merchant/delete/<int:account_id>")
@admin_required
def admin_merchant_delete(account_id):
    account = MerchantStore.query.get_or_404(account_id); account.store.active = False; account.status = "rejected"; db.session.commit()
    flash("فروشگاه غیرفعال شد.", "success"); return redirect(url_for("admin_merchants"))
