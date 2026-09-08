"""Public catalog authorization and input hardening."""
from flask import abort, request


def apply_catalog_security(app):
    if getattr(app, "_kharidino_catalog_security", False):
        return app

    @app.before_request
    def _catalog_security():
        # Public product/store URLs must not expose unpublished entities by ID.
        if request.endpoint == "product_detail" and request.view_args:
            from app import db, Product
            product = db.session.get(Product, request.view_args.get("product_id"))
            if not product or not product.active:
                abort(404)
        elif request.endpoint == "store_detail" and request.view_args:
            from app import db, Store
            store = db.session.get(Store, request.view_args.get("store_id"))
            if not store or not store.active:
                abort(404)

        # Bound search input prevents pathological oversized LIKE queries while
        # retaining normal Persian/Latin product searches.
        if request.endpoint in {"home", "category"} and request.method == "GET":
            q = request.args.get("q")
            if q is not None and len(q) > 100:
                copied = request.args.copy()
                copied["q"] = q[:100]
                request.args = copied

    app._kharidino_catalog_security = True
    return app
