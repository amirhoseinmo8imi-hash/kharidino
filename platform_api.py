"""Versioned read API for the unified Kharidino Android/web clients."""
from flask import abort, jsonify, request, url_for


def register_platform_api(app, db, Product):
    @app.get("/api/v1/market/products")
    def api_market_products():
        page = max(1, min(request.args.get("page", 1, type=int) or 1, 10000))
        query = Product.query.filter_by(active=True).order_by(Product.id.desc())
        total = query.count()
        rows = query.offset((page - 1) * 20).limit(20).all()
        return jsonify({
            "items": [{"id": p.id, "name": p.name, "description": p.description or "",
                       "price": p.price or 0, "image": p.image or ""} for p in rows],
            "page": page, "per_page": 20, "total": total,
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
