import os
import secrets
import uuid
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
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


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

configured_secret = os.environ.get("SECRET_KEY", "").strip()
if configured_secret:
    app.config["SECRET_KEY"] = configured_secret
else:
    app.config["SECRET_KEY"] = secrets.token_urlsafe(48)

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

    return {

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
# HOME
# =========================================================

@app.route("/")
def home():

    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "newest").strip()
    category_id = request.args.get("category", "").strip()

    query = Product.query.filter_by(active=True)

    if q:
        search = f"%{q}%"
        query = query.filter(
            db.or_(
                Product.name.ilike(search),
                Product.description.ilike(search)
            )
        )

    if category_id:
        try:
            query = query.filter(Product.category_id == int(category_id))
        except ValueError:
            category_id = ""

    if sort == "price_low":
        # قیمت پایه مرتب می‌شود؛ قیمت واقعی کارت‌ها همچنان lowest_price است.
        query = query.order_by(Product.price.asc(), Product.id.desc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc(), Product.id.desc())
    elif sort == "name":
        query = query.order_by(Product.name.asc())
    else:
        sort = "newest"
        query = query.order_by(Product.id.desc())

    products = query.all()

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

    selected_category = None
    if category_id:
        selected_category = db.session.get(Category, int(category_id))

    return render_template(
        "index.html",
        products=products,
        categories=categories,
        stores=stores,
        q=q,
        sort=sort,
        category_id=category_id,
        selected_category=selected_category,
        lowest_price=lowest_price
    )


# =========================================================
# CATEGORY
# =========================================================

@app.route(
    "/category/<int:category_id>"
)
def category(category_id):

    cat = Category.query.get_or_404(
        category_id
    )

    sort = request.args.get("sort", "newest").strip()
    query = Product.query.filter_by(category_id=cat.id, active=True)

    if sort == "price_low":
        query = query.order_by(Product.price.asc(), Product.id.desc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc(), Product.id.desc())
    elif sort == "name":
        query = query.order_by(Product.name.asc())
    else:
        sort = "newest"
        query = query.order_by(Product.id.desc())

    products = query.all()

    return render_template(
        "category.html",
        category=cat,
        products=products,
        sort=sort,
        lowest_price=lowest_price
    )


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

            review = Review(
                product_id=product.id,
                user_id=session["user_id"],
                rating=rating,
                text=text
            )

            db.session.add(
                review
            )

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

    # -----------------------------------------------------
    # DEBUG
    # -----------------------------------------------------

    print("")
    print("==============================================")
    print("KHARIDINO PRODUCT DEBUG")
    print("==============================================")
    print(
        "Product ID:",
        product.id
    )
    print(
        "Product:",
        product.name
    )
    print(
        "Offers:",
        len(offers)
    )

    for offer in offers:

        print(
            "----------------------------------------------"
        )

        print(
            "Offer ID:",
            offer.id
        )

        print(
            "Store ID:",
            offer.store_id
        )

        print(
            "Store:",
            offer.store.name
            if offer.store
            else "NO STORE"
        )

        print(
            "Price:",
            offer.price
        )

        print(
            "Stock:",
            offer.in_stock
        )

        print(
            "Store Active:",
            offer.store.active
            if offer.store
            else False
        )

    print("==============================================")
    print("")

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render_template(
        "product.html",
        product=product,
        offers=offers,
        lowest_price=lowest,
        rating=rating
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
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if (
            not name
            or not email
            or len(password) < 6
        ):

            flash(
                "نام، ایمیل و رمز حداقل ۶ کاراکتری لازم است.",
                "warning"
            )

            return redirect(
                url_for("register")
            )

        if User.query.filter_by(
            email=email
        ).first():

            flash(
                "این ایمیل قبلاً ثبت شده است.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        user = User(
            name=name,
            email=email,
            password=generate_password_hash(
                password
            ),
            role="user"
        )

        db.session.add(user)

        db.session.commit()

        flash(
            "ثبت‌نام با موفقیت انجام شد.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth.html",
        mode="register"
    )


# =========================================================
# LOGIN
# =========================================================

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

            session.clear()

            # =================================================
            # ایجاد Session جدید
            # =================================================

            session["user_id"] = user.id

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

    if request.method == "POST":

        name = request.form.get(
            "customer_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        note = request.form.get(
            "note",
            ""
        ).strip()

        # =================================================
        # بررسی اطلاعات
        # =================================================

        if (
            not name
            or not phone
            or not address
        ):

            flash(
                "نام، شماره تماس و آدرس الزامی است.",
                "warning"
            )

            return render_template(
                "checkout.html",
                items=items,
                total=total
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
        total=total
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
# ADMIN DASHBOARD
# =========================================================

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
    completed_orders = Order.query.filter_by(status="تکمیل شد").count()
    revenue = sum(int(o.total or 0) for o in Order.query.filter(Order.status != "لغو شد").all())

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
# DATABASE INIT
# =========================================================

with app.app_context():

    db.create_all()

    seed()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    )