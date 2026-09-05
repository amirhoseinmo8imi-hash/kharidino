from flask import Blueprint, jsonify, request


def register_mobile_api(app, db, Product, Category, Store, Offer):
    bp = Blueprint("mobile_api", __name__, url_prefix="/api/mobile")

    def image_url(product):
        if not product.image:
            return ""
        return request.host_url.rstrip("/") + "/static/" + product.image.lstrip("/")

    def product_json(product, include_offers=False):
        data = {
            "id": product.id,
            "name": product.name,
            "description": product.description or "",
            "price": product.price or 0,
            "image": image_url(product),
            "category_id": product.category_id,
            "category": product.category.name if product.category else "",
        }
        if include_offers:
            offers = []
            for offer in Offer.query.filter_by(product_id=product.id).order_by(Offer.price.asc()).all():
                store = db.session.get(Store, offer.store_id)
                offers.append({
                    "id": offer.id,
                    "store_id": offer.store_id,
                    "store": store.name if store else "",
                    "price": offer.price,
                    "url": offer.url or "",
                    "in_stock": bool(offer.in_stock),
                })
            data["offers"] = offers
        return data

    @bp.get("/health")
    def health():
        return jsonify({"ok": True, "service": "kharidino-mobile-api"})

    @bp.get("/categories")
    def categories():
        rows = Category.query.filter_by(active=True).order_by(Category.name.asc()).all()
        return jsonify({"items": [{
            "id": c.id,
            "name": c.name,
            "icon": c.icon or "fa-box",
            "description": c.description or "",
        } for c in rows]})

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
        return jsonify({
            "items": [product_json(p) for p in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        })

    @bp.get("/products/<int:product_id>")
    def product_detail(product_id):
        product = Product.query.filter_by(id=product_id, active=True).first_or_404()
        return jsonify(product_json(product, include_offers=True))

    @bp.get("/search")
    def search_products():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"items": [], "total": 0})
        rows = Product.query.filter(
            Product.active.is_(True),
            Product.name.ilike(f"%{q}%")
        ).order_by(Product.id.desc()).limit(50).all()
        return jsonify({"items": [product_json(p) for p in rows], "total": len(rows)})

    app.register_blueprint(bp)
