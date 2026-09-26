import smtplib
from email.message import EmailMessage
import os
import secrets
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    jsonify,
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv


# Load local .env before any SMTP/payment configuration is read.
load_dotenv()


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"

PRODUCT_UPLOAD_DIR = UPLOAD_DIR / "products"
STORE_UPLOAD_DIR = UPLOAD_DIR / "stores"
BACKGROUND_UPLOAD_DIR = UPLOAD_DIR / "backgrounds"

for folder in [
    STATIC_DIR,
    UPLOAD_DIR,
    PRODUCT_UPLOAD_DIR,
    STORE_UPLOAD_DIR,
    BACKGROUND_UPLOAD_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)

configured_secret = (
    os.environ.get("KHARIDINO_SECRET_KEY", "").strip()
    or os.environ.get("SECRET_KEY", "").strip()
)

if configured_secret:
    app.config["SECRET_KEY"] = configured_secret
else:
    # Keep local sessions stable across restarts. The generated file is ignored
    # by git and can still be overridden by an environment variable in production.
    local_secret_file = BASE_DIR / ".kharidino-secret"
    try:
        if local_secret_file.exists():
            local_secret = local_secret_file.read_text(encoding="utf-8").strip()
        else:
            local_secret = secrets.token_urlsafe(64)
            local_secret_file.write_text(local_secret, encoding="utf-8")
        app.config["SECRET_KEY"] = local_secret or secrets.token_urlsafe(64)
    except OSError:
        app.config["SECRET_KEY"] = secrets.token_urlsafe(64)

# Browser/session settings: use a new cookie namespace so old development sessions cannot
# poison the CSRF/session state after the authentication system is upgraded.
app.config["SESSION_COOKIE_NAME"] = "kharidino_session_v2"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + str(BASE_DIR / "kharidino.db")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# حداکثر حجم آپلود: 100MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

db = SQLAlchemy(app)


# =========================================================
# ALLOWED FILES
# =========================================================

ALLOWED_IMAGES = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
}

ALLOWED_VIDEOS = {
    "mp4",
    "webm",
    "ogg",
}

ALLOWED_BACKGROUND = ALLOWED_IMAGES | ALLOWED_VIDEOS


# =========================================================
# MODELS
# =========================================================

