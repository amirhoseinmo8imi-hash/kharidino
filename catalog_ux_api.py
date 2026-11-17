"""Conversion-focused catalog discovery API.

Provides a stable backend for search/filter/sort UI without changing the existing
storefront markup. The API follows common ecommerce discovery patterns: keyword
search, category, price range, stock, sorting, pagination and result counts.
"""
from flask import jsonify, request
from sqlalchemy import func, or_


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
            query = query.filter(
                or_(Product.name.ilike(pattern), Product.description.ilike(pattern))
            )
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)

        # Filter and sort by the same price users see: the lowest active offer
        # from an active store. Products without an offer fall back to base price.
        lowest_offer_price = (
            db.session.query(func.min(Offer.price))
            .join(Store, Offer.store_id == Store.id)
            .filter(
                Offer.product_id == Product.id,
                Offer.in_stock.is_(True),
                Store.active.is_(True),
                Offer.price > 0,
            )
            .correlate(Product)
            .scalar_subquery()
        )
        effective_price = func.coalesce(lowest_offer_price, Product.price)

        if min_price is not None:
            query = query.filter(effective_price >= min_price)
        if max_price is not None:
            query = query.filter(effective_price <= max_price)

        if sort == "price_low":
            query = query.order_by(effective_price.asc(), Product.id.desc())
        elif sort == "price_high":
            query = query.order_by(effective_price.desc(), Product.id.desc())
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


    @app.get("/api/catalog/compare")
    def catalog_compare():
        """Compare 2-4 active products using offers from active stores only."""
        raw_ids = (request.args.get("ids") or "").strip()
        parts = [part.strip() for part in raw_ids.split(",") if part.strip()]
        if not 2 <= len(parts) <= 4:
            return jsonify({"error": "compare_requires_two_to_four_products"}), 400
        try:
            product_ids = [int(part) for part in parts]
        except ValueError:
            return jsonify({"error": "invalid_product_ids"}), 400
        if any(product_id <= 0 for product_id in product_ids) or len(set(product_ids)) != len(product_ids):
            return jsonify({"error": "invalid_product_ids"}), 400

        products = (
            Product.query.filter(Product.active.is_(True), Product.id.in_(product_ids))
            .all()
        )
        by_id = {product.id: product for product in products}
        missing_ids = [product_id for product_id in product_ids if product_id not in by_id]
        if missing_ids:
            return jsonify({"error": "products_not_found", "ids": missing_ids}), 404

        items = []
        for product_id in product_ids:
            product = by_id[product_id]
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
                "id": product.id,
                "name": product.name,
                "image": product.image or "",
                "base_price": int(product.price or 0),
                "lowest_offer_price": min(prices) if prices else None,
                "highest_offer_price": max(prices) if prices else None,
                "offer_count": len(offer_items),
                "offers": offer_items,
            })

        return jsonify({"items": items, "count": len(items)})
