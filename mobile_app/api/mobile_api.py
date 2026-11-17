from flask import Blueprint, jsonify, request


def register_mobile_api(app, db, Product, Category, Store, Offer):
    """Register the mobile API once.

    The API is intentionally read-only here. Authentication can be added later
    for account/order features without weakening the public catalog endpoints.
    """
    if "mobile_api.health" in app.view_functions:
        return app

    bp = Blueprint("mobile_api", __name__, url_prefix="/api/mobile")

    def image_url(product):
        if not product.image:
            return ""
        return "/static/" + product.image.lstrip("/")

    def clean_query(value, max_length=100):
        return (value or "").strip()[:max_length]

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
            for offer in Offer.query.filter_by(
                product_id=product.id, in_stock=True
            ).filter(Offer.price > 0).order_by(Offer.price.asc(), Offer.id.asc()).all():
                store = db.session.get(Store, offer.store_id)
                if not store or not store.active:
                    continue
                offers.append({
                    "id": offer.id,
                    "store_id": offer.store_id,
                    "store": store.name,
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
        search = clean_query(request.args.get("q"))
        limit = min(max(request.args.get("limit", 50, type=int), 1), 100)
        offset = min(max(request.args.get("offset", 0, type=int), 0), 100_000)
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

    @bp.get("/compare")
    def compare_products():
        """Return the same active, in-stock store offers used by web comparison."""
        raw_ids = clean_query(request.args.get("ids"), 80)
        parts = [part.strip() for part in raw_ids.split(",") if part.strip()]
        if not 2 <= len(parts) <= 4:
            return jsonify({"error": "compare_requires_two_to_four_products"}), 400
        try:
            product_ids = [int(part) for part in parts]
        except ValueError:
            return jsonify({"error": "invalid_product_ids"}), 400
        if any(product_id <= 0 for product_id in product_ids) or len(set(product_ids)) != len(product_ids):
            return jsonify({"error": "invalid_product_ids"}), 400

        products_by_id = {
            product.id: product
            for product in Product.query.filter(
                Product.active.is_(True), Product.id.in_(product_ids)
            ).all()
        }
        missing = [product_id for product_id in product_ids if product_id not in products_by_id]
        if missing:
            return jsonify({"error": "products_not_found", "ids": missing}), 404

        items = []
        for product_id in product_ids:
            product = products_by_id[product_id]
            offers = (
                db.session.query(Offer, Store)
                .join(Store, Offer.store_id == Store.id)
                .filter(
                    Offer.product_id == product.id,
                    Offer.in_stock.is_(True),
                    Offer.price > 0,
                    Store.active.is_(True),
                )
                .order_by(Offer.price.asc(), Offer.id.asc())
                .all()
            )
            offer_items = [{
                "id": offer.id,
                "store_id": store.id,
                "store": store.name,
                "price": int(offer.price),
                "url": offer.url or "",
            } for offer, store in offers]
            prices = [item["price"] for item in offer_items]
            items.append({
                **product_json(product),
                "base_price": int(product.price or 0),
                "lowest_offer_price": min(prices) if prices else None,
                "highest_offer_price": max(prices) if prices else None,
                "offer_count": len(offer_items),
                "offers": offer_items,
            })
        return jsonify({"items": items, "count": len(items)})

    @bp.get("/search")
    def search_products():
        q = clean_query(request.args.get("q"))
        if not q:
            return jsonify({"items": [], "total": 0})
        rows = Product.query.filter(
            Product.active.is_(True),
            Product.name.ilike(f"%{q}%")
        ).order_by(Product.id.desc()).limit(50).all()
        return jsonify({"items": [product_json(p) for p in rows], "total": len(rows)})

    app.register_blueprint(bp)
    return app
