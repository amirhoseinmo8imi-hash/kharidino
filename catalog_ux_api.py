"""Conversion-focused catalog discovery API.

Provides a stable backend for search/filter/sort UI without changing the existing
storefront markup. The API follows common ecommerce discovery patterns: keyword
search, category, price range, stock, sorting, pagination and result counts.
"""
from flask import jsonify, request
from sqlalchemy import func


def apply_catalog_ux_api(app, db, Product, Category, Offer, Store):
    if getattr(app, "_kharidino_catalog_ux_api", False):
        return

    @app.get("/api/catalog/search")
    def catalog_search():
        raw_q = (request.args.get("q") or "").strip()
        q = raw_q[:100]
        sort = (request.args.get("sort") or "newest").strip()
        if sort not in {"newest", "price_low", "price_high", "name"}:
            sort = "newest"

        try:
            category_id = int(request.args["category"]) if request.args.get("category") else None
            min_price = max(0, int(request.args["min_price"])) if request.args.get("min_price") else None
            max_price = max(0, int(request.args["max_price"])) if request.args.get("max_price") else None
            page = max(1, int(request.args.get("page", "1")))
            per_page = min(40, max(1, int(request.args.get("per_page", "20"))))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_filter"}), 400

        if min_price is not None and max_price is not None and min_price > max_price:
            return jsonify({"error": "invalid_price_range"}), 400

        query = Product.query.filter(Product.active.is_(True))
        if q:
            pattern = f"%{q}%"
            query = query.filter(db.or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)

        # Use the product's base price for cheap SQL-side filtering. The response
        # still reports the real lowest active offer price.
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        if max_price is not None:
            query = query.filter(Product.price <= max_price)

        if sort == "price_low":
            query = query.order_by(Product.price.asc(), Product.id.desc())
        elif sort == "price_high":
            query = query.order_by(Product.price.desc(), Product.id.desc())
        elif sort == "name":
            query = query.order_by(Product.name.asc(), Product.id.desc())
        else:
            query = query.order_by(Product.id.desc())

        total = query.count()
        products = query.offset((page - 1) * per_page).limit(per_page).all()
        rows = []
        for product in products:
            offers = [
                offer for offer in product.offers
                if offer.in_stock and offer.store and offer.store.active and int(offer.price or 0) > 0
            ]
            prices = [int(offer.price) for offer in offers]
            lowest = min(prices) if prices else int(product.price or 0)
            rows.append({
                "id": product.id,
                "name": product.name,
                "category": {"id": product.category.id, "name": product.category.name} if product.category else None,
                "image": product.image or "",
                "price": lowest,
                "store_count": len({offer.store_id for offer in offers}),
                "in_stock": bool(offers),
            })

        return jsonify({
            "query": q,
            "sort": sort,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
            "items": rows,
        })

    app._kharidino_catalog_ux_api = True
