"""Production security hardening for Kharidino.

This module intentionally keeps browser-session CSRF protection, request limits,
security headers, rate limiting and upload content validation in one place so
that every Flask route receives the same baseline protections.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import abort, g, redirect, request, session, url_for

_INSECURE_KEYS = {"", "change-this-secret-key", "dev-secret", "secret"}
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_CSRF_SESSION_KEY = "_kharidino_csrf_token"
_CSRF_FIELD = "csrf_token"
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_CHECKOUT_WINDOW_SECONDS = 24 * 60 * 60

_IMAGE_MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
_VIDEO_MIME = {"mp4": "video/mp4", "webm": "video/webm", "ogg": "video/ogg"}
_ALLOWED_UPLOADS = set(_IMAGE_MIME) | set(_VIDEO_MIME)


def _is_production() -> bool:
    return os.environ.get("FLASK_ENV", "").lower() == "production" or os.environ.get("KHARIDINO_PRODUCTION", "").lower() in {"1", "true", "yes"}


def csrf_token() -> str:
    token = session.get(_CSRF_SESSION_KEY)
    if not token or not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(48)
        session[_CSRF_SESSION_KEY] = token
    return token


def _rotate_csrf_token() -> None:
    session[_CSRF_SESSION_KEY] = secrets.token_urlsafe(48)


def _csrf_valid() -> bool:
    expected = session.get(_CSRF_SESSION_KEY)
    supplied = request.form.get(_CSRF_FIELD) or request.headers.get("X-CSRF-Token")
    if not expected or not supplied:
        return False
    return hmac.compare_digest(str(expected), str(supplied))


def _is_safe_local_redirect(target: str | None) -> bool:
    """Allow only unambiguous same-site relative paths."""
    if not target:
        return False
    target = str(target).strip()
    if not target or "\\" in target or any(ord(ch) < 32 for ch in target):
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and not parsed.username and not parsed.password


def _checkout_fingerprint() -> str | None:
    if request.endpoint != "checkout" or request.method != "POST":
        return None
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        cart = session.get("cart", {})
        if not isinstance(cart, dict):
            cart = {}
        normalized_cart = sorted((str(k), str(v)) for k, v in cart.items())
        payload = "|".join(
            [
                str(user_id),
                repr(normalized_cart),
                request.form.get("customer_name", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("address", "").strip(),
                request.form.get("note", "").strip(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _checkout_guard_init(app) -> None:
    """Create the small idempotency ledger without changing existing tables."""
    try:
        from sqlalchemy import text
        from app import db

        with db.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS kharidino_checkout_guard (
                    fingerprint VARCHAR(64) PRIMARY KEY,
                    created_at REAL NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    order_id INTEGER
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_kharidino_checkout_guard_created_at "
                "ON kharidino_checkout_guard(created_at)"
            ))
    except Exception:
        app.logger.exception("Unable to initialize checkout idempotency ledger")
        if _is_production():
            raise


def _check_checkout_replay() -> None:
    fingerprint = _checkout_fingerprint()
    if not fingerprint:
        return

    try:
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        from app import db

        now = time.time()
        # Cleanup is bounded and safe because completed entries are only used
        # for duplicate protection, not as order records.
        with db.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM kharidino_checkout_guard WHERE created_at < :cutoff"),
                {"cutoff": now - _CHECKOUT_WINDOW_SECONDS},
            )
            try:
                connection.execute(
                    text("""
                        INSERT INTO kharidino_checkout_guard
                            (fingerprint, created_at, status, order_id)
                        VALUES
                            (:fingerprint, :created_at, 'pending', NULL)
                    """),
                    {"fingerprint": fingerprint, "created_at": now},
                )
            except IntegrityError:
                abort(409, description="این سفارش قبلاً در حال ثبت یا ثبت شده است.")

        g.kharidino_checkout_fingerprint = fingerprint
    except ImportError:
        abort(503, description="سرویس سفارش موقتاً در دسترس نیست.")


def _finish_checkout_replay(response) -> None:
    fingerprint = getattr(g, "kharidino_checkout_fingerprint", None)
    if not fingerprint:
        return

    try:
        from sqlalchemy import text
        from app import db

        if response.status_code >= 400:
            with db.engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM kharidino_checkout_guard WHERE fingerprint = :fingerprint"),
                    {"fingerprint": fingerprint},
                )
        else:
            with db.engine.begin() as connection:
                connection.execute(
                    text("""
                        UPDATE kharidino_checkout_guard
                        SET status = 'completed'
                        WHERE fingerprint = :fingerprint
                    """),
                    {"fingerprint": fingerprint},
                )
    except Exception:
        # Never turn a successful order response into a 500 because the
        # idempotency bookkeeping failed after the order was committed.
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass


def _validate_checkout_stock() -> None:
    if request.endpoint != "checkout" or not session.get("user_id"):
        return
    try:
        from app import Product, Offer, Store
        cart = session.get("cart", {})
        if not isinstance(cart, dict):
            cart = {}
        for raw_id, raw_qty in cart.items():
            try:
                product_id = int(raw_id)
                quantity = int(raw_qty)
            except (TypeError, ValueError):
                abort(400, description="سبد خرید نامعتبر است.")
            if quantity < 1 or quantity > 99:
                abort(400, description="تعداد کالا نامعتبر است.")
            product = Product.query.get(product_id)
            if not product or not product.active:
                abort(400, description="یکی از کالاهای سبد دیگر قابل خرید نیست.")
            available = (
                Offer.query
                .join(Store, Offer.store_id == Store.id)
                .filter(
                    Offer.product_id == product.id,
                    Offer.in_stock.is_(True),
                    Store.active.is_(True),
                    Offer.price > 0,
                )
                .count()
            )
            if available == 0:
                abort(409, description="یکی از کالاهای سبد در حال حاضر موجود نیست.")
    except ImportError:
        abort(503, description="سرویس سفارش موقتاً در دسترس نیست.")


def apply_security(app):
    if getattr(app, "_kharidino_security_applied", False):
        return app

    configured_key = os.environ.get("SECRET_KEY", "").strip()
    if configured_key in _INSECURE_KEYS:
        if _is_production():
            raise RuntimeError("SECRET_KEY must be set to a strong random value in production.")
        app.config["SECRET_KEY"] = secrets.token_urlsafe(48)
    else:
        app.config["SECRET_KEY"] = configured_key

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = _is_production()
    app.config["SESSION_COOKIE_NAME"] = "kharidino_session"
    app.config["MAX_FORM_MEMORY_SIZE"] = 2 * 1024 * 1024
    app.config["MAX_FORM_PARTS"] = 200
    app.config["MAX_CONTENT_LENGTH"] = min(int(app.config.get("MAX_CONTENT_LENGTH") or _MAX_UPLOAD_BYTES), _MAX_UPLOAD_BYTES)

    _checkout_guard_init(app)

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def _csrf_context():
        return {"csrf_token": csrf_token}

    @app.before_request
    def _security_before_request():
        _validate_uploaded_files()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            _check_same_origin()
            _check_csrf()
        if request.path in {"/login", "/register"} and request.method == "POST":
            _rate_limit("auth", limit=10, window=300)
        if request.path.startswith("/admin/kharidino-ai/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            _rate_limit("ai", limit=30, window=60)
        if request.path.startswith("/api/mobile/") and request.method == "GET":
            _rate_limit("mobile-read", limit=120, window=60)
        if request.endpoint == "compare_add" and request.method == "POST":
            target = request.form.get("next", "")
            if target and not _is_safe_local_redirect(target):
                request.form = request.form.copy()
                request.form.pop("next", None)
        if request.endpoint == "login" and request.method == "POST":
            target = request.args.get("next", "")
            if target and not _is_safe_local_redirect(target):
                abort(400, description="مقصد بازگشت نامعتبر است.")
        if request.endpoint == "checkout":
            _validate_checkout_stock()
            if request.method == "POST":
                _check_checkout_replay()

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.is_secure or _is_production():
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https:; font-src 'self' data: https:; media-src 'self' blob: https:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'")
        if request.endpoint == "checkout" and request.method == "POST":
            _finish_checkout_replay(response)
        if request.endpoint in {"login", "register", "logout"} and response.status_code < 400:
            _rotate_csrf_token()
        return response

    @app.errorhandler(Exception)
    def _safe_unhandled_error(error):
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unhandled Kharidino request error")
        return "خطای داخلی سرور. لطفاً دوباره تلاش کنید.", 500

    app._kharidino_security_applied = True
    return app


def _check_csrf() -> None:
    if request.path.startswith("/api/") and request.headers.get("Authorization"):
        return
    if not _csrf_valid():
        abort(403, description="Invalid or missing CSRF token.")


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _rate_limit(name: str, *, limit: int, window: int) -> None:
    now = time.monotonic()
    bucket = _RATE_BUCKETS[f"{name}:{_client_ip()}"]
    cutoff = now - window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        abort(429, description="Too many requests. Please try again later.")
    bucket.append(now)


def _check_same_origin() -> None:
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    candidate = origin or referer
    if not candidate:
        if request.path.startswith("/api/") and request.headers.get("Authorization"):
            return
        abort(403, description="Missing Origin/Referer on state-changing request.")
    parsed = urlparse(candidate)
    if not parsed.netloc:
        abort(403, description="Invalid request origin.")
    if parsed.netloc.lower() != request.host.lower():
        abort(403, description="Cross-site state-changing request blocked.")


def _validate_uploaded_files() -> None:
    if not request.files:
        return
    for _field_name, files in request.files.lists():
        for file in files:
            if not file or not file.filename:
                continue
            filename = file.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if "." not in filename:
                continue
            extension = filename.rsplit(".", 1)[1].lower()
            if extension not in _ALLOWED_UPLOADS:
                continue
            if file.content_length and file.content_length > _MAX_UPLOAD_BYTES:
                abort(413, description="Uploaded file is too large.")
            stream = file.stream
            try:
                stream.seek(0)
                head = stream.read(64)
                stream.seek(0)
                _validate_mime_hint(file.mimetype, extension)
                if extension in _IMAGE_MIME:
                    _validate_image(file, extension)
                else:
                    _validate_video_header(head, extension)
            except ValueError as exc:
                abort(400, description=str(exc))
            finally:
                try:
                    stream.seek(0)
                except Exception:
                    pass


def _validate_mime_hint(mimetype: str | None, extension: str) -> None:
    if not mimetype or mimetype == "application/octet-stream":
        return
    expected = _IMAGE_MIME.get(extension) or _VIDEO_MIME.get(extension)
    if expected and mimetype.lower() != expected:
        raise ValueError("نوع محتوای فایل با پسوند آن مطابقت ندارد.")


def _validate_image(file, extension: str) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError("کتابخانه Pillow برای بررسی تصویر نصب نیست.") from exc
    Image.MAX_IMAGE_PIXELS = 25_000_000
    stream = file.stream
    stream.seek(0)
    try:
        image = Image.open(stream)
        actual_format = (image.format or "").lower()
        expected_format = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}[extension]
        if actual_format != expected_format:
            raise ValueError("محتوای واقعی تصویر با پسوند فایل مطابقت ندارد.")
        image.verify()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("فایل تصویر خراب یا نامعتبر است.") from exc
    finally:
        stream.seek(0)


def _validate_video_header(head: bytes, extension: str) -> None:
    if extension == "mp4":
        if b"ftyp" not in head[:32]:
            raise ValueError("فایل MP4 معتبر نیست.")
        return
    if extension == "webm":
        if not head.startswith(b"\x1a\x45\xdf\xa3"):
            raise ValueError("فایل WebM معتبر نیست.")
        return
    if extension == "ogg":
        if not head.startswith(b"OggS"):
            raise ValueError("فایل OGG معتبر نیست.")
        return
    raise ValueError("فرمت ویدئو پشتیبانی نمی‌شود.")
