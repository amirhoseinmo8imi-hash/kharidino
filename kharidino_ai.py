"""Kharidino AI control plane.

The dashboard combines deterministic Site Doctor checks with an OpenAI-backed
assistant. The assistant is intentionally read-only: it can inspect the
current health snapshot and produce a structured repair plan, but it never
edits source code or the database without a future explicit executor layer.
"""
from __future__ import annotations

import json
import os
import py_compile
import shutil
from datetime import datetime
from pathlib import Path
from statistics import mean

from flask import Blueprint, jsonify, render_template, request

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - requirements installs this
    OpenAI = None


BASE_DIR = Path(__file__).resolve().parent
AI_DIR = BASE_DIR / "ai_workspace"
BACKUP_DIR = AI_DIR / "backups"
VERSION_DIR = AI_DIR / "versions"
for _path in (AI_DIR, BACKUP_DIR, VERSION_DIR):
    _path.mkdir(parents=True, exist_ok=True)


def _ai_client():
    """Create an OpenAI client only when an API key is configured."""
    if OpenAI is None:
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _ai_model():
    return os.environ.get("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"


def _parse_json(text):
    """Parse model JSON even if the model wraps it in a markdown fence."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return None


def create_ai_blueprint(app, db, Product, Store, Offer, User, admin_required):
    bp = Blueprint("kharidino_ai", __name__, url_prefix="/admin/kharidino-ai")

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
            py_compile.compile(str(BASE_DIR / "kharidino_ai.py"), doraise=True)
            add("Python / Flask", "ok", "app.py and kharidino_ai.py compile successfully")
        except Exception as exc:
            add("Python / Flask", "critical", str(exc))

        for rel in (
            "templates/base.html",
            "templates/index.html",
            "templates/kharidino_ai.html",
            "static/css/style.css",
            "static/css/kharidino-ai.css",
            "static/js/main.js",
            "static/js/kharidino-ai.js",
        ):
            exists = (BASE_DIR / rel).exists()
            add(rel, "ok" if exists else "critical", "present" if exists else "missing")

        try:
            products = Product.query.filter_by(active=True).all()
            no_image = sum(1 for p in products if not p.image)
            no_price = sum(1 for p in products if not p.price or p.price <= 0)
            add(
                "Product data",
                "ok" if no_image == 0 and no_price == 0 else "warning",
                f"{len(products)} active products; {no_image} without image; {no_price} without valid price",
            )
        except Exception as exc:
            add("Product data", "critical", str(exc))

        try:
            stores = Store.query.filter_by(active=True).count()
            offers = Offer.query.count()
            add("Pricing", "ok" if stores and offers else "warning", f"{stores} active stores; {offers} offers")
        except Exception as exc:
            add("Pricing", "critical", str(exc))

        env_secret = bool(os.environ.get("SECRET_KEY")) and os.environ.get("SECRET_KEY") not in {
            "change-this-secret-key",
            "dev-secret",
        }
        add(
            "Security",
            "ok" if env_secret else "warning",
            "SECRET_KEY is supplied by environment" if env_secret else "Set a strong SECRET_KEY in production",
        )

        ai_ready = bool(os.environ.get("OPENAI_API_KEY", "").strip()) and OpenAI is not None
        add(
            "Kharidino AI",
            "ok" if ai_ready else "warning",
            f"OpenAI client ready ({_ai_model()})" if ai_ready else "OPENAI_API_KEY or openai package is missing",
        )

        score = 100
        for item in checks:
            if item["status"] == "critical":
                score -= 15
            elif item["status"] == "warning":
                score -= 5
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
        missing_images = Product.query.filter_by(active=True).filter(
            (Product.image == "") | (Product.image.is_(None))
        ).count()
        return jsonify({
            "products": products,
            "stores": stores,
            "offers": offers,
            "missing_images": missing_images,
        })

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
                return jsonify({"items": [
                    {"id": p.id, "name": p.name, "price": p.price, "image": p.image}
                    for p in same
                ]})
        items = query.order_by(Product.id.desc()).limit(8).all()
        return jsonify({"items": [
            {"id": p.id, "name": p.name, "price": p.price, "image": p.image}
            for p in items
        ]})

    @bp.post("/api/price-analysis")
    @admin_required
    def price_analysis():
        data = request.get_json(silent=True) or {}
        product_id = data.get("product_id")
        try:
            product = db.session.get(Product, int(product_id)) if product_id else None
        except (TypeError, ValueError):
            product = None
        if not product:
            return jsonify({"error": "product_not_found"}), 404
        offers = Offer.query.filter_by(product_id=product.id).all()
        prices = [int(o.price) for o in offers if o.price and o.price > 0]
        if not prices:
            return jsonify({"count": 0, "message": "No valid offers"})
        avg = mean(prices)
        spread = max(prices) - min(prices)
        outliers = [p for p in prices if abs(p - avg) > max(avg * 0.25, 1)]
        return jsonify({
            "count": len(prices),
            "min": min(prices),
            "avg": round(avg),
            "max": max(prices),
            "spread": spread,
            "outliers": outliers,
        })

    @bp.post("/api/agent")
    @admin_required
    def agent():
        data = request.get_json(silent=True) or {}
        command = str(data.get("command", "")).strip()
        if not command:
            return jsonify({"ok": False, "message": "دستور خالی است."}), 400

        health = _health()
        try:
            products = Product.query.filter_by(active=True).all()
            missing_images = [p.name for p in products if not p.image]
            no_price = [p.name for p in products if not p.price or p.price <= 0]
            stores = Store.query.filter_by(active=True).count()
            offers = Offer.query.count()
        except Exception as exc:
            return jsonify({"ok": False, "message": f"خطا در جمع‌آوری وضعیت سایت: {exc}"}), 500

        context = {
            "health_score": health["score"],
            "health_checks": health["checks"],
            "products": len(products),
            "stores": stores,
            "offers": offers,
            "missing_image_count": len(missing_images),
            "missing_image_products": missing_images[:50],
            "invalid_price_count": len(no_price),
            "invalid_price_products": no_price[:50],
        }

        client = _ai_client()
        if client is None:
            return jsonify({
                "ok": False,
                "mode": "configuration_error",
                "message": "هوش مصنوعی وصل نیست. OPENAI_API_KEY یا پکیج openai روی سرور تنظیم نشده است.",
                "plan": [],
                "health": health,
            }), 503

        system = (
            "تو Kharidino AI، دستیار فنی فارسی یک فروشگاه Flask هستی. "
            "دستور مدیر را با توجه به وضعیت واقعی سایت تحلیل کن. "
            "هیچ ادعایی درباره تغییری که انجام نشده نکن. "
            "در این endpoint فقط تحلیل و برنامه تغییر تولید می‌کنی و حق تغییر فایل، دیتابیس، "
            "رمز، کلید API یا اجرای shell command را نداری. "
            "پاسخ را فقط JSON معتبر با کلیدهای message، diagnosis، plan، priority بده. "
            "plan آرایه‌ای از حداکثر 8 گام کوتاه باشد و priority یکی از low, medium, high, critical باشد."
        )
        user_prompt = (
            f"دستور مدیر:\n{command}\n\n"
            f"وضعیت فعلی خریدینو (JSON):\n{json.dumps(context, ensure_ascii=False)}"
        )

        try:
            response = client.responses.create(
                model=_ai_model(),
                instructions=system,
                input=user_prompt,
                max_output_tokens=900,
            )
            result = _parse_json(response.output_text)
            if not isinstance(result, dict):
                return jsonify({
                    "ok": False,
                    "mode": "ai_parse_error",
                    "message": "پاسخ هوش مصنوعی قابل پردازش نبود.",
                    "raw": response.output_text[:2000],
                }), 502

            plan = result.get("plan") if isinstance(result.get("plan"), list) else []
            return jsonify({
                "ok": True,
                "mode": "ai_analysis",
                "model": _ai_model(),
                "command": command,
                "message": str(result.get("message") or "برنامه تحلیل آماده شد."),
                "diagnosis": str(result.get("diagnosis") or ""),
                "priority": str(result.get("priority") or "medium"),
                "plan": [str(x) for x in plan[:8]],
                "approval_required": True,
                "health": health,
            })
        except Exception as exc:
            text = str(exc)
            if "429" in text or "rate limit" in text.lower() or "quota" in text.lower():
                return jsonify({
                    "ok": False,
                    "mode": "rate_limit",
                    "message": "سهمیه یا نرخ درخواست OpenAI فعلاً پر شده است. بعداً دوباره امتحان کن.",
                }), 429
            return jsonify({
                "ok": False,
                "mode": "ai_error",
                "message": f"ارتباط با Kharidino AI ناموفق بود: {text[:500]}",
            }), 502

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
