"""Recommended launcher for Kharidino with the AI control plane enabled."""
import os

from app import app, db, Product, Store, Offer, User, admin_required
from kharidino_ai import register as register_ai

register_ai(app, db, Product, Store, Offer, User, admin_required)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    # Debug is opt-in, never the default.
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
