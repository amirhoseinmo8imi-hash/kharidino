"""Production-safe launcher for Kharidino Ultimate."""
import io
import os
import socket

from flask import redirect, request, render_template
from PIL import Image, UnidentifiedImageError

import app as kharidino_app
from app import app, db, Product, Category, Store, Offer, User, admin_required
from kharidino_ai import register as register_ai
from mobile_app.api.mobile_api import register_mobile_api

register_ai(app, db, Product, Store, Offer, User, admin_required)
register_mobile_api(app, db, Product, Category, Store, Offer)


@app.get("/splash")
def kharidino_splash():
    return render_template("kharidino_splash.html")


@app.get("/phone")
def phone_connection():
    """Simple LAN connection page for opening Kharidino on a phone."""
    host = request.host.split(":", 1)[0]
    port = request.host.rsplit(":", 1)[-1] if ":" in request.host else os.environ.get("PORT", "5000")
    if host in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
        try:
            host = socket.gethostbyname(socket.gethostname())
        except OSError:
            host = "YOUR-PC-IP"
    return (
        "<!doctype html><html lang='fa' dir='rtl'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>اتصال موبایل | خریدینو</title>"
        "<style>body{font-family:Tahoma,Arial;background:#f7f8fa;margin:0;padding:28px;color:#202124}"
        ".card{max-width:520px;margin:auto;background:#fff;border:1px solid #e7e9ed;border-radius:20px;padding:24px;box-shadow:0 10px 35px #0001}"
        "h1{font-size:23px}.url{direction:ltr;display:block;background:#fff4ee;color:#e94b00;padding:15px;border-radius:12px;font:bold 20px Arial;text-align:center;margin:18px 0}"
        "ol{line-height:2}.ok{color:#16a34a;font-weight:bold}</style>"
        f"<div class='card'><h1>📱 اتصال خریدینو به گوشی</h1>"
        f"<p class='ok'>سرور روی شبکه محلی فعال است.</p>"
        f"<span class='url'>http://{host}:{port}</span>"
        "<ol><li>گوشی و کامپیوتر را به یک Wi‑Fi وصل کن.</li>"
        "<li>آدرس بالا را در Chrome گوشی وارد کن.</li>"
        "<li>اگر باز نشد، Windows Firewall را برای Python روی Private Network مجاز کن.</li></ol>"
        "<p>برای API موبایل: <b>/api/mobile/health</b></p></div></html>"
    )


@app.before_request
def splash_gate():
    if (
        request.path.startswith("/static/")
        or request.path.startswith("/splash")
        or request.path.startswith("/phone")
        or request.path.startswith("/api/mobile/")
        or request.path.startswith("/admin/kharidino-ai/api/")
    ):
        return None
    if request.cookies.get("kharidino_splash") != "1":
        return redirect("/splash")
    return None


@app.after_request
def security_headers(response):
    """Apply safe browser defaults without breaking the existing frontend."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _secure_save_upload(file, folder, allowed_extensions):
    """Validate image bytes before delegating to the original uploader."""
    if not file or not getattr(file, "filename", ""):
        return kharidino_app.save_upload(file, folder, allowed_extensions)

    extension = kharidino_app.get_extension(file.filename)
    if extension in kharidino_app.ALLOWED_IMAGES:
        try:
            position = file.stream.tell()
            payload = file.stream.read()
            file.stream.seek(position)
            with Image.open(io.BytesIO(payload)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValueError("محتوای فایل تصویر معتبر نیست.")
        finally:
            try:
                file.stream.seek(0)
            except (AttributeError, OSError):
                pass

    return _ORIGINAL_SAVE_UPLOAD(file, folder, allowed_extensions)


_ORIGINAL_SAVE_UPLOAD = kharidino_app.save_upload
kharidino_app.save_upload = _secure_save_upload


def validate_runtime_config():
    """Fail fast when the production runtime is missing required secrets."""
    secret = os.environ.get("SECRET_KEY", "").strip()
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    if not secret or secret in {"change-this-secret-key", "dev-secret"}:
        if not debug:
            raise RuntimeError(
                "SECRET_KEY is not configured. Set a strong random SECRET_KEY before starting Kharidino."
            )
        app.logger.warning("Using development SECRET_KEY configuration; do not use this in production.")
    if len(secret) < 32 and not debug:
        raise RuntimeError("SECRET_KEY must contain at least 32 characters in production.")

    if not debug and os.environ.get("KHARIDINO_ADMIN_PASSWORD", "").strip() in {"", "admin12345"}:
        app.logger.warning(
            "KHARIDINO_ADMIN_PASSWORD is not configured. Do not rely on a default administrator password."
        )


if __name__ == "__main__":
    validate_runtime_config()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
