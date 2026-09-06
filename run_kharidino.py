"""Recommended launcher for Kharidino Ultimate."""
import os
import socket

from flask import redirect, request, render_template

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


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
