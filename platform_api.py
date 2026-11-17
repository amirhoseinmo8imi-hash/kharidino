"""Versioned read API for the unified Kharidino Android/web clients."""
from flask import jsonify, request, url_for
from sqlalchemy import and_, func, or_

from catalog_ux_api import _normalized_sql, normalize_search_text


def register_platform_api(app, db, Product, Offer, Store):
    @app.get("/api/v1/market/products")
    def api_market_products():
        raw_q = (request.args.get("q") or "")[:100]
        q = normalize_search_text(raw_q)
        stock = (request.args.get("stock") or "all").strip().lower()
        sort = (request.args.get("sort") or "newest").strip()
        if stock not in {"all", "available", "unavailable"}:
            return jsonify({"error": "invalid_stock_filter"}), 400
        if sort not in {"newest", "price_low", "price_high", "name"}:
            return jsonify({"error": "invalid_sort"}), 400
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        if page is None or per_page is None or page < 1 or per_page < 1:
            return jsonify({"error": "invalid_pagination"}), 400
        page = min(page, 10000)
        per_page = min(per_page, 40)

        query = Product.query.filter(Product.active.is_(True))
        if q:
            name_expr = _normalized_sql(Product.name)
            description_expr = _normalized_sql(Product.description)
            query = query.filter(and_(*[
                or_(name_expr.ilike(f"%{token}%"), description_expr.ilike(f"%{token}%"))
                for token in q.split()
            ]))
        available_ids = (
            db.session.query(Offer.product_id)
            .join(Store, Offer.store_id == Store.id)
            .filter(Store.active.is_(True), Offer.in_stock.is_(True), Offer.price > 0)
        )
        if stock == "available":
            query = query.filter(Product.id.in_(available_ids))
        elif stock == "unavailable":
            query = query.filter(~Product.id.in_(available_ids))

        lowest_offer = (
            db.session.query(func.min(Offer.price))
            .join(Store, Offer.store_id == Store.id)
            .filter(
                Offer.product_id == Product.id,
                Store.active.is_(True),
                Offer.in_stock.is_(True),
                Offer.price > 0,
            )
            .correlate(Product).scalar_subquery()
        )
        effective_price = func.coalesce(lowest_offer, Product.price)
        if sort == "price_low":
            query = query.order_by(effective_price.asc(), Product.id.desc())
        elif sort == "price_high":
            query = query.order_by(effective_price.desc(), Product.id.desc())
        elif sort == "name":
            query = query.order_by(Product.name.asc(), Product.id.desc())
        else:
            query = query.order_by(Product.id.desc())

        total = query.count()
        rows = query.offset((page - 1) * per_page).limit(per_page).all()
        items = []
        for product in rows:
            offers = [
                offer for offer in product.offers
                if offer.in_stock and offer.store and offer.store.active and int(offer.price or 0) > 0
            ]
            prices = [int(offer.price) for offer in offers]
            items.append({
                "id": product.id,
                "name": product.name,
                "description": product.description or "",
                "price": min(prices) if prices else int(product.price or 0),
                "image": product.image or "",
                "store_count": len({offer.store_id for offer in offers}),
                "in_stock": bool(offers),
            })
        return jsonify({
            "items": items, "query": q, "stock": stock, "sort": sort,
            "page": page, "per_page": per_page, "total": total,
            "pages": (total + per_page - 1) // per_page,
        })

    @app.get("/api/v1/market/products/<int:product_id>/offers")
    def api_market_product_offers(product_id):
        product = db.session.get(Product, product_id)
        if not product or not product.active:
            return jsonify({"error": "product_not_found"}), 404
        offers = Offer.query.join(Store).filter(
            Offer.product_id == product.id,
            Store.active.is_(True),
        ).order_by(Offer.price.asc(), Offer.id.asc()).all()
        return jsonify({
            "product_id": product.id,
            "items": [{
                "offer_id": offer.id,
                "store_id": offer.store_id,
                "store": offer.store.name,
                "price": offer.price,
                "url": offer.url,
                "in_stock": bool(offer.in_stock),
            } for offer in offers],
        })

    @app.get("/api/v1/explore/feed")
    def api_explore_feed():
        models = app.extensions.get("kharidino_explore_models")
        if not models:
            return jsonify({"items": [], "page": 1, "per_page": 12, "total": 0})
        Post = models["post"]
        page = max(1, min(request.args.get("page", 1, type=int) or 1, 10000))
        query = Post.query.filter_by(status="published").order_by(Post.created_at.desc(), Post.id.desc())
        total = query.count()
        rows = query.offset((page - 1) * 12).limit(12).all()
        return jsonify({
            "items": [{"id": p.id, "caption": p.caption, "media_type": p.media_type,
                       "media_url": url_for("static", filename=p.media_path, _external=True),
                       "author": p.user.name, "created_at": p.created_at.isoformat(),
                       "product_id": p.product_id, "likes": len(p.likes)} for p in rows],
            "page": page, "per_page": 12, "total": total,
        })

    @app.get("/api/v1/cinema/titles")
    def api_cinema_titles():
        models = app.extensions.get("kharidino_cinema_models")
        if not models:
            return jsonify({"items": [], "page": 1, "per_page": 20, "total": 0})
        Title = models["title"]
        page = max(1, min(request.args.get("page", 1, type=int) or 1, 10000))
        query = Title.query.filter_by(status="published").order_by(Title.created_at.desc())
        total = query.count()
        rows = query.offset((page - 1) * 20).limit(20).all()
        return jsonify({
            "items": [{"id": t.id, "title": t.title, "synopsis": t.synopsis,
                       "genre": t.genre, "release_year": t.release_year,
                       "poster_url": t.poster_url,
                       "detail_url": url_for("cinema_title", title_id=t.id, _external=True),
                       "has_video": bool(t.video_path)} for t in rows],
            "page": page, "per_page": 20, "total": total,
        })

    @app.get("/api/v1/platform")
    def api_platform_manifest():
        return jsonify({
            "name": "Kharidino",
            "api_version": "v1",
            "modules": [
                {"id": "market", "title": "بازار", "path": "/api/v1/market/products"},
                {"id": "explore", "title": "اکسپلور", "path": "/api/v1/explore/feed"},
                {"id": "cinema", "title": "سینما", "path": "/api/v1/cinema/titles"},
            ],
        })
