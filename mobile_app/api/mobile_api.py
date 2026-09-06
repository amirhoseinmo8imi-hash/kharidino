from datetime import datetime, timezone
import secrets

from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash


def register_mobile_api(app, db, Product, Category, Store, Offer, User):
    bp = Blueprint("mobile_api", __name__, url_prefix="/api/mobile")
    serializer = URLSafeTimedSerializer(app.config.get("SECRET_KEY", "dev-secret"), salt="kharidino-mobile-v1")

    def image_url(product):
        if not product.image:
            return ""
        return request.host_url.rstrip("/") + "/static/" + product.image.lstrip("/")

    def product_json(product, include_offers=False):
        data = {"id": product.id, "name": product.name, "description": product.description or "", "price": product.price or 0,
                "image": image_url(product), "category_id": product.category_id,
                "category": product.category.name if product.category else ""}
        if include_offers:
            data["offers"] = [{"id": o.id, "store_id": o.store_id, "store": o.store.name if o.store else "", "price": o.price,
                               "url": o.url or "", "in_stock": bool(o.in_stock)}
                              for o in Offer.query.filter_by(product_id=product.id).order_by(Offer.price.asc()).all()]
        return data

    def admin_from_token():
        auth = (request.headers.get("Authorization") or "").strip()
        if not auth.startswith("Bearer "):
            return None
        try:
            data = serializer.loads(auth[7:].strip(), max_age=60 * 60 * 24 * 30)
        except (BadSignature, SignatureExpired):
            return None
        user = db.session.get(User, int(data.get("uid", 0))) if data.get("uid") else None
        return user if user and user.role == "admin" else None

    def auth_required():
        user = admin_from_token()
        if not user:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return user

    @bp.get("/health")
    def health():
        return jsonify({"ok": True, "service": "kharidino-mobile-api", "sync": True})

    @bp.post("/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        user = User.query.filter_by(email=email, role="admin").first()
        if not user or not check_password_hash(user.password, password):
            return jsonify({"ok": False, "error": "اطلاعات ورود مدیر نادرست است."}), 401
        token = serializer.dumps({"uid": user.id, "nonce": secrets.token_hex(8)})
        return jsonify({"ok": True, "token": token, "expires_in": 60 * 60 * 24 * 30,
                        "user": {"id": user.id, "name": user.name, "email": user.email}})

    @bp.get("/categories")
    def categories():
        rows = Category.query.filter_by(active=True).order_by(Category.name.asc()).all()
        return jsonify({"items": [{"id": c.id, "name": c.name, "icon": c.icon or "fa-box", "description": c.description or ""} for c in rows]})

    @bp.get("/products")
    def products():
        query = Product.query.filter_by(active=True)
        category_id = request.args.get("category_id", type=int)
        search = (request.args.get("q") or "").strip()
        limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
        offset = max(request.args.get("offset", 0, type=int), 0)
        if category_id:
            query = query.filter_by(category_id=category_id)
        if search:
            query = query.filter(Product.name.ilike(f"%{search}%"))
        total = query.count()
        rows = query.order_by(Product.id.desc()).offset(offset).limit(limit).all()
        return jsonify({"items": [product_json(p) for p in rows], "total": total, "offset": offset, "limit": limit})

    @bp.get("/products/<int:product_id>")
    def product_detail(product_id):
        product = Product.query.filter_by(id=product_id, active=True).first_or_404()
        return jsonify(product_json(product, include_offers=True))

    @bp.get("/search")
    def search_products():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"items": [], "total": 0})
        rows = Product.query.filter(Product.active.is_(True), Product.name.ilike(f"%{q}%")).order_by(Product.id.desc()).limit(50).all()
        return jsonify({"items": [product_json(p) for p in rows], "total": len(rows)})

    def serialize_entity(model, row):
        if model is Product:
            return {"id": row.id, "name": row.name, "description": row.description or "", "price": row.price or 0,
                    "category_id": row.category_id, "image": row.image or "", "active": bool(row.active)}
        if model is Category:
            return {"id": row.id, "name": row.name, "icon": row.icon or "fa-box", "description": row.description or "", "active": bool(row.active)}
        if model is Store:
            return {"id": row.id, "name": row.name, "website": row.website or "", "logo": row.logo or "", "active": bool(row.active)}
        return {"id": row.id, "product_id": row.product_id, "store_id": row.store_id, "price": row.price, "url": row.url or "", "in_stock": bool(row.in_stock)}

    MODELS = {"product": Product, "category": Category, "store": Store, "offer": Offer}

    def apply_operation(op):
        entity = str(op.get("entity") or "").lower()
        action = str(op.get("action") or "").lower()
        model = MODELS.get(entity)
        if not model or action not in {"create", "update", "delete"}:
            raise ValueError("عملیات همگام‌سازی نامعتبر است.")
        data = op.get("data") or {}
        client_id = op.get("client_id")
        row = db.session.get(model, int(client_id)) if client_id is not None and str(client_id).lstrip("-").isdigit() and int(client_id) > 0 else None
        if action == "delete":
            if row:
                db.session.delete(row)
            return {"client_id": client_id, "server_id": int(client_id) if client_id else None, "action": action, "entity": entity}
        fields = {"product": ["name", "description", "price", "category_id", "image", "active"],
                  "category": ["name", "icon", "description", "active"],
                  "store": ["name", "website", "logo", "active"],
                  "offer": ["product_id", "store_id", "price", "url", "in_stock"]}[entity]
        if not row:
            row = model()
            db.session.add(row)
        for key in fields:
            if key in data:
                setattr(row, key, data[key])
        db.session.flush()
        return {"client_id": client_id, "server_id": row.id, "action": action, "entity": entity}

    @bp.post("/sync/push")
    def sync_push():
        user = auth_required()
        if not hasattr(user, "role"):
            return user
        operations = (request.get_json(silent=True) or {}).get("operations") or []
        if len(operations) > 100:
            return jsonify({"ok": False, "error": "حداکثر ۱۰۰ عملیات در هر بسته."}), 400
        results = []
        try:
            for op in operations:
                results.append(apply_operation(op))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Mobile sync push failed")
            return jsonify({"ok": False, "error": "بسته همگام‌سازی اعمال نشد.", "detail": str(exc) if app.debug else None}), 400
        return jsonify({"ok": True, "results": results, "processed": len(results), "synced_at": datetime.now(timezone.utc).isoformat()})

    @bp.get("/sync/pull")
    def sync_pull():
        user = auth_required()
        if not hasattr(user, "role"):
            return user
        return jsonify({"ok": True,
                        "categories": [serialize_entity(Category, r) for r in Category.query.all()],
                        "products": [serialize_entity(Product, r) for r in Product.query.all()],
                        "stores": [serialize_entity(Store, r) for r in Store.query.all()],
                        "offers": [serialize_entity(Offer, r) for r in Offer.query.all()],
                        "synced_at": datetime.now(timezone.utc).isoformat()})

    app.register_blueprint(bp)
