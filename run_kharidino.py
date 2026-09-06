"""Recommended launcher for Kharidino Ultimate."""
import os
import socket

from flask import redirect, request, render_template, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app import app, db, Product, Category, Store, Offer, User, admin_required
from kharidino_ai import register as register_ai
from mobile_app.api.mobile_api import register_mobile_api
from security_hardening import apply_security
from inventory_hardening import apply_inventory_security
from commerce_extensions_v2 import apply_commerce_extensions
from commerce_catalog import apply_catalog_extensions
import commerce_runtime  # noqa: F401
import profile_extensions  # noqa: F401 - registers customer profile model/routes
import merchant_marketplace  # noqa: F401 - registers seller/store workspace and models

register_ai(app, db, Product, Store, Offer, User, admin_required)
register_mobile_api(app, db, Product, Category, Store, Offer)

with app.app_context():
    apply_security(app)
    apply_inventory_security(app)
    apply_commerce_extensions(app)
    apply_catalog_extensions(app)
    db.create_all()


def _port_is_available(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.25)
    try:
        result = probe.connect_ex(("127.0.0.1", port))
        return result != 0
    except OSError:
        return True
    finally:
        probe.close()


def _select_port(requested: int) -> int:
    if _port_is_available("0.0.0.0", requested):
        return requested
    if os.environ.get("STRICT_PORT", "0").lower() in {"1", "true", "yes"}:
        raise RuntimeError(f"Port {requested} is already in use. Stop the old Kharidino server or choose another PORT.")
    for candidate in range(requested + 1, requested + 21):
        if _port_is_available("0.0.0.0", candidate):
            print(f"[Kharidino] Port {requested} is busy; using free port {candidate}.")
            return candidate
    raise RuntimeError(f"Ports {requested}-{requested + 20} are busy. Stop old Python/Flask processes and try again.")


@app.get("/splash")
def kharidino_splash():
    return render_template("kharidino_splash.html")


@app.get("/phone")
def phone_connection():
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
        "<style>body{font-family:Tahoma,Arial;background:#f7f8fa;margin:0;padding:28px;color:#202124}.card{max-width:520px;margin:auto;background:#fff;border:1px solid #e7e9ed;border-radius:20px;padding:24px;box-shadow:0 10px 35px #0001}h1{font-size:23px}.url{direction:ltr;display:block;background:#fff4ee;color:#e94b00;padding:15px;border-radius:12px;font:bold 20px Arial;text-align:center;margin:18px 0}ol{line-height:2}.ok{color:#16a34a;font-weight:bold}</style>"
        f"<div class='card'><h1>📱 اتصال خریدینو به گوشی</h1><p class='ok'>سرور روی شبکه محلی فعال است.</p><span class='url'>http://{host}:{port}</span>"
        "<ol><li>گوشی و کامپیوتر را به یک Wi‑Fi وصل کن.</li><li>آدرس بالا را در Chrome گوشی وارد کن.</li><li>اگر باز نشد، Windows Firewall را برای Python روی Private Network مجاز کن.</li></ol><p>برای API موبایل: <b>/api/mobile/health</b></p></div></html>"
    )


@app.get("/logout")
def logout_get():
    token_factory = app.jinja_env.globals.get("csrf_token")
    token = token_factory() if callable(token_factory) else ""
    action = url_for("logout")
    return (
        "<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>خروج | خریدینو</title></head><body>"
        f"<form id='logout-form' method='post' action='{action}'><input type='hidden' name='csrf_token' value='{token}'>"
        "<noscript><button type='submit'>خروج از حساب</button></noscript></form><script>document.getElementById('logout-form').submit();</script>"
        "</body></html>"
    )


@app.before_request
def splash_gate():
    if (request.path.startswith("/static/") or request.path.startswith("/splash") or request.path.startswith("/phone")
            or request.path.startswith("/api/mobile/") or request.path.startswith("/admin/kharidino-ai/api/")):
        return None
    if request.cookies.get("kharidino_splash") != "1":
        return redirect("/splash")
    return None


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    requested_port = int(os.environ.get("PORT", "5000"))
    port = _select_port(requested_port)
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    print("=" * 50)
    print("KHARIDINO ULTIMATE SERVER")
    print(f"Local:  http://127.0.0.1:{port}")
    print(f"LAN:    http://<PC-IP>:{port}")
    print(f"AI:     http://127.0.0.1:{port}/admin/kharidino-ai/")
    print("=" * 50)
    app.run(host=host, port=port, debug=debug)
