"""Production WSGI entrypoint for Kharidino."""
from app import app
from kharidino_ai import register as register_ai
from mobile_app.api.mobile_api import register_mobile_api
from app import db, Product, Category, Store, Offer, User, admin_required
from security_hardening import apply_security
from inventory_hardening import apply_inventory_security
from commerce_extensions_v2 import apply_commerce_extensions
from commerce_catalog import apply_catalog_extensions
import commerce_runtime  # noqa: F401 - registers secure checkout/address hooks

register_ai(app, db, Product, Store, Offer, User, admin_required)
register_mobile_api(app, db, Product, Category, Store, Offer)

with app.app_context():
    apply_security(app)
    apply_inventory_security(app)
    apply_commerce_extensions(app)
    apply_catalog_extensions(app)
    db.create_all()