class Setting(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    key = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    value = db.Column(
        db.Text,
        nullable=False,
        default=""
    )


class Category(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    icon = db.Column(
        db.String(100),
        default="fa-box"
    )

    description = db.Column(
        db.String(300),
        default=""
    )

    active = db.Column(
        db.Boolean,
        default=True
    )


class Product(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text,
        default=""
    )

    price = db.Column(
        db.Integer,
        default=0
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("category.id"),
        nullable=True
    )

    image = db.Column(
        db.String(500),
        default=""
    )

    active = db.Column(
        db.Boolean,
        default=True
    )

    category = db.relationship(
        "Category",
        backref=db.backref(
            "products",
            lazy=True
        )
    )


class Store(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(200),
        nullable=False
    )

    website = db.Column(
        db.String(500),
        default=""
    )

    logo = db.Column(
        db.String(500),
        default=""
    )

    active = db.Column(
        db.Boolean,
        default=True
    )


class Offer(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    store_id = db.Column(
        db.Integer,
        db.ForeignKey("store.id"),
        nullable=False
    )

    price = db.Column(
        db.Integer,
        nullable=False
    )

    url = db.Column(
        db.String(700),
        default=""
    )

    in_stock = db.Column(
        db.Boolean,
        default=True
    )

    product = db.relationship(
        "Product",
        backref=db.backref(
            "offers",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    store = db.relationship(
        "Store",
        backref=db.backref(
            "offers",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )


class User(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(200),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(300),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="user",
        nullable=False
    )


class AccountEmailChange(db.Model):
    __tablename__ = "account_email_change"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    pending_email = db.Column(db.String(200), nullable=False)
    code_hash = db.Column(db.String(300), nullable=False, default="")
    expires_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("email_change_request", uselist=False))


class Order(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    total = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="در انتظار بررسی"
    )

    customer_name = db.Column(
        db.String(120),
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    address = db.Column(
        db.Text,
        nullable=False
    )

    note = db.Column(
        db.Text,
        default=""
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "orders",
            lazy=True
        )
    )


class OrderItem(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("order.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    product_name = db.Column(
        db.String(200),
        nullable=False
    )

    price = db.Column(
        db.Integer,
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    order = db.relationship(
        "Order",
        backref=db.backref(
            "items",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    product = db.relationship(
        "Product"
    )



class OrganizationRequest(db.Model):
    __tablename__ = "organization_request"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(250), nullable=False)
    national_id = db.Column(db.String(30), default="")
    economic_code = db.Column(db.String(30), default="")
    registration_number = db.Column(db.String(50), default="")
    postal_code = db.Column(db.String(20), default="")
    phone = db.Column(db.String(40), default="")
    address = db.Column(db.Text, default="")
    contact_name = db.Column(db.String(150), nullable=False)
    contact_email = db.Column(db.String(254), default="")
    contract_subject = db.Column(db.String(300), default="")
    estimated_value = db.Column(db.String(80), default="")
    payment_terms = db.Column(db.String(150), default="")
    invoice_required = db.Column(db.Boolean, default=True)
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(40), default="در انتظار بررسی", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Invoice(db.Model):
    __tablename__ = "invoice"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, unique=True)
    invoice_number = db.Column(db.String(60), unique=True, nullable=False)
    invoice_type = db.Column(db.String(30), default="فروش")
    buyer_type = db.Column(db.String(30), default="مصرف‌کننده")
    buyer_name = db.Column(db.String(250), nullable=False)
    buyer_national_id = db.Column(db.String(30), default="")
    buyer_economic_code = db.Column(db.String(30), default="")
    buyer_registration_number = db.Column(db.String(50), default="")
    buyer_postal_code = db.Column(db.String(20), default="")
    buyer_phone = db.Column(db.String(40), default="")
    buyer_address = db.Column(db.Text, default="")
    subtotal = db.Column(db.Integer, default=0, nullable=False)
    discount = db.Column(db.Integer, default=0, nullable=False)
    tax = db.Column(db.Integer, default=0, nullable=False)
    total = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(30), default="صادر نشده")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    order = db.relationship("Order", backref=db.backref("invoice", uselist=False))


class Review(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    rating = db.Column(
        db.Integer,
        nullable=False,
        default=5
    )

    text = db.Column(
        db.Text,
        default=""
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )

    product = db.relationship(
        "Product",
        backref=db.backref(
            "reviews",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )

    user = db.relationship(
        "User"
    )


class PriceAlert(db.Model):
    __tablename__ = "price_alert"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    target_price = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("price_alerts", lazy=True, cascade="all, delete-orphan"))
    product = db.relationship("Product", backref=db.backref("price_alerts", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="unique_user_product_price_alert"),
    )


class Favorite(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "product_id",
            name="unique_user_product_favorite"
        ),
    )

    user = db.relationship("User")
    product = db.relationship("Product")


# =========================================================
# SETTINGS
# =========================================================

def setting(key, default=""):

    row = Setting.query.filter_by(
        key=key
    ).first()

    if row:
        return row.value

    return default


def set_setting(key, value):

    row = Setting.query.filter_by(
        key=key
    ).first()

    if not row:

        row = Setting(
            key=key,
            value=str(value)
        )

        db.session.add(row)

    else:

        row.value = str(value)

    return row


app.jinja_env.globals["setting"] = setting


# =========================================================
# GLOBAL TEMPLATE DATA
# =========================================================

@app.context_processor
def inject_globals():

    user = (
        db.session.get(
            User,
            session["user_id"]
        )
        if session.get("user_id")
        else None
    )

    raw_cart = session.get(
        "cart",
        {}
    )

    if not isinstance(raw_cart, dict):
        raw_cart = {}

    # =====================================================
    # FAVORITE PRODUCT IDS
    # =====================================================

    favorite_ids = set()

    if user:
        favorite_ids = {
            favorite.product_id
            for favorite in Favorite.query.filter_by(
                user_id=user.id
            ).all()
        }

    # =====================================================
    # COMPARE LIST
    # =====================================================

    raw_compare = session.get("compare", [])
    if not isinstance(raw_compare, list):
        raw_compare = []

    compare_ids = set()
    for value in raw_compare:
        try:
            compare_ids.add(int(value))
        except (TypeError, ValueError):
            pass

    compare_count = len(compare_ids)

    # =====================================================
    # CART COUNT
    # =====================================================

    cart_count = 0

    for value in raw_cart.values():

        try:
            cart_count += int(value)

        except (
            TypeError,
            ValueError
        ):
            pass

    # =====================================================
    # GLOBAL TEMPLATE VARIABLES
    # =====================================================

    # Shared catalog data keeps the mega-menu/footer/search shell connected
    # on every page, not only on the home route.
    global_categories = (
        Category.query
        .filter_by(active=True)
        .order_by(Category.id.asc())
        .all()
    )
    global_stores = (
        Store.query
        .filter_by(active=True)
        .order_by(Store.name.asc())
        .all()
    )

    return {

        "categories": global_categories,
        "stores": global_stores,
        "category_count": len(global_categories),
        "store_count": len(global_stores),
        "product_count": Product.query.filter_by(active=True).count(),
        "offer_count": Offer.query.count(),

        # =================================================
        # SITE
        # =================================================

        "site_name": setting(
            "site_name",
            "خریدینو"
        ),

        "site_tagline": setting(
            "site_tagline",
            "مقایسه قیمت، خرید هوشمند"
        ),

        # =================================================
        # USER
        # =================================================

        "current_user": user,

        # =================================================
        # CART
        # =================================================

        "cart_count": cart_count,

        # =================================================
        # FAVORITES
        # =================================================

        "favorite_ids": favorite_ids,

        # =================================================
        # COMPARE
        # =================================================

        "compare_ids": compare_ids,
        "compare_count": compare_count,

        # =================================================
        # BACKGROUND
        # =================================================

        "background_mode": setting(
            "background_mode",
            "css"
        ),

        "background_media": setting(
            "background_media",
            ""
        ),

        "background_overlay": setting(
            "background_overlay",
            "0.45"
        ),

        "background_speed": setting(
            "background_speed",
            "18"
        ),

        "background_blur": setting(
            "background_blur",
            "0"
        ),

        "background_position": setting(
            "background_position",
            "center"
        ),

        "background_size": setting(
            "background_size",
            "cover"
        ),

        "background_opacity": setting(
            "background_opacity",
            "1"
        ),
    }


# =========================================================
# PRODUCT IMAGE FALLBACKS
# =========================================================
PRODUCT_FALLBACK_IMAGES = {
    "موبایل": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=700&q=85",
    "لپ‌تاپ و کامپیوتر": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=700&q=85",
    "کالای دیجیتال": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=700&q=85",
    "هدفون و هندزفری": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=700&q=85",
    "گیمینگ": "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=700&q=85",
    "تلویزیون و صوتی تصویری": "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?auto=format&fit=crop&w=700&q=85",
    "ساعت و پوشیدنی": "https://images.unsplash.com/photo-1524805444758-089113d48a6d?auto=format&fit=crop&w=700&q=85",
    "خانه و آشپزخانه": "https://images.unsplash.com/photo-1556910103-1c02745aae3?auto=format&fit=crop&w=700&q=85",
    "زیبایی و سلامت": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=700&q=85",
    "کتاب و لوازم‌التحریر": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=700&q=85",
    "ورزش و سفر": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=700&q=85",
    "ابزار": "https://images.unsplash.com/photo-1504148455328-c376907d081c?auto=format&fit=crop&w=700&q=85",
    "خودرو": "https://images.unsplash.com/photo-1503736334956-4c8f8e92946d?auto=format&fit=crop&w=700&q=85",
    "مد و پوشاک": "https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=700&q=85",
    "سوپرمارکتی": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=700&q=85",
    "default": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=700&q=85",
}


def product_image_url(product):
    image = (getattr(product, "image", "") or "").strip()
    if image.startswith(("http://", "https://", "/")):
        return image
    if image:
        return url_for("static", filename=image)
    category = getattr(getattr(product, "category", None), "name", "") or ""
    return PRODUCT_FALLBACK_IMAGES.get(category, PRODUCT_FALLBACK_IMAGES["default"])


app.jinja_env.globals["product_image_url"] = product_image_url


# =========================================================
# CSRF PROTECTION
# =========================================================

def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def validate_csrf():
    # Every rendered page gets a token. Keeping one token for the browser session
    # prevents ordinary navigation and multi-tab use from invalidating open forms.
    csrf_token()

    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    submitted = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or ""
    )
    expected = session.get("csrf_token") or ""

    # If an old/invalid development session cookie was discarded by Flask, allow
    # a public form carrying its own token to establish the fresh session token.
    # Authenticated sessions still require an exact token match.
    if not expected:
        if submitted and not session.get("user_id"):
            session["csrf_token"] = str(submitted)
            session.modified = True
            return None
        abort(400, description="CSRF token is missing or invalid.")

    if not submitted or not secrets.compare_digest(
        str(submitted), str(expected)
    ):
        # Public authentication/onboarding forms can legitimately remain open
        # across a session refresh (for example after restarting the dev server).
        # Rebind their anonymous session to the submitted form token instead of
        # returning a confusing 400. Authenticated mutations remain strict.
        public_recovery_endpoints = {
            "login",
            "register",
            "seller_register",
            "organization_request",
        }
        if not session.get("user_id") and request.endpoint in public_recovery_endpoints and submitted:
            session["csrf_token"] = str(submitted)
            session.modified = True
            return None
        abort(400, description="CSRF token is missing or invalid.")

    return None




def send_kharidino_email(to_email, subject, body):
    """Send SMTP email using either Kharidino or standard .env variable names."""
    to_email = (to_email or "").strip()
    smtp_host = (
        os.environ.get("KHARIDINO_SMTP_HOST", "").strip()
        or os.environ.get("SMTP_HOST", "").strip()
    )
    smtp_user = (
        os.environ.get("KHARIDINO_SMTP_USER", "").strip()
        or os.environ.get("SMTP_USERNAME", "").strip()
    )
    smtp_password = (
        os.environ.get("KHARIDINO_SMTP_PASSWORD", "")
        or os.environ.get("SMTP_PASSWORD", "")
    )
    if not to_email or not smtp_host or not smtp_user or not smtp_password:
        app.logger.error("Kharidino SMTP is not fully configured.")
        return False

    try:
        smtp_port = int(
            os.environ.get("KHARIDINO_SMTP_PORT", "").strip()
            or os.environ.get("SMTP_PORT", "587").strip()
        )
    except ValueError:
        app.logger.error("Invalid SMTP port configuration.")
        return False

    sender = (
        os.environ.get("KHARIDINO_SMTP_FROM", "").strip()
        or os.environ.get("MAIL_FROM", "").strip()
        or smtp_user
    )
    use_ssl = (
        os.environ.get("KHARIDINO_SMTP_SSL", "").strip()
        or os.environ.get("SMTP_USE_SSL", "0").strip()
    ).lower() in {"1", "true", "yes"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        app.logger.info("Kharidino email sent successfully to %s", to_email)
        return True
    except Exception:
        app.logger.exception("Kharidino SMTP notification failed")
        return False

# =========================================================
# AUTH HELPERS
# =========================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if not session.get("user_id"):

            flash(
                "ابتدا وارد حساب کاربری شوید.",
                "warning"
            )

            return redirect(
                url_for(
                    "login",
                    next=request.path
                )
            )

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        user = None

        if session.get("user_id"):

            user = db.session.get(
                User,
                session["user_id"]
            )

        if not user or user.role != "admin":

            flash(
                "دسترسی فقط برای مدیر سایت است.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        return fn(*args, **kwargs)

    return wrapper


# =========================================================
# SAFE REDIRECTS
# =========================================================

def safe_local_redirect(target, fallback):
    target = (target or "").strip()
    if not target:
        return fallback
    parsed = urlparse(target)
    if (
        target.startswith("/")
        and not target.startswith("//")
        and not parsed.scheme
        and not parsed.netloc
        and not parsed.username
        and not parsed.password
    ):
        return target
    return fallback


def validate_external_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("لینک باید یک آدرس معتبر http یا https باشد.")
    if parsed.username or parsed.password:
        raise ValueError("لینک‌های دارای نام کاربری یا رمز عبور مجاز نیستند.")
    return value


# =========================================================
# FILE HELPERS
# =========================================================

def get_extension(filename):

    if not filename or "." not in filename:
        return ""

    return filename.rsplit(
        ".",
        1
    )[1].lower()


def save_upload(
    file,
    folder,
    allowed_extensions
):

    if not file:
        return ""

    if not file.filename:
        return ""

    original_name = secure_filename(
        file.filename
    )

    if not original_name:

        raise ValueError(
            "نام فایل نامعتبر است."
        )

    extension = get_extension(
        original_name
    )

    if not extension:

        raise ValueError(
            "فایل پسوند ندارد."
        )

    if extension not in allowed_extensions:

        raise ValueError(
            "فرمت فایل مجاز نیست."
        )

    unique_name = (
        uuid.uuid4().hex
        + "."
        + extension
    )

    if folder == "products":

        target_dir = PRODUCT_UPLOAD_DIR

    elif folder == "stores":

        target_dir = STORE_UPLOAD_DIR

    elif folder == "backgrounds":

        target_dir = BACKGROUND_UPLOAD_DIR

    else:

        raise ValueError(
            "پوشه آپلود نامعتبر است."
        )

    target_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    target_file = (
        target_dir / unique_name
    )

    file.save(target_file)

    return (
        f"uploads/{folder}/{unique_name}"
    )


def save_image(file):

    return save_upload(
        file,
        "products",
        ALLOWED_IMAGES
    )


def save_store_logo(file):

    return save_upload(
        file,
        "stores",
        ALLOWED_IMAGES
    )


def save_background(file):

    return save_upload(
        file,
        "backgrounds",
        ALLOWED_BACKGROUND
    )


def remove_upload(path):

    if not path:
        return

    if not path.startswith("uploads/"):
        return

    target = (
        STATIC_DIR / path
    ).resolve()

    static_root = STATIC_DIR.resolve()

    try:

        target.relative_to(
            static_root
        )

    except ValueError:

        return

    try:

        if target.exists() and target.is_file():
            target.unlink()

    except OSError:

        pass


def detect_background_mode(path):

    extension = get_extension(
        path
    )

    if extension == "gif":
        return "gif"

    if extension in ALLOWED_VIDEOS:
        return "video"

    if extension in {
        "png",
        "jpg",
        "jpeg",
        "webp",
    }:
        return "image"

    return "css"


# =========================================================
# PRICE
# =========================================================

def lowest_price(product):

    if not product:
        return 0

    prices = []

    for offer in product.offers:

        if not offer:
            continue

        if not offer.in_stock:
            continue

        if not offer.store:
            continue

        if not offer.store.active:
            continue

        try:
            price = int(offer.price)
        except (TypeError, ValueError):
            continue

        if price > 0:
            prices.append(price)

    if prices:
        return min(prices)

    try:
        return int(product.price or 0)
    except (TypeError, ValueError):
        return 0

app.jinja_env.globals["lowest_price"] = lowest_price

# =========================================================
# REVIEWS
# =========================================================

def product_rating(product):

    reviews = product.reviews

    if not reviews:
        return 0

    return round(

        sum(
            review.rating
            for review in reviews
        ) / len(reviews),

        1

    )


app.jinja_env.globals[
    "product_rating"
] = product_rating


# =========================================================
# MONEY FILTER
# =========================================================

@app.template_filter("money")
def money(value):

    try:

        return f"{int(value):,}"

    except Exception:

        return "0"



# =========================================================
# SMART SEARCH HELPERS
# =========================================================

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def normalize_search_text(value):
    return (value or "").translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS).strip()

def parse_search_intent(value):
    """Parse common Persian shopping price intents deterministically."""
    raw = normalize_search_text(value)
    lower = raw.lower()
    import re

    def amount(number, unit):
        try:
            n = float(number.replace(",", "").replace("٬", ""))
        except (TypeError, ValueError):
            return None
        unit = (unit or "").lower()
        if "میلیون" in unit:
            n *= 1_000_000
        elif "هزار" in unit:
            n *= 1_000
        return int(n)

    nums = re.findall(r"(\d+(?:[.,]\d+)?)\s*(میلیون|هزار)?", lower)
    values = [amount(n, u) for n, u in nums]
    values = [v for v in values if v is not None and v > 0]
    min_price = max_price = None
    if values:
        if len(values) >= 2 and re.search(r"(بین|از).*?(تا|-)", lower):
            min_price, max_price = sorted(values[-2:])
        elif re.search(r"(زیر|کمتر از|حداکثر|تا)", lower):
            max_price = values[-1]
        elif re.search(r"(بالای|بیشتر از|حداقل|از)", lower):
            min_price = values[-1]
    cleaned = re.sub(r"(زیر|کمتر از|بیشتر از|بالای|حداکثر|حداقل|بین|میلیون|هزار|تومان|تا)", " ", raw)
    cleaned = re.sub(r"\d+(?:[.,]\d+)?", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return {"original": value or "", "query": cleaned, "min_price": min_price, "max_price": max_price}

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    q = request.args.get("q", "").strip()
    intent = parse_search_intent(q)
    # If the query is price-only (for example «زیر ۵ میلیون»),
    # the price intent should filter the catalog instead of becoming a text query.
    search_q = intent["query"]
    sort = request.args.get("sort", "newest").strip()
    category_id = request.args.get("category", "").strip()

    query = Product.query.filter_by(active=True)

    if search_q:
        search = f"%{search_q}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search),
                Product.description.ilike(search),
                Product.category.has(Category.name.ilike(search)),
            )
        )

    if category_id:
        try:
            query = query.filter(Product.category_id == int(category_id))
        except ValueError:
            category_id = ""

    products = query.all()
    if intent["min_price"] is not None or intent["max_price"] is not None:
        products = [p for p in products if (intent["min_price"] is None or lowest_price(p) >= intent["min_price"]) and (intent["max_price"] is None or lowest_price(p) <= intent["max_price"])]

    # Sort by the effective price shown to users, not the stale base price.
    if sort == "price_low":
        products.sort(key=lambda item: (lowest_price(item), -item.id))
    elif sort == "price_high":
        products.sort(key=lambda item: (-lowest_price(item), -item.id))
    elif sort == "name":
        products.sort(key=lambda item: item.name.lower())
    else:
        sort = "newest"
        products.sort(key=lambda item: item.id, reverse=True)

    categories = (
        Category.query
        .filter_by(active=True)
        .order_by(Category.id.asc())
        .all()
    )

    stores = (
        Store.query
        .filter_by(active=True)
        .order_by(Store.name.asc())
        .all()
    )

    # Homepage vehicle showcase: only approved ads, newest first.
    vehicle_ads = (
        VehicleAd.query
        .filter_by(status="approved")
        .order_by(VehicleAd.id.desc())
        .limit(16)
        .all()
    )

    selected_category = None
    if category_id:
        selected_category = db.session.get(Category, int(category_id))

    return render_template(
        "index.html",
        products=products,
        categories=categories,
        stores=stores,
        q=q,
        search_intent=intent,
        sort=sort,
        category_id=category_id,
        selected_category=selected_category,
        lowest_price=lowest_price,
        vehicle_ads=vehicle_ads
    )


# =========================================================
# CATALOG
# =========================================================

@app.route("/products")
def catalog_products():
    """Display the complete active product catalog with one consistent filter model."""
    q = request.args.get("q", "").strip()[:100]
    intent = parse_search_intent(q)
    # If the query is price-only (for example «زیر ۵ میلیون»),
    # the price intent should filter the catalog instead of becoming a text query.
    search_q = intent["query"]
    sort = request.args.get("sort", "newest").strip()
    category_id = request.args.get("category", "").strip()

    try:
        min_price = max(0, int(request.args.get("min_price", "0") or 0))
        max_price = max(0, int(request.args.get("max_price", "0") or 0))
    except (TypeError, ValueError):
        min_price = max_price = 0

    if min_price and max_price and min_price > max_price:
        min_price, max_price = max_price, min_price

    query = Product.query.filter(Product.active.is_(True))

    if search_q:
        search = f"%{search_q}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search),
                Product.description.ilike(search),
                Product.category.has(Category.name.ilike(search)),
            )
        )

    if category_id:
        try:
            query = query.filter(Product.category_id == int(category_id))
        except (TypeError, ValueError):
            category_id = ""

    products = query.all()

    # Keep natural-language price intent and explicit toolbar filters compatible.
    effective_min = intent["min_price"] if intent["min_price"] is not None else min_price
    effective_max = intent["max_price"] if intent["max_price"] is not None else max_price
    if effective_min is not None or effective_max is not None:
        products = [
            p for p in products
            if (effective_min in (None, 0) or lowest_price(p) >= effective_min)
            and (effective_max in (None, 0) or lowest_price(p) <= effective_max)
        ]

    if sort == "price_low":
        products.sort(key=lambda item: (lowest_price(item), -item.id))
    elif sort == "price_high":
        products.sort(key=lambda item: (-lowest_price(item), -item.id))
    elif sort == "name":
        products.sort(key=lambda item: item.name.lower())
    else:
        sort = "newest"
        products.sort(key=lambda item: item.id, reverse=True)

    categories = (
        Category.query
        .filter_by(active=True)
        .order_by(Category.id.asc())
        .all()
    )

    selected_category = None
    if category_id.isdigit():
        selected_category = db.session.get(Category, int(category_id))

    return render_template(
        "catalog_products.html",
        products=products,
        categories=categories,
        q=q,
        search_intent=intent,
        sort=sort,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        selected_category=selected_category,
        lowest_price=lowest_price,
    )


@app.get("/api/catalog/search")
def api_catalog_search():
    """Small, fast autocomplete endpoint used by the global header search."""
    q = normalize_search_text(request.args.get("q", ""))[:100]
    try:
        limit = max(1, min(10, int(request.args.get("per_page", "7") or 7)))
    except (TypeError, ValueError):
        limit = 7

    if len(q) < 2:
        return jsonify({"items": []})

    needle = f"%{q}%"
    products = (
        Product.query
        .filter(
            Product.active.is_(True),
            db.or_(
                Product.name.ilike(needle),
                Product.description.ilike(needle),
                Product.category.has(Category.name.ilike(needle)),
            ),
        )
        .order_by(Product.id.desc())
        .limit(limit)
        .all()
    )

    return jsonify({
        "items": [
            {
                "id": product.id,
                "name": product.name,
                "price": lowest_price(product),
                "url": url_for("product_detail", product_id=product.id),
            }
            for product in products
        ]
    })


# =========================================================
# CATEGORY
# =========================================================

@app.route(
    "/category/<int:category_id>"
)
def category(category_id):

    cat = Category.query.get_or_404(category_id)

    sort = request.args.get("sort", "newest").strip()
    store_id = request.args.get("store", "").strip()
    q = request.args.get("q", "").strip()[:100]

    try:
        min_price = max(0, int(request.args.get("min_price", "0") or 0))
        max_price = max(0, int(request.args.get("max_price", "0") or 0))
    except (TypeError, ValueError):
        min_price = max_price = 0

    if min_price and max_price and min_price > max_price:
        min_price, max_price = max_price, min_price

    query = Product.query.filter(
        Product.category_id == cat.id,
        Product.active.is_(True),
    )

    if q:
        needle = f"%{q}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(needle),
                Product.description.ilike(needle),
            )
        )

    products = query.all()
    selected_store = db.session.get(Store, int(store_id)) if store_id.isdigit() else None

    # Filter using the same effective price users see on product cards.
    filtered = []
    for product in products:
        if store_id.isdigit():
            if not selected_store or not selected_store.active:
                continue
            matching = [
                offer for offer in product.offers
                if offer.store_id == selected_store.id
                and offer.in_stock
                and offer.price
                and offer.price > 0
            ]
            if not matching:
                continue

        effective = lowest_price(product)
        if min_price and effective < min_price:
            continue
        if max_price and effective > max_price:
            continue
        filtered.append(product)

    if sort == "price_low":
        filtered.sort(key=lambda item: (lowest_price(item), -item.id))
    elif sort == "price_high":
        filtered.sort(key=lambda item: (-lowest_price(item), -item.id))
    elif sort == "name":
        filtered.sort(key=lambda item: item.name.lower())
    else:
        sort = "newest"
        filtered.sort(key=lambda item: item.id, reverse=True)

    store_options = (
        Store.query
        .filter_by(active=True)
        .order_by(Store.name.asc())
        .all()
    )

    return render_template(
        "category.html",
        category=cat,
        products=filtered,
        sort=sort,
        q=q,
        store_id=store_id,
        min_price=min_price,
        max_price=max_price,
        store_options=store_options,
        lowest_price=lowest_price,
    )


# =========================================================
# PRICE ALERT
# =========================================================

@app.post("/product/<int:product_id>/price-alert")
@login_required
def create_price_alert(product_id):
    product = Product.query.get_or_404(product_id)
    raw = request.form.get("target_price", "").strip().replace(",", "").replace("٬", "")
    try:
        target = int(normalize_search_text(raw))
    except (TypeError, ValueError):
        target = 0
    if target <= 0:
        flash("قیمت هدف معتبر وارد کن.", "warning")
        return redirect(url_for("product_detail", product_id=product.id) + "#price-alert")

    user_id = session["user_id"]
    alert = PriceAlert.query.filter_by(user_id=user_id, product_id=product.id).first()
    if alert:
        alert.target_price = target
        alert.active = True
    else:
        db.session.add(PriceAlert(user_id=user_id, product_id=product.id, target_price=target, active=True))
    db.session.commit()
    flash("هشدار قیمت برای این محصول فعال شد. 🔔", "success")
    return redirect(url_for("product_detail", product_id=product.id) + "#price-alert")


@app.post("/product/<int:product_id>/price-alert/remove")
@login_required
def remove_price_alert(product_id):
    alert = PriceAlert.query.filter_by(user_id=session["user_id"], product_id=product_id).first()
    if alert:
        alert.active = False
        db.session.commit()
    flash("هشدار قیمت غیرفعال شد.", "success")
    return redirect(url_for("product_detail", product_id=product_id) + "#price-alert")


# =========================================================
# PRODUCT
# =========================================================

@app.route(
    "/product/<int:product_id>",
    methods=["GET", "POST"]
)
def product_detail(product_id):

    # -----------------------------------------------------
    # PRODUCT
    # -----------------------------------------------------

    product = Product.query.get_or_404(
        product_id
    )

    # -----------------------------------------------------
    # REVIEW
    # -----------------------------------------------------

    if request.method == "POST":

        if not session.get("user_id"):

            flash(
                "برای ثبت نظر ابتدا وارد شوید.",
                "warning"
            )

            return redirect(
                url_for(
                    "login",
                    next=request.path
                )
            )

        try:

            rating = int(
                request.form.get(
                    "rating",
                    5
                )
            )

        except (
            TypeError,
            ValueError
        ):

            rating = 5

        rating = max(
            1,
            min(
                5,
                rating
            )
        )

        text = request.form.get(
            "text",
            ""
        ).strip()

        if text:

            review = Review.query.filter_by(
                product_id=product.id,
                user_id=session["user_id"]
            ).first()

            if review:
                review.rating = rating
                review.text = text
            else:
                review = Review(
                    product_id=product.id,
                    user_id=session["user_id"],
                    rating=rating,
                    text=text
                )
                db.session.add(review)

            db.session.commit()

            flash(
                "نظر شما با موفقیت ثبت شد. ⭐",
                "success"
            )

        return redirect(
            url_for(
                "product_detail",
                product_id=product.id
            )
        )

    # -----------------------------------------------------
    # PRODUCT OFFERS
    # -----------------------------------------------------
    #
    # فقط Offerهای:
    # - مربوط به همین محصول
    # - موجود
    # - دارای فروشگاه
    # - فروشگاه فعال
    #
    # -----------------------------------------------------

    offers = (
        Offer.query
        .join(
            Store,
            Offer.store_id == Store.id
        )
        .filter(
            Offer.product_id == product.id,
            Offer.in_stock.is_(True),
            Store.active.is_(True)
        )
        .order_by(
            Offer.price.asc(),
            Offer.id.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # LOWEST PRICE
    # -----------------------------------------------------

    if offers:

        valid_prices = []

        for offer in offers:

            try:

                price = int(
                    offer.price
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            if price > 0:
                valid_prices.append(
                    price
                )

        if valid_prices:

            lowest = min(
                valid_prices
            )

        else:

            lowest = int(
                product.price or 0
            )

    else:

        lowest = int(
            product.price or 0
        )

    # -----------------------------------------------------
    # RATING
    # -----------------------------------------------------

    rating = product_rating(
        product
    )

    price_alert = None
    if session.get("user_id"):
        price_alert = PriceAlert.query.filter_by(
            user_id=session["user_id"],
            product_id=product.id,
            active=True,
        ).first()

    related_products = (
        Product.query
        .filter(
            Product.active.is_(True),
            Product.id != product.id,
            Product.category_id == product.category_id,
        )
        .order_by(Product.id.desc())
        .limit(8)
        .all()
    )

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render_template(
        "product.html",
        product=product,
        offers=offers,
        lowest_price=lowest,
        rating=rating,
        price_alert=price_alert,
        related_products=related_products
    )

# =========================================================
# DELETE REVIEW
# =========================================================

@app.post(
    "/review/delete/<int:review_id>"
)
@login_required
def delete_review(review_id):

    review = Review.query.get_or_404(
        review_id
    )

    user = db.session.get(
        User,
        session["user_id"]
    )

    if (
        review.user_id != user.id
        and user.role != "admin"
    ):

        abort(403)

    product_id = review.product_id

    db.session.delete(
        review
    )

    db.session.commit()

    flash(
        "نظر حذف شد.",
        "success"
    )

    return redirect(
        url_for(
            "product_detail",
            product_id=product_id
        )
    )


# =========================================================
# PRODUCT COMPARISON
# =========================================================

@app.post("/compare/add/<int:product_id>")
def compare_add(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.active:
        abort(404)

    ids = session.get("compare", [])
    if not isinstance(ids, list):
        ids = []

    ids = [int(x) for x in ids if str(x).isdigit()]

    if product.id not in ids:
        if len(ids) >= 4:
            flash("حداکثر ۴ محصول را می‌توانی همزمان مقایسه کنی.", "warning")
        else:
            ids.append(product.id)
            flash(f"{product.name} به مقایسه اضافه شد.", "success")

    session["compare"] = ids
    session.modified = True

    fallback = url_for("home")
    target = safe_local_redirect(request.form.get("next"), fallback)
    if target == fallback and request.referrer:
        target = safe_local_redirect(request.referrer, fallback)
    return redirect(target)


@app.post("/compare/remove/<int:product_id>")
def compare_remove(product_id):
    ids = session.get("compare", [])
    if not isinstance(ids, list):
        ids = []

    session["compare"] = [int(x) for x in ids if str(x).isdigit() and int(x) != product_id]
    session.modified = True
    return redirect(request.referrer or url_for("compare"))


@app.route("/compare")
def compare():
    raw_ids = session.get("compare", [])
    if not isinstance(raw_ids, list):
        raw_ids = []

    ids = []
    for value in raw_ids:
        try:
            value = int(value)
            if value not in ids:
                ids.append(value)
        except (TypeError, ValueError):
            pass

    products = []
    for pid in ids[:4]:
        product = Product.query.get(pid)
        if product and product.active:
            products.append(product)

    session["compare"] = [p.id for p in products]
    session.modified = True

    return render_template(
        "compare.html",
        products=products,
        lowest_price=lowest_price
    )


# =========================================================
# FAVORITES
# =========================================================

@app.post(
    "/favorite/<int:product_id>"
)
@login_required
def toggle_favorite(product_id):

    Product.query.get_or_404(
        product_id
    )

    user_id = session["user_id"]

    favorite = Favorite.query.filter_by(
        user_id=user_id,
        product_id=product_id
    ).first()

    if favorite:

        db.session.delete(
            favorite
        )

        message = (
            "محصول از علاقه‌مندی‌ها حذف شد."
        )

    else:

        db.session.add(
            Favorite(
                user_id=user_id,
                product_id=product_id
            )
        )

        message = (
            "محصول به علاقه‌مندی‌ها اضافه شد. ❤️"
        )

    db.session.commit()

    flash(
        message,
        "success"
    )

    return redirect(
        request.referrer
        or url_for("home")
    )


@app.route("/favorites")
@login_required
def favorites():

    favorites = (
        Favorite.query
        .filter_by(
            user_id=session["user_id"]
        )
        .order_by(
            Favorite.id.desc()
        )
        .all()
    )

    products = [

        item.product

        for item in favorites

        if item.product
        and item.product.active

    ]

    return render_template(
        "favorites.html",
        products=products,
        lowest_price=lowest_price
    )


# =========================================================
# SELLER REGISTRATION
# =========================================================

@app.route("/seller/register", methods=["GET", "POST"])
def seller_register():
    """
    Keep the seller-registration entry point available.

    The current application does not yet expose the merchant-account workflow
    required by the dedicated seller_register template, so route the user into
    the existing account-registration flow instead of allowing Jinja's
    url_for('seller_register') to raise a BuildError.
    """
    return redirect(url_for("register"))


# =========================================================
# STORES
# =========================================================

@app.route("/stores")
def stores():

    stores = (
        Store.query
        .filter_by(active=True)
        .order_by(Store.name.asc())
        .all()
    )

    return render_template(
        "stores.html",
        stores=stores
    )


@app.route(
    "/store/<int:store_id>"
)
def store_detail(store_id):

    store = Store.query.get_or_404(
        store_id
    )

    offers = (
        Offer.query
        .filter_by(
            store_id=store.id
        )
        .join(Product)
        .filter(
            Product.active == True
        )
        .order_by(
            Offer.price.asc()
        )
        .all()
    )

    return render_template(
        "store.html",
        store=store,
        offers=offers
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("نام، ایمیل و رمز عبور حداقل ۸ کاراکتری الزامی است.", "warning")
            return render_template("auth.html", mode="register")

        if User.query.filter_by(email=email).first():
            flash("این ایمیل قبلاً ثبت شده است.", "warning")
            return render_template("auth.html", mode="register")

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role="user",
        )
        db.session.add(user)
        db.session.commit()

        session["user_id"] = user.id
        session.modified = True
        flash("حساب کاربری با موفقیت ساخته شد. خوش آمدی 👋", "success")
        return redirect(url_for("home"))

    return render_template("auth.html", mode="register")


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            user
            and check_password_hash(
                user.password,
                password
            )
        ):

            # =================================================
            # حفظ سبد خرید قبل از پاک کردن Session
            # =================================================

            old_cart = session.get(
                "cart",
                {}
            )

            if not isinstance(
                old_cart,
                dict
            ):

                old_cart = {}

            # =================================================
            # پاک کردن Session قبلی
            # =================================================

            # توکن CSRF را بین ورود کاربر و فرم‌هایی که در تب دیگری باز هستند
            # حفظ می‌کنیم تا ورود در یک تب باعث خراب شدن فرم سازمانی/سفارش در تب دیگر نشود.
            preserved_csrf = session.get("csrf_token")

            session.clear()

            # =================================================
            # ایجاد Session جدید
            # =================================================

            session["user_id"] = user.id
            session["csrf_token"] = preserved_csrf or secrets.token_urlsafe(32)

            # حفظ سبد خرید قبلی
            session["cart"] = old_cart

            session.modified = True

            # =================================================
            # پیام ورود
            # =================================================

            flash(
                "خوش آمدی 👋",
                "success"
            )

            # =================================================
            # NEXT PAGE
            # =================================================

            next_page = request.args.get(
                "next",
                ""
            ).strip()

            if (
                next_page
                and next_page.startswith("/")
                and not next_page.startswith("//")
            ):

                return redirect(
                    next_page
                )

            # =================================================
            # ADMIN
            # =================================================

            if user.role == "admin":

                return redirect(
                    url_for("admin")
                )

            # =================================================
            # USER
            # =================================================

            return redirect(
                url_for("home")
            )

        # =====================================================
        # LOGIN FAILED
        # =====================================================

        flash(
            "ایمیل یا رمز عبور اشتباه است.",
            "danger"
        )

    return render_template(
        "auth.html",
        mode="login"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.post("/logout")
def logout():

    # سبد خرید را قبل از خروج حفظ می‌کنیم
    old_cart = session.get(
        "cart",
        {}
    )

    if not isinstance(
        old_cart,
        dict
    ):

        old_cart = {}

    session.clear()

    # سبد خرید حتی بعد از خروج هم باقی بماند
    session["cart"] = old_cart

    session.modified = True

    return redirect(
        url_for("home")
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
@login_required
def profile():

    return render_template(
        "profile.html"
    )


@app.route("/profile/settings", methods=["GET", "POST"])
@login_required
def profile_settings():
    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not check_password_hash(user.password, current_password):
                flash("رمز عبور فعلی اشتباه است.", "danger")
            elif len(new_password) < 8:
                flash("رمز عبور جدید باید حداقل ۸ کاراکتر باشد.", "warning")
            elif new_password != confirm_password:
                flash("تکرار رمز عبور با رمز جدید یکسان نیست.", "warning")
            elif check_password_hash(user.password, new_password):
                flash("رمز عبور جدید نباید با رمز فعلی یکسان باشد.", "warning")
            else:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                session.clear()
                flash("رمز عبور با موفقیت تغییر کرد. لطفاً دوباره وارد حساب شوید.", "success")
                return redirect(url_for("login"))

        elif action == "email_send":
            new_email = request.form.get("new_email", "").strip().lower()
            if not new_email or "@" not in new_email or "." not in new_email.rsplit("@", 1)[-1]:
                flash("یک ایمیل معتبر وارد کنید.", "warning")
            elif new_email == user.email.lower():
                flash("این ایمیل همین حالا روی حساب شما ثبت شده است.", "info")
            elif User.query.filter(db.func.lower(User.email) == new_email).first():
                flash("این ایمیل قبلاً برای یک حساب دیگر ثبت شده است.", "danger")
            else:
                pending = AccountEmailChange.query.filter_by(user_id=user.id).first()
                now = datetime.utcnow()
                if pending and pending.sent_at and now - pending.sent_at < timedelta(seconds=60):
                    flash("برای ارسال دوباره کد، کمی صبر کنید.", "warning")
                else:
                    code = f"{secrets.randbelow(1000000):06d}"
                    if send_kharidino_email(
                        new_email,
                        "کد تأیید تغییر ایمیل خریدینو",
                        f"کد تأیید تغییر ایمیل خریدینو: {code}\nاین کد 10 دقیقه اعتبار دارد.\nاگر این درخواست از طرف شما نبوده، آن را نادیده بگیرید.",
                    ):
                        if not pending:
                            pending = AccountEmailChange(user_id=user.id, pending_email=new_email)
                            db.session.add(pending)
                        pending.pending_email = new_email
                        pending.code_hash = generate_password_hash(code)
                        pending.expires_at = now + timedelta(minutes=10)
                        pending.sent_at = now
                        db.session.commit()
                        flash("کد تأیید به ایمیل جدید ارسال شد.", "success")
                    else:
                        flash("ارسال کد انجام نشد. تنظیمات SMTP را بررسی کنید.", "danger")

        elif action == "email_confirm":
            code = request.form.get("code", "").strip()
            pending = AccountEmailChange.query.filter_by(user_id=user.id).first()
            now = datetime.utcnow()
            if (
                not pending
                or not pending.code_hash
                or not pending.expires_at
                or pending.expires_at < now
                or not check_password_hash(pending.code_hash, code)
            ):
                flash("کد تأیید ایمیل نامعتبر یا منقضی شده است.", "danger")
            elif User.query.filter(
                db.func.lower(User.email) == pending.pending_email.lower(),
                User.id != user.id,
            ).first():
                flash("این ایمیل در این فاصله توسط حساب دیگری ثبت شده است.", "danger")
            else:
                user.email = pending.pending_email
                db.session.delete(pending)
                db.session.commit()
                flash("ایمیل حساب با موفقیت تغییر کرد.", "success")

        else:
            flash("درخواست نامعتبر است.", "warning")

        return redirect(url_for("profile_settings"))

    pending = AccountEmailChange.query.filter_by(user_id=user.id).first()
    return render_template("profile_settings.html", pending_email=pending.pending_email if pending else "")


# =========================================================
# STATIC PAGES
# =========================================================

@app.route("/about")
def about():

    return render_template(
        "about.html"
    )


@app.route("/features")
def features():

    return render_template(
        "features.html"
    )


@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        flash(
            "پیامت دریافت شد؛ به‌زودی با شما تماس می‌گیریم.",
            "success"
        )

        return redirect(
            url_for("contact")
        )

    return render_template(
        "contact.html"
    )


# =========================================================
# CART
# =========================================================

def cart_data():

    raw = session.get(
        "cart",
        {}
    )

    # اگر Session خراب باشد
    if not isinstance(
        raw,
        dict
    ):

        raw = {}

    result = []

    total = 0

    # سبد تمیز
    clean_cart = {}

    for pid, qty in raw.items():

        try:

            product_id = int(pid)

            quantity = int(qty)

        except (
            ValueError,
            TypeError
        ):

            continue

        # =================================================
        # محدود کردن تعداد
        # =================================================

        quantity = max(
            0,
            min(99, quantity)
        )

        # تعداد صفر = حذف
        if quantity <= 0:
            continue

        # =================================================
        # دریافت محصول
        # =================================================

        product = db.session.get(
            Product,
            product_id
        )

        # محصول باید وجود داشته باشد و فعال باشد
        if (
            not product
            or not product.active
        ):

            continue

        # =================================================
        # قیمت فعلی
        # =================================================

        price = lowest_price(
            product
        )

        subtotal = (
            price * quantity
        )

        # =================================================
        # ذخیره سبد تمیز
        # =================================================

        clean_cart[
            str(product_id)
        ] = quantity

        result.append({

            "product": product,

            "quantity": quantity,

            "price": price,

            "subtotal": subtotal

        })

        total += subtotal

    # =====================================================
    # پاکسازی Session
    # =====================================================

    if clean_cart != raw:

        session["cart"] = clean_cart

        session.modified = True

    return result, total


# =========================================================
# SHOW CART
# =========================================================

@app.route("/cart")
def cart():

    items, total = cart_data()

    return render_template(
        "cart.html",
        items=items,
        total=total
    )


# =========================================================
# ADD TO CART
# =========================================================

@app.post(
    "/cart/add/<int:product_id>"
)
def cart_add(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    # محصول غیرفعال
    if not product.active:

        abort(404)

    cart = session.get(
        "cart",
        {}
    )

    if not isinstance(
        cart,
        dict
    ):

        cart = {}

    key = str(
        product.id
    )

    # =================================================
    # تعداد فعلی
    # =================================================

    try:

        current_quantity = int(
            cart.get(
                key,
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):

        current_quantity = 0

    # =================================================
    # حداکثر 99 عدد
    # =================================================

    cart[key] = min(
        current_quantity + 1,
        99
    )

    # =================================================
    # ذخیره Session
    # =================================================

    session["cart"] = cart

    session.modified = True

    flash(
        f"{product.name} به سبد خرید اضافه شد. 🛒",
        "success"
    )

    return redirect(
        request.referrer
        or url_for("cart")
    )


# =========================================================
# UPDATE CART
# =========================================================

@app.post(
    "/cart/update"
)
def cart_update():

    new_cart = {}

    # =====================================================
    # دریافت تمام qty ها
    # =====================================================

    for key, value in request.form.items():

        if not key.startswith(
            "qty_"
        ):

            continue

        try:

            # مثال:
            # qty_15
            #
            # نتیجه:
            # 15

            product_id = int(
                key[4:]
            )

            quantity = int(
                value
            )

        except (
            ValueError,
            TypeError
        ):

            continue

        # =================================================
        # محدود کردن تعداد
        # =================================================

        quantity = max(
            0,
            min(99, quantity)
        )

        # تعداد صفر یعنی حذف
        if quantity <= 0:

            continue

        # =================================================
        # بررسی محصول
        # =================================================

        product = db.session.get(
            Product,
            product_id
        )

        if (
            product
            and product.active
        ):

            new_cart[
                str(product_id)
            ] = quantity

    # =====================================================
    # ذخیره سبد جدید
    # =====================================================

    session["cart"] = new_cart

    session.modified = True

    # =====================================================
    # رفتن به Checkout
    # =====================================================

    if request.form.get(
        "go_to_checkout"
    ) == "1":

        # اگر سبد خالی شد
        if not new_cart:

            flash(
                "سبد خرید شما خالی است.",
                "warning"
            )

            return redirect(
                url_for("cart")
            )

        return redirect(
            url_for("checkout")
        )

    # =====================================================
    # بروزرسانی عادی
    # =====================================================

    flash(
        "سبد خرید با موفقیت به‌روزرسانی شد. 🛒",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =========================================================
# REMOVE PRODUCT FROM CART
# =========================================================

@app.post(
    "/cart/remove/<int:product_id>"
)
def cart_remove(product_id):

    cart = session.get(
        "cart",
        {}
    )

    if not isinstance(
        cart,
        dict
    ):

        cart = {}

    # =====================================================
    # حذف محصول
    # =====================================================

    cart.pop(
        str(product_id),
        None
    )

    # =====================================================
    # ذخیره Session
    # =====================================================

    session["cart"] = cart

    session.modified = True

    flash(
        "محصول از سبد خرید حذف شد. 🗑️",
        "success"
    )

    return redirect(
        url_for("cart")
    )


# =========================================================
# CHECKOUT
# =========================================================

@app.route(
    "/checkout",
    methods=["GET", "POST"]
)
@login_required
def checkout():

    # =====================================================
    # دریافت اطلاعات سبد
    # =====================================================

    items, total = cart_data()

    # =====================================================
    # سبد خالی
    # =====================================================

    if not items:

        flash(
            "سبد خرید شما خالی است.",
            "warning"
        )

        return redirect(
            url_for("cart")
        )

    # =====================================================
    # ثبت سفارش
    # =====================================================

    checkout_nonce = session.get("checkout_nonce")

    if request.method == "GET" or not checkout_nonce:
        checkout_nonce = secrets.token_urlsafe(24)
        session["checkout_nonce"] = checkout_nonce

    if request.method == "POST":

        submitted_nonce = request.form.get("checkout_nonce", "")
        if not submitted_nonce or not checkout_nonce or not secrets.compare_digest(
            str(submitted_nonce), str(checkout_nonce)
        ):
            flash("این فرم قبلاً ثبت شده یا منقضی شده است. لطفاً دوباره تلاش کن.", "warning")
            return redirect(url_for("checkout"))

        name = request.form.get("customer_name", "").strip()[:120]
        phone = normalize_search_text(request.form.get("phone", "")).strip()[:30]
        address = request.form.get("address", "").strip()[:2000]
        note = request.form.get("note", "").strip()[:2000]

        # نام، آدرس و شماره تماس را قبل از ساخت سفارش اعتبارسنجی می‌کنیم.
        phone_digits = "".join(ch for ch in phone if ch.isdigit())
        if (
            not name
            or not address
            or len(phone_digits) < 10
            or len(phone_digits) > 15
        ):
            flash("نام، شماره تماس معتبر و آدرس کامل الزامی است.", "warning")
            return render_template(
                "checkout.html",
                items=items,
                total=total,
                checkout_nonce=checkout_nonce,
            )

        # =================================================
        # ایجاد سفارش
        # =================================================

        order = Order(

            user_id=session["user_id"],

            total=total,

            customer_name=name,

            phone=phone,

            address=address,

            note=note,

            status="در انتظار بررسی"

        )

        db.session.add(
            order
        )

        # =================================================
        # ایجاد آیتم‌های سفارش
        # =================================================

        for row in items:

            db.session.add(

                OrderItem(

                    order=order,

                    product_id=row["product"].id,

                    product_name=row["product"].name,

                    price=row["price"],

                    quantity=row["quantity"]

                )

            )

        # =================================================
        # ذخیره سفارش
        # =================================================

        db.session.commit()

        # =================================================
        # پاک کردن سبد بعد از ثبت موفق
        # =================================================

        session["cart"] = {}
        session.pop("checkout_nonce", None)
        session.modified = True

        flash(
            "سفارش شما با موفقیت ثبت شد. 💙",
            "success"
        )

        return redirect(
            url_for("my_orders")
        )

    # =====================================================
    # نمایش Checkout
    # =====================================================

    return render_template(
        "checkout.html",
        items=items,
        total=total,
        checkout_nonce=checkout_nonce,
    )


# =========================================================
# ORDERS
# =========================================================

@app.route("/orders")
@login_required
def my_orders():

    orders = (
        Order.query
        .filter_by(
            user_id=session["user_id"]
        )
        .order_by(
            Order.id.desc()
        )
        .all()
    )

    return render_template(
        "orders.html",
        orders=orders
    )



# =========================================================
# ORGANIZATIONS / B2B
# =========================================================
@app.route("/organizations")
def organizations():
    return render_template("organizations.html")


@app.post("/organizations/request")
def organization_request():
    company_name = request.form.get("company_name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    if not company_name or not contact_name:
        flash("نام سازمان و نام شخص رابط الزامی است.", "warning")
        return redirect(url_for("organizations"))
    inquiry = OrganizationRequest(
        company_name=company_name,
        national_id=request.form.get("national_id", "").strip(),
        economic_code=request.form.get("economic_code", "").strip(),
        registration_number=request.form.get("registration_number", "").strip(),
        postal_code=request.form.get("postal_code", "").strip(),
        phone=request.form.get("phone", "").strip(),
        address=request.form.get("address", "").strip(),
        contact_name=contact_name,
        contact_email=request.form.get("contact_email", "").strip(),
        contract_subject=request.form.get("contract_subject", "").strip(),
        estimated_value=request.form.get("estimated_value", "").strip(),
        payment_terms=request.form.get("payment_terms", "").strip(),
        invoice_required=bool(request.form.get("invoice_required")),
        message=request.form.get("message", "").strip(),
    )
    db.session.add(inquiry)
    db.session.commit()

    tracking_code = f"KHD-ORG-{inquiry.id:06d}"
    admin_email = os.environ.get("KHARIDINO_ADMIN_NOTIFICATION_EMAIL", "").strip()
    customer_body = (
        f"درخواست سازمانی شما با کد پیگیری {tracking_code} ثبت شد.\\n\\n"
        "واحد فروش خریدینو درخواست شما را بررسی خواهد کرد."
    )
    if inquiry.contact_email:
        send_kharidino_email(
            inquiry.contact_email,
            f"ثبت درخواست سازمانی خریدینو | {tracking_code}",
            customer_body,
        )
    if admin_email:
        send_kharidino_email(
            admin_email,
            f"درخواست سازمانی جدید | {tracking_code} | {inquiry.company_name}",
            f"درخواست جدیدی در خریدینو ثبت شد.\\nکد پیگیری: {tracking_code}\\nسازمان: {inquiry.company_name}\\nرابط: {inquiry.contact_name}\\nتلفن: {inquiry.phone}\\nایمیل: {inquiry.contact_email}\\nموضوع: {inquiry.contract_subject}\\nفاکتور: {'بله' if inquiry.invoice_required else 'خیر'}",
        )

    flash(f"درخواست همکاری سازمانی ثبت شد. کد پیگیری شما: {tracking_code}", "success")
    return redirect(url_for("organizations"))


def _company_profile():
    return {
        "legal_name": setting("company_legal_name", setting("site_name", "خریدینو")),
        "national_id": setting("company_national_id", ""),
        "economic_code": setting("company_economic_code", ""),
        "registration_number": setting("company_registration_number", ""),
        "postal_code": setting("company_postal_code", ""),
        "phone": setting("company_phone", ""),
        "address": setting("company_address", ""),
        "website": setting("company_website", ""),
        "email": setting("company_email", ""),
        "bank_name": setting("company_bank_name", ""),
        "iban": setting("company_iban", ""),
    }


@app.route("/admin/business-profile", methods=["GET", "POST"])
@admin_required
def admin_business_profile():
    fields = {
        "company_legal_name": "نام حقوقی شرکت",
        "company_national_id": "شناسه ملی",
        "company_economic_code": "شماره اقتصادی",
        "company_registration_number": "شماره ثبت",
        "company_postal_code": "کد پستی",
        "company_phone": "تلفن",
        "company_address": "نشانی",
        "company_website": "وب‌سایت",
        "company_email": "ایمیل",
        "company_bank_name": "نام بانک",
        "company_iban": "شماره شبا",
    }
    if request.method == "POST":
        for key in fields:
            set_setting(key, request.form.get(key, "").strip())
        db.session.commit()
        flash("اطلاعات حقوقی و صدور فاکتور ذخیره شد.", "success")
        return redirect(url_for("admin_business_profile"))
    return render_template("admin_business_profile.html", fields=fields, profile=_company_profile())


@app.route("/orders/<int:order_id>/invoice")
@login_required
def order_invoice(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.user_id != session["user_id"]:
        abort(404)
    invoice = Invoice.query.filter_by(order_id=order.id).first()
    if not invoice:
        invoice = Invoice(
            order_id=order.id,
            invoice_number=f"KH-{datetime.utcnow().strftime('%Y%m%d')}-{order.id:06d}",
            buyer_name=order.customer_name,
            buyer_phone=order.phone,
            buyer_address=order.address,
            subtotal=order.total,
            total=order.total,
            status="پیش‌نویس",
        )
        db.session.add(invoice)
        db.session.commit()
    return render_template("invoice.html", invoice=invoice, order=order, company=_company_profile())


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/organization-requests")
@admin_required
def admin_organization_requests():
    status_filter = request.args.get("status", "").strip()
    allowed_statuses = [
        "در انتظار بررسی",
        "در حال پیگیری",
        "تکمیل شد",
        "رد شد",
    ]

    query = OrganizationRequest.query.order_by(OrganizationRequest.id.desc())
    if status_filter in allowed_statuses:
        query = query.filter_by(status=status_filter)
    else:
        status_filter = ""

    requests = query.all()
    counts = {
        "all": OrganizationRequest.query.count(),
        "pending": OrganizationRequest.query.filter_by(status="در انتظار بررسی").count(),
        "tracking": OrganizationRequest.query.filter_by(status="در حال پیگیری").count(),
        "completed": OrganizationRequest.query.filter_by(status="تکمیل شد").count(),
        "rejected": OrganizationRequest.query.filter_by(status="رد شد").count(),
    }

    return render_template(
        "admin_organization_requests.html",
        requests=requests,
        counts=counts,
        status_filter=status_filter,
        allowed_statuses=allowed_statuses,
    )


@app.post("/admin/organization-requests/<int:request_id>/status")
@admin_required
def admin_organization_request_status(request_id):
    inquiry = db.session.get(OrganizationRequest, request_id)
    if not inquiry:
        abort(404)

    allowed_statuses = {
        "در انتظار بررسی",
        "در حال پیگیری",
        "تکمیل شد",
        "رد شد",
    }
    new_status = request.form.get("status", "").strip()
    if new_status not in allowed_statuses:
        flash("وضعیت انتخاب‌شده معتبر نیست.", "danger")
        return redirect(url_for("admin_organization_requests"))

    inquiry.status = new_status
    db.session.commit()

    tracking_code = f"KHD-ORG-{inquiry.id:06d}"
    if inquiry.contact_email:
        send_kharidino_email(
            inquiry.contact_email,
            f"به‌روزرسانی درخواست خریدینو | {tracking_code}",
            f"وضعیت درخواست سازمانی شما با کد {tracking_code} به «{new_status}» تغییر کرد.\\n\\nواحد فروش خریدینو در صورت نیاز با شما تماس خواهد گرفت.",
        )
    flash(f"وضعیت درخواست #{inquiry.id} به «{new_status}» تغییر کرد.", "success")
    return redirect(url_for("admin_organization_requests", status=request.args.get("status", "")))


@app.route("/admin")
@admin_required
def admin():

    q = request.args.get(
        "q",
        ""
    ).strip()

    if q:

        products = (
            Product.query
            .filter(
                Product.name.ilike(
                    f"%{q}%"
                )
            )
            .order_by(
                Product.id.desc()
            )
            .all()
        )

    else:

        products = (
            Product.query
            .order_by(
                Product.id.desc()
            )
            .all()
        )

    categories = (
        Category.query
        .order_by(
            Category.id.asc()
        )
        .all()
    )

    stores = (
        Store.query
        .order_by(
            Store.id.desc()
        )
        .all()
    )

    offers = (
        Offer.query
        .order_by(
            Offer.id.desc()
        )
        .all()
    )

    users = (
        User.query
        .order_by(
            User.id.desc()
        )
        .all()
    )

    orders = (
        Order.query
        .order_by(
            Order.id.desc()
        )
        .all()
    )

    orders_total = Order.query.count()
    pending_orders = Order.query.filter_by(status="در انتظار بررسی").count()
    completed_orders = Order.query.filter(Order.status.in_(["تکمیل شد", "تحویل شد"])).count()
    revenue = sum(int(o.total or 0) for o in Order.query.filter(Order.status != "لغو شد").all())
    out_of_stock_offers = Offer.query.filter_by(in_stock=False).count()
    active_users = User.query.filter_by(role="user").count()
    pending_org_requests = OrganizationRequest.query.filter_by(status="در انتظار بررسی").count()
    completion_rate = round((completed_orders / orders_total) * 100) if orders_total else 0
    recent_orders = orders[:6]

    stats = {
        "products": Product.query.count(),
        "categories": Category.query.count(),
        "stores": Store.query.count(),
        "offers": Offer.query.count(),
        "users": User.query.count(),
        "orders": orders_total,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "revenue": revenue,
        "out_of_stock_offers": out_of_stock_offers,
        "active_users": active_users,
        "pending_org_requests": pending_org_requests,
        "completion_rate": min(max(completion_rate, 0), 100),
    }

    return render_template(
        "admin.html",
        products=products,
        categories=categories,
        stores=stores,
        offers=offers,
        users=users,
        orders=orders,
        stats=stats,
        recent_orders=recent_orders,
        q=q
    )


# =========================================================
# ADMIN BACKGROUND
# =========================================================

@app.post(
    "/admin/background"
)
@admin_required
def admin_background():

    # -----------------------------------------------------
    # MODE
    # -----------------------------------------------------

    mode = request.form.get(
        "mode",
        "css"
    ).strip().lower()

    allowed_modes = {
        "css",
        "image",
        "gif",
        "video",
    }

    if mode not in allowed_modes:
        mode = "css"

    # -----------------------------------------------------
    # OVERLAY
    # -----------------------------------------------------

    try:

        overlay = float(
            request.form.get(
                "overlay",
                "0.45"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        overlay = 0.45

    overlay = max(
        0.0,
        min(0.9, overlay)
    )

    # -----------------------------------------------------
    # SPEED
    # -----------------------------------------------------

    try:

        speed = float(
            request.form.get(
                "speed",
                "18"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        speed = 18

    speed = max(
        1,
        min(120, speed)
    )

    # -----------------------------------------------------
    # BLUR
    # -----------------------------------------------------

    try:

        blur = float(
            request.form.get(
                "blur",
                "0"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        blur = 0

    blur = max(
        0,
        min(30, blur)
    )

    # -----------------------------------------------------
    # POSITION
    # -----------------------------------------------------

    allowed_positions = {

        "center",

        "center top",

        "center bottom",

        "left center",

        "right center",

        "left top",

        "right top",

        "left bottom",

        "right bottom",

    }

    position = request.form.get(
        "position",
        "center"
    ).strip()

    if position not in allowed_positions:
        position = "center"

    # -----------------------------------------------------
    # SIZE
    # -----------------------------------------------------

    allowed_sizes = {

        "cover",

        "contain",

        "100% 100%",

    }

    size = request.form.get(
        "size",
        "cover"
    ).strip()

    if size not in allowed_sizes:
        size = "cover"

    # -----------------------------------------------------
    # CURRENT BACKGROUND
    # -----------------------------------------------------

    old_background = setting(
        "background_media",
        ""
    )

    # -----------------------------------------------------
    # REMOVE?
    # -----------------------------------------------------

    remove_background = (
        request.form.get(
            "remove_background"
        ) == "1"
    )

    # -----------------------------------------------------
    # UPLOAD
    # -----------------------------------------------------

    uploaded_file = request.files.get(
        "background_file"
    )

    try:

        new_background = ""

        # =================================================
        # NEW FILE
        # =================================================

        if (
            uploaded_file
            and uploaded_file.filename
        ):

            new_background = save_background(
                uploaded_file
            )

            detected_mode = detect_background_mode(
                new_background
            )

            if detected_mode != "css":

                mode = detected_mode

        # =================================================
        # REMOVE
        # =================================================

        if remove_background:

            remove_upload(
                old_background
            )

            set_setting(
                "background_media",
                ""
            )

            mode = "css"

        # =================================================
        # SAVE NEW FILE
        # =================================================

        elif new_background:

            if old_background:

                remove_upload(
                    old_background
                )

            set_setting(
                "background_media",
                new_background
            )

        # =================================================
        # SAVE SETTINGS
        # =================================================

        set_setting(
            "background_mode",
            mode
        )

        set_setting(
            "background_overlay",
            overlay
        )

        set_setting(
            "background_speed",
            speed
        )

        set_setting(
            "background_blur",
            blur
        )

        set_setting(
            "background_position",
            position
        )

        set_setting(
            "background_size",
            size
        )

        set_setting(
            "background_opacity",
            1
        )

        db.session.commit()

        flash(
            "تنظیمات بک‌گراند با موفقیت ذخیره شد. 🎨",
            "success"
        )

    except ValueError as e:

        db.session.rollback()

        flash(
            str(e),
            "danger"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"خطا در ذخیره بک‌گراند: {e}",
            "danger"
        )

    return redirect(
        url_for("admin")
        + "#appearance-admin"
    )


# =========================================================
# DELETE BACKGROUND
# =========================================================

@app.post(
    "/admin/background/delete"
)
@admin_required
def delete_background():

    old_media = setting(
        "background_media",
        ""
    )

    remove_upload(
        old_media
    )

    set_setting(
        "background_media",
        ""
    )

    set_setting(
        "background_mode",
        "css"
    )

    db.session.commit()

    flash(
        "پس‌زمینه سفارشی حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#appearance-admin"
    )


# =========================================================
# ADMIN ORDER STATUS
# =========================================================

@app.post(
    "/admin/order/status/<int:order_id>"
)
@admin_required
def update_order_status(order_id):

    order = Order.query.get_or_404(
        order_id
    )

    allowed = {

        "در انتظار بررسی",

        "تأیید شد",

        "در حال آماده‌سازی",

        "ارسال شد",

        "تحویل شد",

        "لغو شد",

    }

    status = request.form.get(
        "status",
        ""
    )

    if status in allowed:

        order.status = status

        db.session.commit()

        flash(
            "وضعیت سفارش به‌روزرسانی شد.",
            "success"
        )

    return redirect(
        url_for("admin")
        + "#orders-admin"
    )
# =========================================================
# ADMIN - REPAIR OFFERS
# =========================================================

@app.post(
    "/admin/fix-offers"
)
@admin_required
def admin_fix_offers():

    try:

        # -------------------------------------------------
        # پیدا کردن فروشگاه‌های فعال
        # -------------------------------------------------

        stores = (
            Store.query
            .filter_by(active=True)
            .order_by(Store.id.asc())
            .all()
        )

        # -------------------------------------------------
        # اگر هیچ فروشگاهی وجود ندارد
        # -------------------------------------------------

        if not stores:

            default_stores = [

                Store(
                    name="فروشگاه نمونه",
                    website="https://example.com",
                    active=True
                ),

                Store(
                    name="فروشگاه آنلاین",
                    website="https://example.com",
                    active=True
                ),

                Store(
                    name="فروشگاه دیجیتال",
                    website="https://example.com",
                    active=True
                ),

            ]

            db.session.add_all(
                default_stores
            )

            db.session.commit()

            stores = (
                Store.query
                .filter_by(active=True)
                .all()
            )


        # -------------------------------------------------
        # محصولات فعال
        # -------------------------------------------------

        products = (
            Product.query
            .filter_by(active=True)
            .all()
        )


        created_count = 0
        repaired_count = 0


        # -------------------------------------------------
        # بررسی همه محصولات
        # -------------------------------------------------

        for product in products:

            for index, store in enumerate(stores):

                offer = (
                    Offer.query
                    .filter_by(
                        product_id=product.id,
                        store_id=store.id
                    )
                    .first()
                )


                # -----------------------------------------
                # Offer موجود است
                # -----------------------------------------

                if offer:

                    changed = False

                    if not offer.url:

                        offer.url = (
                            store.website or ""
                        )

                        changed = True


                    if not offer.in_stock:

                        offer.in_stock = True

                        changed = True


                    if not offer.price:

                        offer.price = (
                            int(product.price or 0)
                            + index * 700000
                        )

                        changed = True


                    if changed:

                        repaired_count += 1

                    continue


                # -----------------------------------------
                # Offer وجود ندارد
                # -----------------------------------------

                offer_price = (
                    int(product.price or 0)
                    + index * 700000
                )

                new_offer = Offer(

                    product_id=product.id,

                    store_id=store.id,

                    price=offer_price,

                    url=store.website or "",

                    in_stock=True

                )

                db.session.add(
                    new_offer
                )

                created_count += 1


        db.session.commit()


        flash(
            f"دیتابیس اصلاح شد. "
            f"{created_count} پیشنهاد جدید ساخته شد "
            f"و {repaired_count} پیشنهاد اصلاح شد. ✅",
            "success"
        )


    except Exception:

        db.session.rollback()
        app.logger.exception("admin_fix_offers failed")

        flash(
            "تعمیر پیشنهادها با خطا مواجه شد.",
            "danger"
        )


    return redirect(
        url_for("admin")
    )

# =========================================================
# ADMIN SETTINGS
# =========================================================

@app.post(
    "/admin/settings"
)
@admin_required
def admin_settings():

    keys = [

        "site_name",

        "site_tagline",

        "hero_title",

        "hero_subtitle",

        "hero_badge",

        "footer_text",

        "footer_copyright",

        "meta_description",

        "theme_color",

    ]

    for key in keys:

        value = request.form.get(
            key,
            ""
        ).strip()

        set_setting(
            key,
            value
        )

    db.session.commit()

    flash(
        "تنظیمات سایت ذخیره شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#settings"
    )


# =========================================================
# CATEGORY CRUD
# =========================================================

@app.post(
    "/admin/category/save"
)
@admin_required
def save_category():

    cid = request.form.get(
        "id",
        ""
    ).strip()

    name = request.form.get(
        "name",
        ""
    ).strip()

    icon = request.form.get(
        "icon",
        "fa-box"
    ).strip()

    desc = request.form.get(
        "description",
        ""
    ).strip()

    if not name:

        flash(
            "نام دسته‌بندی الزامی است.",
            "warning"
        )

        return redirect(
            url_for("admin")
        )

    try:

        if cid:

            cat = Category.query.get_or_404(
                int(cid)
            )

        else:

            cat = Category()

            db.session.add(
                cat
            )

        cat.name = name

        cat.icon = icon or "fa-box"

        cat.description = desc

        cat.active = (
            request.form.get(
                "active"
            ) == "1"
        )

        db.session.commit()

        flash(
            "دسته‌بندی ذخیره شد.",
            "success"
        )

    except Exception:

        db.session.rollback()

        flash(
            "این نام دسته‌بندی قبلاً وجود دارد.",
            "danger"
        )

    return redirect(
        url_for("admin")
        + "#categories-admin"
    )


@app.post(
    "/admin/category/delete/<int:category_id>"
)
@admin_required
def delete_category(category_id):

    cat = Category.query.get_or_404(
        category_id
    )

    for product in cat.products:

        product.category_id = None

    db.session.delete(
        cat
    )

    db.session.commit()

    flash(
        "دسته‌بندی حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#categories-admin"
    )


# =========================================================
# PRODUCT CRUD
# =========================================================

@app.post(
    "/admin/product/save"
)
@admin_required
def save_product():

    pid = request.form.get(
        "id",
        ""
    ).strip()

    if pid:

        product = Product.query.get_or_404(
            int(pid)
        )

    else:

        product = Product()

        db.session.add(
            product
        )

    product.name = request.form.get(
        "name",
        ""
    ).strip()

    product.description = request.form.get(
        "description",
        ""
    ).strip()

    try:

        product.price = max(

            0,

            int(
                request.form.get(
                    "price",
                    "0"
                ) or 0
            )

        )

    except (
        TypeError,
        ValueError
    ):

        product.price = 0

    cid = request.form.get(
        "category_id",
        ""
    ).strip()

    try:

        product.category_id = (

            int(cid)

            if cid

            else None

        )

    except ValueError:

        product.category_id = None

    product.active = (
        request.form.get(
            "active"
        ) == "1"
    )

    old_image = product.image

    try:

        new_image = save_image(
            request.files.get(
                "image"
            )
        )

        if new_image:

            product.image = new_image

            if old_image:

                remove_upload(
                    old_image
                )

        db.session.commit()

        flash(
            "محصول ذخیره شد.",
            "success"
        )

    except ValueError as e:

        db.session.rollback()

        flash(
            str(e),
            "danger"
        )

    return redirect(
        url_for("admin")
        + "#products-admin"
    )


@app.post(
    "/admin/product/delete/<int:product_id>"
)
@admin_required
def delete_product(product_id):

    product = Product.query.get_or_404(
        product_id
    )

    remove_upload(
        product.image
    )

    db.session.delete(
        product
    )

    db.session.commit()

    flash(
        "محصول حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#products-admin"
    )


# =========================================================
# STORE CRUD
# =========================================================

@app.post(
    "/admin/store/save"
)
@admin_required
def save_store():

    sid = request.form.get(
        "id",
        ""
    ).strip()

    if sid:

        store = Store.query.get_or_404(
            int(sid)
        )

    else:

        store = Store()

        db.session.add(
            store
        )

    store.name = request.form.get(
        "name",
        ""
    ).strip()

    try:
        store.website = validate_external_url(request.form.get("website", ""))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("admin") + "#stores-admin")

    store.active = (
        request.form.get(
            "active"
        ) == "1"
    )

    old_logo = store.logo

    try:

        new_logo = save_store_logo(
            request.files.get(
                "logo"
            )
        )

        if new_logo:

            store.logo = new_logo

            if old_logo:

                remove_upload(
                    old_logo
                )

        db.session.commit()

        flash(
            "فروشگاه ذخیره شد.",
            "success"
        )

    except ValueError as e:

        db.session.rollback()

        flash(
            str(e),
            "danger"
        )

    return redirect(
        url_for("admin")
        + "#stores-admin"
    )


@app.post(
    "/admin/store/delete/<int:store_id>"
)
@admin_required
def delete_store(store_id):

    store = Store.query.get_or_404(
        store_id
    )

    if store.logo:

        remove_upload(
            store.logo
        )

    db.session.delete(
        store
    )

    db.session.commit()

    flash(
        "فروشگاه حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#stores-admin"
    )


# =========================================================
# OFFER CRUD
# =========================================================

@app.post(
    "/admin/offer/save"
)
@admin_required
def save_offer():

    oid = request.form.get(
        "id",
        ""
    ).strip()

    if oid:

        offer = Offer.query.get_or_404(
            int(oid)
        )

    else:

        offer = Offer()

        db.session.add(
            offer
        )

    try:

        offer.product_id = int(
            request.form["product_id"]
        )

        offer.store_id = int(
            request.form["store_id"]
        )

        offer.price = max(

            0,

            int(
                request.form.get(
                    "price",
                    "0"
                ) or 0
            )

        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):

        db.session.rollback()

        flash(
            "اطلاعات قیمت نامعتبر است.",
            "danger"
        )

        return redirect(
            url_for("admin")
            + "#offers-admin"
        )

    try:
        offer.url = validate_external_url(request.form.get("url", ""))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("admin") + "#offers-admin")

    offer.in_stock = (
        request.form.get(
            "in_stock"
        ) == "1"
    )

    db.session.commit()

    flash(
        "قیمت ذخیره شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#offers-admin"
    )


@app.post(
    "/admin/offer/delete/<int:offer_id>"
)
@admin_required
def delete_offer(offer_id):

    offer = Offer.query.get_or_404(
        offer_id
    )

    db.session.delete(
        offer
    )

    db.session.commit()

    flash(
        "قیمت حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#offers-admin"
    )


# =========================================================
# USER MANAGEMENT
# =========================================================

@app.post(
    "/admin/user/role/<int:user_id>"
)
@admin_required
def change_role(user_id):

    user = User.query.get_or_404(
        user_id
    )

    if user.id == session["user_id"]:

        flash(
            "نقش حساب خودت را از اینجا تغییر نده.",
            "warning"
        )

        return redirect(
            url_for("admin")
            + "#users-admin"
        )

    user.role = (

        "admin"

        if request.form.get(
            "role"
        ) == "admin"

        else "user"

    )

    db.session.commit()

    flash(
        "نقش کاربر تغییر کرد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#users-admin"
    )


@app.post(
    "/admin/user/delete/<int:user_id>"
)
@admin_required
def delete_user(user_id):

    user = User.query.get_or_404(
        user_id
    )

    if user.id == session["user_id"]:

        flash(
            "نمی‌توانی خودت را حذف کنی.",
            "warning"
        )

        return redirect(
            url_for("admin")
            + "#users-admin"
        )

    if (
        user.role == "admin"
        and User.query.filter_by(
            role="admin"
        ).count() <= 1
    ):

        flash(
            "آخرین مدیر حذف نمی‌شود.",
            "warning"
        )

        return redirect(
            url_for("admin")
            + "#users-admin"
        )

    db.session.delete(
        user
    )

    db.session.commit()

    flash(
        "کاربر حذف شد.",
        "success"
    )

    return redirect(
        url_for("admin")
        + "#users-admin"
    )


# =========================================================
# SEED
# =========================================================

def seed():

    # =====================================================
    # SETTINGS
    # =====================================================

    defaults = {
        "site_name": "خریدینو",
        "site_tagline": "مقایسه قیمت، خرید هوشمند",
        "hero_title": "بهترین قیمت را پیدا کن",
        "hero_subtitle": "قیمت محصولات را مقایسه کن و هوشمندانه خرید کن.",
        "hero_badge": "خرید هوشمند",
        "footer_text": "خریدینو؛ مقایسه قیمت و خرید هوشمند",
        "footer_copyright": "تمامی حقوق برای خریدینو محفوظ است.",
        "meta_description": "خریدینو؛ سامانه مقایسه قیمت محصولات و خرید هوشمند.",
        "theme_color": "#6c5ce7",
        "background_mode": "css",
        "background_media": "",
        "background_opacity": "1",
        "background_speed": "18",
        "background_color": "#070b14",
        "background_overlay": "0.45",
        "background_blur": "0",
        "background_position": "center",
        "background_size": "cover",
    }

    for key, value in defaults.items():

        if not Setting.query.filter_by(key=key).first():

            db.session.add(
                Setting(
                    key=key,
                    value=str(value)
                )
            )

    # =====================================================
    # ADMIN
    # =====================================================

    admin = User.query.filter_by(
        email="admin@kharidino.local"
    ).first()

    if not admin:

        bootstrap_email = os.environ.get("KHARIDINO_ADMIN_EMAIL", "").strip().lower()
        bootstrap_password = os.environ.get("KHARIDINO_ADMIN_PASSWORD", "")
        if bootstrap_email and bootstrap_password:
            if len(bootstrap_password) < 12:
                raise RuntimeError("KHARIDINO_ADMIN_PASSWORD must be at least 12 characters.")
            db.session.add(
                User(
                    name="مدیر سایت",
                    email=bootstrap_email,
                    password=generate_password_hash(bootstrap_password),
                    role="admin"
                )
            )

    # =====================================================
    # CATEGORIES
    # =====================================================

    categories_data = [

        (
            "موبایل",
            "fa-mobile-screen-button",
            "گوشی موبایل و لوازم جانبی"
        ),

        (
            "لپ‌تاپ و کامپیوتر",
            "fa-laptop",
            "لپ‌تاپ، کامپیوتر و تجهیزات کامپیوتری"
        ),

        (
            "کالای دیجیتال",
            "fa-microchip",
            "تجهیزات و لوازم دیجیتال"
        ),

        (
            "هدفون و هندزفری",
            "fa-headphones",
            "هدفون، هندزفری و تجهیزات صوتی"
        ),

        (
            "گیمینگ",
            "fa-gamepad",
            "کنسول، دسته بازی و تجهیزات گیمینگ"
        ),

        (
            "تلویزیون و صوتی تصویری",
            "fa-tv",
            "تلویزیون، سینمای خانگی و تجهیزات تصویری"
        ),

        (
            "ساعت و پوشیدنی",
            "fa-clock",
            "ساعت هوشمند و تجهیزات پوشیدنی"
        ),

        (
            "خانه و آشپزخانه",
            "fa-house",
            "لوازم خانگی و آشپزخانه"
        ),

        (
            "زیبایی و سلامت",
            "fa-heart-pulse",
            "محصولات زیبایی، بهداشتی و سلامت"
        ),

        (
            "کتاب و لوازم‌التحریر",
            "fa-book",
            "کتاب، دفتر و لوازم تحریر"
        ),

        (
            "ورزش و سفر",
            "fa-person-running",
            "لوازم ورزشی و سفر"
        ),

        (
            "ابزار",
            "fa-screwdriver-wrench",
            "ابزارآلات و تجهیزات کارگاهی"
        ),

        (
            "خودرو",
            "fa-car",
            "لوازم جانبی و تجهیزات خودرو"
        ),

        (
            "مد و پوشاک",
            "fa-shirt",
            "پوشاک، کفش و اکسسوری"
        ),

        (
            "سوپرمارکتی",
            "fa-cart-shopping",
            "مواد غذایی و کالاهای مصرفی"
        ),

    ]

    for name, icon, description in categories_data:

        category = Category.query.filter_by(
            name=name
        ).first()

        if not category:

            db.session.add(
                Category(
                    name=name,
                    icon=icon,
                    description=description,
                    active=True
                )
            )

    db.session.commit()

    # =====================================================
    # CATEGORY MAP
    # =====================================================

    cats = {
        category.name: category
        for category in Category.query.all()
    }

    # =====================================================
    # REAL PRODUCTS
    # قیمت‌ها نمونه هستند و باید بعداً از API/فروشگاه
    # یا پنل مدیریت به‌روزرسانی شوند.
    # =====================================================

    products_data = [

        # -------------------------------------------------
        # موبایل
        # -------------------------------------------------

        (
            "Samsung Galaxy S24",
            "گوشی پرچمدار سامسونگ با نمایشگر Dynamic AMOLED، دوربین چندگانه و عملکرد قدرتمند برای استفاده روزمره، عکاسی و اجرای برنامه‌های سنگین.",
            42000000,
            "موبایل"
        ),

        (
            "Apple iPhone 16 Pro",
            "گوشی پرچمدار اپل با بدنه حرفه‌ای، دوربین پیشرفته، نمایشگر باکیفیت و پردازنده قدرتمند سری A.",
            115000000,
            "موبایل"
        ),

        (
            "Xiaomi Redmi Note 13 Pro",
            "گوشی میان‌رده قدرتمند شیائومی با نمایشگر باکیفیت، دوربین مناسب و باتری با ظرفیت بالا.",
            27000000,
            "موبایل"
        ),

        (
            "Samsung Galaxy A55",
            "گوشی میان‌رده سامسونگ با طراحی مدرن، نمایشگر AMOLED و عملکرد مناسب برای استفاده روزمره.",
            32000000,
            "موبایل"
        ),

        # -------------------------------------------------
        # لپ‌تاپ
        # -------------------------------------------------

        (
            "Apple MacBook Air M3",
            "لپ‌تاپ سبک و کم‌مصرف اپل مجهز به تراشه M3، مناسب برای کارهای روزمره، برنامه‌نویسی، طراحی و استفاده حرفه‌ای.",
            89000000,
            "لپ‌تاپ و کامپیوتر"
        ),

        (
            "ASUS TUF Gaming F15",
            "لپ‌تاپ گیمینگ ایسوس با سخت‌افزار مناسب اجرای بازی‌ها و نرم‌افزارهای سنگین.",
            75000000,
            "لپ‌تاپ و کامپیوتر"
        ),

        (
            "Lenovo IdeaPad Slim 3",
            "لپ‌تاپ اقتصادی لنوو برای کارهای روزمره، دانشجویی، اداری و وب‌گردی.",
            43000000,
            "لپ‌تاپ و کامپیوتر"
        ),

        (
            "HP Victus 15",
            "لپ‌تاپ گیمینگ اچ‌پی با طراحی مناسب و سخت‌افزار قدرتمند برای بازی و کارهای سنگین.",
            68000000,
            "لپ‌تاپ و کامپیوتر"
        ),

        # -------------------------------------------------
        # کالای دیجیتال
        # -------------------------------------------------

        (
            "Seagate Expansion Portable 2TB",
            "هارد اکسترنال قابل حمل سیگیت با ظرفیت ۲ ترابایت برای ذخیره‌سازی و انتقال اطلاعات.",
            20000000,
            "کالای دیجیتال"
        ),

        (
            "Silicon Power Blaze B10 32GB",
            "فلش مموری سیلیکون پاور با ظرفیت ۳۲ گیگابایت و رابط USB برای انتقال و ذخیره اطلاعات.",
            1567000,
            "کالای دیجیتال"
        ),

        (
            "Baseus Simple Mini3 Wireless Charger",
            "شارژر بی‌سیم باسئوس با توان شارژ ۱۵ وات و طراحی جمع‌وجور.",
            1900000,
            "کالای دیجیتال"
        ),

        (
            "TP-Link Archer C6",
            "روتر بی‌سیم مناسب برای خانه و دفتر با پشتیبانی از شبکه‌های پرسرعت.",
            3200000,
            "کالای دیجیتال"
        ),

        # -------------------------------------------------
        # هدفون
        # -------------------------------------------------

        (
            "Apple AirPods Pro 2",
            "هندزفری بی‌سیم حرفه‌ای اپل با قابلیت حذف نویز فعال و کیفیت صدای مناسب.",
            14500000,
            "هدفون و هندزفری"
        ),

        (
            "Anker Soundcore R50i",
            "هندزفری بی‌سیم اقتصادی انکر با طراحی سبک و مناسب استفاده روزمره.",
            2400000,
            "هدفون و هندزفری"
        ),

        (
            "Sony WH-1000XM5",
            "هدفون بی‌سیم حرفه‌ای سونی با حذف نویز فعال و کیفیت صدای بالا.",
            21000000,
            "هدفون و هندزفری"
        ),

        # -------------------------------------------------
        # گیمینگ
        # -------------------------------------------------

        (
            "Sony PlayStation 5 Slim",
            "کنسول بازی نسل نهم سونی با طراحی باریک‌تر و قدرت پردازشی بالا برای اجرای بازی‌های نسل جدید.",
            38500000,
            "گیمینگ"
        ),

        (
            "Xbox Series X",
            "کنسول قدرتمند مایکروسافت برای اجرای بازی‌های نسل جدید با کیفیت بالا.",
            52000000,
            "گیمینگ"
        ),

        (
            "Sony DualSense Wireless Controller",
            "دسته بازی بی‌سیم پلی‌استیشن ۵ با بازخورد لمسی و تریگرهای تطبیقی.",
            5500000,
            "گیمینگ"
        ),

        # -------------------------------------------------
        # تلویزیون
        # -------------------------------------------------

        (
            "Samsung 55 Inch 4K Smart TV",
            "تلویزیون هوشمند ۵۵ اینچی با وضوح 4K و امکانات هوشمند برای تماشای فیلم و سریال.",
            45000000,
            "تلویزیون و صوتی تصویری"
        ),

        (
            "LG 55 Inch 4K Smart TV",
            "تلویزیون هوشمند ال‌جی با نمایشگر 4K و امکانات متنوع برای سرگرمی خانگی.",
            47000000,
            "تلویزیون و صوتی تصویری"
        ),

        # -------------------------------------------------
        # ساعت
        # -------------------------------------------------

        (
            "Samsung Galaxy Watch 6",
            "ساعت هوشمند سامسونگ با قابلیت پایش فعالیت‌های ورزشی، اعلان‌ها و امکانات سلامتی.",
            12500000,
            "ساعت و پوشیدنی"
        ),

        (
            "Apple Watch Series 9",
            "ساعت هوشمند اپل با امکانات ورزشی، سلامتی و اتصال به اکوسیستم اپل.",
            26000000,
            "ساعت و پوشیدنی"
        ),

        # -------------------------------------------------
        # خانه
        # -------------------------------------------------

        (
            "Vidhas VIR-5637 Sandwich Maker",
            "ساندویچ‌ساز ویداس با توان مصرفی بالا و صفحات مناسب برای تهیه ساندویچ و اسنک.",
            6900000,
            "خانه و آشپزخانه"
        ),

        (
            "Philips Espresso Machine",
            "دستگاه اسپرسوساز خانگی مناسب تهیه انواع نوشیدنی‌های گرم.",
            18000000,
            "خانه و آشپزخانه"
        ),

        (
            "Bosch Vacuum Cleaner",
            "جاروبرقی خانگی بوش با طراحی کاربردی و قدرت مکش مناسب.",
            22000000,
            "خانه و آشپزخانه"
        ),

        # -------------------------------------------------
        # زیبایی
        # -------------------------------------------------

        (
            "Hiska H5107 Hair Brush",
            "برس حرارتی هیسکا برای حالت‌دهی و صاف کردن مو با طراحی مناسب استفاده خانگی.",
            7780000,
            "زیبایی و سلامت"
        ),

        (
            "Nivea Sun SPF 50",
            "ضدآفتاب مناسب استفاده روزانه با محافظت در برابر اشعه‌های مضر خورشید.",
            950000,
            "زیبایی و سلامت"
        ),

        # -------------------------------------------------
        # کتاب
        # -------------------------------------------------

        (
            "کتاب بیلیجی",
            "کتابی منتشرشده توسط نشر نسل نواندیش؛ مناسب علاقه‌مندان به کتاب‌های فارسی.",
            599000,
            "کتاب و لوازم‌التحریر"
        ),

        (
            "دفتر یادداشت 100 برگ",
            "دفتر یادداشت مناسب استفاده روزمره، مدرسه، دانشگاه و محیط کار.",
            250000,
            "کتاب و لوازم‌التحریر"
        ),

        # -------------------------------------------------
        # ورزش
        # -------------------------------------------------

        (
            "Nike Running Shoes",
            "کفش ورزشی مناسب دویدن و فعالیت‌های روزمره با طراحی سبک و راحت.",
            8500000,
            "ورزش و سفر"
        ),

        (
            "قمقمه ورزشی 750ml",
            "قمقمه ورزشی مناسب باشگاه، پیاده‌روی، دوچرخه‌سواری و سفر.",
            750000,
            "ورزش و سفر"
        ),

        # -------------------------------------------------
        # ابزار
        # -------------------------------------------------

        (
            "Bosch Cordless Drill",
            "دریل شارژی بوش مناسب کارهای خانگی و کارگاهی.",
            12500000,
            "ابزار"
        ),

        (
            "Ronix Tool Set",
            "مجموعه ابزار کاربردی رونیکس برای تعمیرات و استفاده‌های خانگی و کارگاهی.",
            6500000,
            "ابزار"
        ),

        # -------------------------------------------------
        # خودرو
        # -------------------------------------------------

        (
            "Bosch Car Air Filter",
            "فیلتر هوای خودرو مناسب تعویض دوره‌ای و کمک به عملکرد بهتر موتور.",
            850000,
            "خودرو"
        ),

        (
            "Car Phone Holder",
            "هولدر موبایل خودرو مناسب استفاده هنگام مسیریابی و رانندگی.",
            650000,
            "خودرو"
        ),

        # -------------------------------------------------
        # پوشاک
        # -------------------------------------------------

        (
            "تیشرت نخی مردانه",
            "تیشرت نخی مناسب استفاده روزمره با طراحی ساده و راحت.",
            850000,
            "مد و پوشاک"
        ),

        (
            "کفش اسپرت مردانه",
            "کفش اسپرت مناسب استفاده روزمره، پیاده‌روی و فعالیت‌های سبک.",
            4200000,
            "مد و پوشاک"
        ),

        # -------------------------------------------------
        # سوپرمارکتی
        # -------------------------------------------------

        (
            "قهوه فوری کلاسیک",
            "قهوه فوری مناسب تهیه سریع نوشیدنی گرم در خانه یا محل کار.",
            450000,
            "سوپرمارکتی"
        ),

        (
            "چای سیاه ایرانی",
            "چای سیاه مناسب مصرف روزانه با عطر و طعم سنتی.",
            650000,
            "سوپرمارکتی"
        ),
    ]

    # =====================================================
    # INSERT PRODUCTS
    # =====================================================

    for name, description, price, category_name in products_data:

        existing = Product.query.filter_by(
            name=name
        ).first()

        if existing:
            continue

        category = cats.get(category_name)

        db.session.add(
            Product(
                name=name,
                description=description,
                price=price,
                category_id=(
                    category.id
                    if category
                    else None
                ),
                active=True
            )
        )

    db.session.commit()

    # =====================================================
    # REAL / KNOWN STORE WEBSITES
    # =====================================================

    stores_data = [

        {
            "name": "دیجی‌کالا",
            "website": "https://www.digikala.com"
        },

        {
            "name": "تکنولایف",
            "website": "https://www.technolife.ir"
        },

        {
            "name": "مقداد آی‌تی",
            "website": "https://meghdadit.com"
        },

        {
            "name": "لیون کامپیوتر",
            "website": "https://lioncomputer.com"
        },

    ]

    # =====================================================
    # INSERT STORES
    # =====================================================

    for store_data in stores_data:

        existing = Store.query.filter_by(
            name=store_data["name"]
        ).first()

        if existing:

            existing.website = store_data["website"]
            existing.active = True

            continue

        db.session.add(
            Store(
                name=store_data["name"],
                website=store_data["website"],
                active=True
            )
        )

    db.session.commit()

    # =====================================================
    # CREATE OFFERS
    # =====================================================

    products = (
        Product.query
        .filter_by(active=True)
        .all()
    )

    stores = (
        Store.query
        .filter_by(active=True)
        .all()
    )

    # =====================================================
    # برای دیتای دمو، قیمت هر فروشگاه کمی متفاوت است.
    #
    # این قیمت‌ها قیمت واقعی لحظه‌ای فروشگاه نیستند.
    # =====================================================

    for product in products:

        base_price = int(
            product.price or 0
        )

        for index, store in enumerate(stores):

            existing_offer = (
                Offer.query
                .filter_by(
                    product_id=product.id,
                    store_id=store.id
                )
                .first()
            )

            if existing_offer:
                continue

            # اختلاف نمونه بین فروشگاه‌ها
            multipliers = [
                1.00,
                1.025,
                0.985,
                1.045,
            ]

            multiplier = multipliers[
                index % len(multipliers)
            ]

            offer_price = int(
                base_price * multiplier
            )

            db.session.add(
                Offer(
                    product_id=product.id,
                    store_id=store.id,
                    price=offer_price,
                    url=store.website,
                    in_stock=True
                )
            )

    db.session.commit()

    # =====================================================
    # FINISH
    # =====================================================

    print("")
    print("==============================================")
    print("KHARIDINO SEED COMPLETED")
    print("==============================================")
    print(
        "Categories:",
        Category.query.count()
    )
    print(
        "Products:",
        Product.query.count()
    )
    print(
        "Stores:",
        Store.query.count()
    )
    print(
        "Offers:",
        Offer.query.count()
    )
    print("==============================================")
    print("")


# =========================================================
# VEHICLE CLASSIFIEDS MODULE
# =========================================================
from vehicle_marketplace import register_vehicle_marketplace, seed_demo_vehicle_ads
VehicleAd = register_vehicle_marketplace(app, db, User, login_required, admin_required)

from vehicle_chat import register_vehicle_chat
register_vehicle_chat(app, db, User, login_required)

# =========================================================
# DATABASE INIT
# =========================================================

@app.context_processor
def inject_request_helpers():
    return {"canonical_url": request.base_url}

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template("404.html", error_message="حجم فایل یا درخواست بیش از حد مجاز است."), 413

@app.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    app.logger.exception("Unhandled Kharidino server error")
    return render_template("404.html", error_message="خطای داخلی رخ داد. لطفاً دوباره تلاش کن."), 500


with app.app_context():

    db.create_all()

    seed()
    seed_demo_vehicle_ads(db, User)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    )