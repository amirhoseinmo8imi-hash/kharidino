"""Kharidino multi-vendor marketplace foundation.

This module layers seller-owned storefronts, listings, commission accounting,
referrals and seller/customer messaging on top of the existing Kharidino app.
It deliberately keeps the original Product/Order models intact so the feature
can be introduced without breaking existing data.
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
import re
import secrets

from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import CheckConstraint, Index, UniqueConstraint


COMMISSION_DEFAULT_BPS = 500  # 5.00%
LEDGER_CREDIT = "credit"
LEDGER_DEBIT = "debit"


def _slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^\w\u0600-\u06ff-]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "shop"


def _money(value):
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0


def register(app, db, Product, Category, Store, Offer, User, login_required, admin_required):
    """Register marketplace models and routes on the existing Flask app."""
    if "marketplace.seller_dashboard" in app.view_functions:
        return

    class SellerProfile(db.Model):
        __tablename__ = "marketplace_seller_profile"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
        store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False, unique=True)
        slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
        display_name = db.Column(db.String(200), nullable=False)
        description = db.Column(db.Text, default="")
        status = db.Column(db.String(20), nullable=False, default="pending")
        commission_bps = db.Column(db.Integer, nullable=False, default=COMMISSION_DEFAULT_BPS)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        user = db.relationship(User, backref=db.backref("seller_profile", uselist=False))
        store = db.relationship(Store, backref=db.backref("seller_profile", uselist=False))
        __table_args__ = (CheckConstraint("commission_bps >= 0 AND commission_bps <= 10000", name="ck_seller_commission_bps"),)

    class SellerListing(db.Model):
        __tablename__ = "marketplace_seller_listing"
        id = db.Column(db.Integer, primary_key=True)
        seller_id = db.Column(db.Integer, db.ForeignKey("marketplace_seller_profile.id"), nullable=False)
        product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
        seller_price = db.Column(db.Integer, nullable=False, default=0)
        stock = db.Column(db.Integer, nullable=False, default=0)
        active = db.Column(db.Boolean, nullable=False, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        seller = db.relationship(SellerProfile, backref=db.backref("listings", lazy=True, cascade="all, delete-orphan"))
        product = db.relationship(Product)
        __table_args__ = (
            UniqueConstraint("seller_id", "product_id", name="uq_marketplace_seller_product"),
            CheckConstraint("seller_price >= 0", name="ck_marketplace_seller_price"),
            CheckConstraint("stock >= 0", name="ck_marketplace_stock"),
            Index("ix_marketplace_listing_active", "seller_id", "active"),
        )

    class SellerLedgerEntry(db.Model):
        __tablename__ = "marketplace_seller_ledger"
        id = db.Column(db.Integer, primary_key=True)
        seller_id = db.Column(db.Integer, db.ForeignKey("marketplace_seller_profile.id"), nullable=False)
        order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=True)
        entry_type = db.Column(db.String(20), nullable=False)
        amount = db.Column(db.Integer, nullable=False)
        commission = db.Column(db.Integer, nullable=False, default=0)
        reference = db.Column(db.String(120), nullable=False, unique=True)
        note = db.Column(db.String(500), default="")
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        seller = db.relationship(SellerProfile, backref=db.backref("ledger", lazy=True, cascade="all, delete-orphan"))
        __table_args__ = (
            CheckConstraint("amount >= 0", name="ck_marketplace_ledger_amount"),
            CheckConstraint("commission >= 0", name="ck_marketplace_ledger_commission"),
            Index("ix_marketplace_ledger_seller_created", "seller_id", "created_at"),
        )

    class SellerWallet(db.Model):
        __tablename__ = "marketplace_seller_wallet"
        id = db.Column(db.Integer, primary_key=True)
        seller_id = db.Column(db.Integer, db.ForeignKey("marketplace_seller_profile.id"), nullable=False, unique=True)
        balance = db.Column(db.Integer, nullable=False, default=0)
        pending_balance = db.Column(db.Integer, nullable=False, default=0)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
        seller = db.relationship(SellerProfile, backref=db.backref("wallet", uselist=False))
        __table_args__ = (
            CheckConstraint("balance >= 0", name="ck_marketplace_wallet_balance"),
            CheckConstraint("pending_balance >= 0", name="ck_marketplace_wallet_pending"),
        )

    class Referral(db.Model):
        __tablename__ = "marketplace_referral"
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        code = db.Column(db.String(40), nullable=False, unique=True, index=True)
        clicks = db.Column(db.Integer, nullable=False, default=0)
        conversions = db.Column(db.Integer, nullable=False, default=0)
        reward_balance = db.Column(db.Integer, nullable=False, default=0)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        user = db.relationship(User, backref=db.backref("referral", uselist=False))

    class MarketplaceMessage(db.Model):
        __tablename__ = "marketplace_message"
        id = db.Column(db.Integer, primary_key=True)
        sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=True)
        body = db.Column(db.Text, nullable=False)
        read_at = db.Column(db.DateTime, nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
        sender = db.relationship(User, foreign_keys=[sender_id])
        recipient = db.relationship(User, foreign_keys=[recipient_id])
        store = db.relationship(Store)
        __table_args__ = (Index("ix_marketplace_message_recipient_created", "recipient_id", "created_at"),)

    app.extensions["kharidino_marketplace"] = {
        "SellerProfile": SellerProfile,
        "SellerListing": SellerListing,
        "SellerLedgerEntry": SellerLedgerEntry,
        "SellerWallet": SellerWallet,
        "Referral": Referral,
        "MarketplaceMessage": MarketplaceMessage,
    }

    def current_user():
        uid = session.get("user_id")
        return db.session.get(User, uid) if uid else None

    def seller_required(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            user = current_user()
            seller = SellerProfile.query.filter_by(user_id=user.id, status="approved").first() if user else None
            if not seller:
                flash("برای دسترسی به پنل فروشنده باید فروشگاه شما تأیید شده باشد.", "warning")
                return redirect(url_for("marketplace.seller_apply"))
            return fn(seller, *args, **kwargs)
        return wrapper

    @app.get("/marketplace/seller/apply")
    @login_required
    def seller_apply():
        user = current_user()
        existing = SellerProfile.query.filter_by(user_id=user.id).first()
        return render_template("marketplace/seller_apply.html", existing=existing)

    @app.post("/marketplace/seller/apply")
    @login_required
    def seller_apply_post():
        user = current_user()
        if SellerProfile.query.filter_by(user_id=user.id).first():
            flash("درخواست فروشندگی شما قبلاً ثبت شده است.", "info")
            return redirect(url_for("marketplace.seller_dashboard"))
        name = request.form.get("store_name", "").strip()
        description = request.form.get("description", "").strip()
        if len(name) < 2:
            flash("نام فروشگاه معتبر نیست.", "danger")
            return redirect(url_for("marketplace.seller_apply"))
        base = _slugify(name)
        slug = base
        n = 2
        while SellerProfile.query.filter_by(slug=slug).first():
            slug = f"{base}-{n}"
            n += 1
        store = Store(name=name, website="", active=False)
        db.session.add(store)
        db.session.flush()
        seller = SellerProfile(user_id=user.id, store_id=store.id, slug=slug, display_name=name, description=description)
        db.session.add(seller)
        db.session.add(SellerWallet(seller=seller))
        db.session.commit()
        flash("درخواست فروشندگی ثبت شد و برای تأیید مدیر ارسال شد. 🏪", "success")
        return redirect(url_for("marketplace.seller_apply"))

    @app.get("/marketplace/seller")
    @seller_required
    def seller_dashboard(seller):
        listings = SellerListing.query.filter_by(seller_id=seller.id).order_by(SellerListing.id.desc()).all()
        wallet = SellerWallet.query.filter_by(seller_id=seller.id).first()
        ledger = SellerLedgerEntry.query.filter_by(seller_id=seller.id).order_by(SellerLedgerEntry.id.desc()).limit(20).all()
        return render_template("marketplace/seller_dashboard.html", seller=seller, listings=listings, wallet=wallet, ledger=ledger)

    @app.post("/marketplace/seller/listing")
    @seller_required
    def seller_listing_create(seller):
        try:
            product_id = int(request.form.get("product_id", "0"))
            price = max(0, int(request.form.get("price", "0")))
            stock = max(0, min(1_000_000, int(request.form.get("stock", "0"))))
        except (TypeError, ValueError):
            flash("اطلاعات محصول نامعتبر است.", "danger")
            return redirect(url_for("marketplace.seller_dashboard"))
        product = db.session.get(Product, product_id)
        if not product or not product.active:
            abort(404)
        listing = SellerListing.query.filter_by(seller_id=seller.id, product_id=product.id).first()
        if listing is None:
            listing = SellerListing(seller_id=seller.id, product_id=product.id)
            db.session.add(listing)
        listing.seller_price = price
        listing.stock = stock
        listing.active = True
        db.session.commit()
        flash("محصول فروشگاه ذخیره شد. ✅", "success")
        return redirect(url_for("marketplace.seller_dashboard"))

    @app.post("/marketplace/seller/listing/<int:listing_id>/toggle")
    @seller_required
    def seller_listing_toggle(seller, listing_id):
        listing = SellerListing.query.filter_by(id=listing_id, seller_id=seller.id).first_or_404()
        listing.active = not listing.active
        db.session.commit()
        return redirect(url_for("marketplace.seller_dashboard"))

    @app.get("/shop/<slug>")
    def public_storefront(slug):
        seller = SellerProfile.query.filter_by(slug=slug, status="approved").first_or_404()
        listings = SellerListing.query.filter_by(seller_id=seller.id, active=True).filter(SellerListing.stock > 0).all()
        return render_template("marketplace/storefront.html", seller=seller, listings=listings)

    @app.get("/marketplace/seller/ledger")
    @seller_required
    def seller_ledger(seller):
        entries = SellerLedgerEntry.query.filter_by(seller_id=seller.id).order_by(SellerLedgerEntry.id.desc()).all()
        return jsonify({"seller": seller.display_name, "entries": [{"type": e.entry_type, "amount": e.amount, "commission": e.commission, "reference": e.reference, "created_at": e.created_at.isoformat()} for e in entries]})

    @app.post("/marketplace/message")
    @login_required
    def send_message():
        user = current_user()
        recipient_id = request.form.get("recipient_id", type=int)
        body = request.form.get("body", "").strip()
        store_id = request.form.get("store_id", type=int)
        if not recipient_id or recipient_id == user.id or not body or len(body) > 4000:
            abort(400)
        recipient = db.session.get(User, recipient_id)
        if not recipient:
            abort(404)
        if store_id and not db.session.get(Store, store_id):
            abort(404)
        db.session.add(MarketplaceMessage(sender_id=user.id, recipient_id=recipient_id, store_id=store_id, body=body))
        db.session.commit()
        return jsonify({"ok": True})

    @app.get("/marketplace/messages")
    @login_required
    def messages():
        user = current_user()
        rows = MarketplaceMessage.query.filter((MarketplaceMessage.sender_id == user.id) | (MarketplaceMessage.recipient_id == user.id)).order_by(MarketplaceMessage.id.desc()).limit(100).all()
        return jsonify({"messages": [{"id": m.id, "sender_id": m.sender_id, "recipient_id": m.recipient_id, "body": m.body, "store_id": m.store_id, "created_at": m.created_at.isoformat()} for m in rows]})

    @app.post("/admin/marketplace/seller/<int:seller_id>/approve")
    @admin_required
    def admin_approve_seller(seller_id):
        seller = db.session.get(SellerProfile, seller_id)
        if not seller:
            abort(404)
        seller.status = "approved"
        seller.store.active = True
        db.session.commit()
        flash(f"فروشگاه «{seller.display_name}» تأیید شد.", "success")
        return redirect(url_for("admin"))

    @app.post("/admin/marketplace/seller/<int:seller_id>/reject")
    @admin_required
    def admin_reject_seller(seller_id):
        seller = db.session.get(SellerProfile, seller_id)
        if not seller:
            abort(404)
        seller.status = "rejected"
        seller.store.active = False
        db.session.commit()
        flash("درخواست فروشندگی رد شد.", "info")
        return redirect(url_for("admin"))

    @app.get("/referral")
    @login_required
    def referral_dashboard():
        user = current_user()
        referral = Referral.query.filter_by(user_id=user.id).first()
        if referral is None:
            referral = Referral(user_id=user.id, code=secrets.token_urlsafe(8))
            db.session.add(referral)
            db.session.commit()
        link = url_for("home", ref=referral.code, _external=True)
        return jsonify({"code": referral.code, "link": link, "clicks": referral.clicks, "conversions": referral.conversions, "reward_balance": referral.reward_balance})

    @app.before_request
    def marketplace_referral_capture():
        code = request.args.get("ref", "").strip()
        if code and len(code) <= 40:
            referral = Referral.query.filter_by(code=code).first()
            if referral:
                session["referral_code"] = code

    @app.cli.command("marketplace-create-tables")
    def marketplace_create_tables():
        db.create_all()
        print("Kharidino marketplace tables created.")

    with app.app_context():
        db.create_all()
