"""Production WSGI entrypoint for Kharidino."""
from app import app
from kharidino_ai import register as register_ai
from mobile_app.api.mobile_api import register_mobile_api
from app import db, Product, Category, Store, Offer, User, admin_required
from security_hardening import apply_security
from inventory_hardening import apply_inventory_security
from commerce_extensions_v2 import apply_commerce_extensions

register_ai(app, db, Product, Store, Offer, User, admin_required)
register_mobile_api(app, db, Product, Category, Store, Offer)
apply_security(app)
apply_inventory_security(app)
apply_commerce_extensions(app)

with app.app_context():
    db.create_all()
