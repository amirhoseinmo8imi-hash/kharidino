"""Kharidino AI control plane.

Safe-by-default admin tools for site health, pricing insights, recommendations,
backup planning and a browser voice/chat interface. Code changes are never
applied automatically by this module; repair requests produce an explicit plan.
"""
from __future__ import annotations

import json
import os
import py_compile
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

from flask import Blueprint, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
AI_DIR = BASE_DIR / "ai_workspace"
BACKUP_DIR = AI_DIR / "backups"
VERSION_DIR = AI_DIR / "versions"
for _path in (AI_DIR, BACKUP_DIR, VERSION_DIR):
    _path.mkdir(parents=True, exist_ok=True)


def create_ai_blueprint(app, db, Product, Store, Offer, User, admin_required):
    bp = Blueprint("kharidino_ai", __name__, url_prefix="/admin/kharidino-ai")

    def _admin_user():
        user_id = __import__("flask").session.get("user_id")
        return db.session.get(User, user_id) if user_id else None

    def _health():
        checks = []
        def add(name, status, detail, weight=1):
            checks.append({"name": name, "status": status, "detail": detail, "weight": weight})

        try:
            db.session.execute(db.text("SELECT 1"))
            add("Database", "ok", "SQLite connection is healthy")
        except Exception as exc:
            add("Database", "critical", str(exc))

        try:
            py_compile.compile(str(BASE_DIR / "app.py"), doraise=True)
            add("Python / Flask", "ok", "app.py compiles successfully")
        except Exception as exc:
            add("Python / Flask", "critical", str(exc))

        for rel in ("templates/base.html", "templates/index.html", "static/css/style.css", "static/js/main.js"):
            add(rel, "ok" if (BASE_DIR / rel).exists() else "critical", "present" if (BASE_DIR / rel).exists() else "missing")

        try:
            products = Product.query.filter_by(active=True).all()
            no_image = sum(1 for p in products if not p.image)
            no_price = sum(1 for p in products if not p.price or p.price <= 0)
            add("Product data", "ok" if no_image == 0 and no_price == 0 else "warning",
                f"{len(products)} active products; {no_image} without image; {no_price} without valid price")
        except Exception as exc:
            add("Product data", "critical", str(exc))

        try:
            stores = Store.query.filter_by(active=True).count()
            offers = Offer.query.count()
            add("Pricing", "ok" if stores and offers else "warning", f"{stores} active stores; {offers} offers")
        except Exception as exc:
            add("Pricing", "critical", str(exc))

        env_secret = bool(os.environ.get("SECRET_KEY")) and os.environ.get("SECRET_KEY") not in {"change-this-secret-key", "dev-secret"}
        add("Security", "ok" if env_secret else "warning", "SECRET_KEY is supplied by environment" if env_secret else "Set a strong SECRET_KEY in production")

        score = 100
        for item in checks:
            if item["status"] == "critical": score -= 15
            elif item["status"] == "warning": score -= 5
        score = max(0, min(100, score))
        return {"score": score, "checks": checks, "generated_at": datetime.utcnow().isoformat() + "Z"}

    @bp.get("/")
    @admin_required
    def dashboard():
        return render_template("kharidino_ai.html", health=_health())

    @bp.get("/api/health")
    @admin_required
    def api_health():
        return jsonify(_health())

    @bp.get("/api/stats")
    @admin_required
    def api_stats():
        products = Product.query.filter_by(active=True).count()
        stores = Store.query.filter_by(active=True).count()
        offers = Offer.query.count()
        missing_images = Product.query.filter_by(active=True).filter((Product.image == "") | (Product.image.is_(None))).count()
        return jsonify({"products": products, "stores": stores, "offers": offers, "missing_images": missing_images})

    @bp.get("/api/recommendations/<int:product_id>")
    @admin_required
    def recommendations(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify({"error": "product_not_found"}), 404
        query = Product.query.filter(Product.id != product.id, Product.active.is_(True))
        if product.category_id:
            same = query.filter(Product.category_id == product.category_id).limit(8).all()
            if same:
                return jsonify({"items": [{"id": p.id, "name": p.name, "price": p.price, "image": p.image} for p in same]})
        items = query.order_by(Product.id.desc()).limit(8).all()
        return jsonify({"items": [{"id": p.id, "name": p.name, "price": p.price, "image": p.image} for p in items]})

    @bp.post("/api/price-analysis")
    @admin_required
    def price_analysis():
        data = request.get_json(silent=True) or {}
        product_id = data.get("product_id")
        product = db.session.get(Product, int(product_id)) if product_id else None
        if not product:
            return jsonify({"error": "product_not_found"}), 404
        offers = Offer.query.filter_by(product_id=product.id).all()
        prices = [int(o.price) for o in offers if o.price and o.price > 0]
        if not prices:
            return jsonify({"count": 0, "message": "No valid offers"})
        avg = mean(prices)
        spread = max(prices) - min(prices)
        outliers = [p for p in prices if abs(p - avg) > max(avg * 0.25, 1)]
        return jsonify({"count": len(prices), "min": min(prices), "avg": round(avg), "max": max(prices), "spread": spread, "outliers": outliers})

    @bp.post("/api/agent")
    @admin_required
    def agent():
        data = request.get_json(silent=True) or {}
        command = str(data.get("command", "")).strip()
        lower = command.lower()
        if not command:
            return jsonify({"ok": False, "message": "دستور خالی است."}), 400
        plan = []
        if any(x in lower for x in ("موبایل", "mobile", "ریسپانسیو", "responsive")):
            plan += ["بررسی breakpointهای موبایل", "بررسی overflow و منو", "اجرای smoke test صفحات اصلی"]
        if any(x in lower for x in ("عکس", "تصویر", "image")):
            missing = Product.query.filter_by(active=True).filter((Product.image == "") | (Product.image.is_(None))).count()
            plan += [f"شناسایی {missing} محصول بدون تصویر", "اعتبارسنجی تصاویر موجود", "پیشنهاد تصاویر جایگزین"]
        if any(x in lower for x in ("قیمت", "price")):
            plan += ["محاسبه min/avg/max پیشنهادها", "تشخیص قیمت‌های پرت", "گزارش فروشگاه ارزان‌تر"]
        if any(x in lower for x in ("امنیت", "security")):
            plan += ["بررسی SECRET_KEY و debug", "بررسی آپلود فایل", "بررسی کنترل دسترسی مدیر"]
        if any(x in lower for x in ("کل سایت", "همه", "بررسی", "check")):
            plan += ["اجرای Site Doctor", "بررسی Python/Flask/DB/Templates/Assets", "ساخت گزارش اولویت‌بندی‌شده"]
        if not plan:
            plan = ["تحلیل دستور", "ساخت Change Plan", "نمایش Diff قبل از اعمال"]
        return jsonify({"ok": True, "mode": "approval_required", "command": command, "plan": list(dict.fromkeys(plan)), "message": "برنامه آماده شد؛ هیچ تغییری بدون تأیید مدیر اعمال نمی‌شود."})

    @bp.post("/api/backup")
    @admin_required
    def backup():
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"snapshot_{stamp}"
        target.mkdir(parents=True, exist_ok=True)
        files = ["app.py", "requirements.txt", ".gitignore"]
        copied = []
        for rel in files:
            src = BASE_DIR / rel
            if src.exists():
                shutil.copy2(src, target / rel.replace("/", "_"))
                copied.append(rel)
        return jsonify({"ok": True, "snapshot": str(target.relative_to(BASE_DIR)), "files": copied})

    @bp.get("/api/versions")
    @admin_required
    def versions():
        items = []
        for path in sorted(VERSION_DIR.glob("*.json"), reverse=True)[:20]:
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return jsonify({"items": items})

    return bp


def register(app, db, Product, Store, Offer, User, admin_required):
    """Register the Kharidino AI blueprint on the existing Flask app."""
    if "kharidino_ai.dashboard" not in app.view_functions:
        app.register_blueprint(create_ai_blueprint(app, db, Product, Store, Offer, User, admin_required))
    return app


if __name__ == "__main__":
    from app import app, db, Product, Store, Offer, User, admin_required
    register(app, db, Product, Store, Offer, User, admin_required)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
