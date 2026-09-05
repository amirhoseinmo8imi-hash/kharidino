"""Recommended launcher for Kharidino Ultimate.

Enables the AI control plane and the cinematic first-entry splash without
changing the original app.py runtime contract.
"""
import os

from flask import redirect, request, render_template

from app import app, db, Product, Store, Offer, User, admin_required
from kharidino_ai import register as register_ai

register_ai(app, db, Product, Store, Offer, User, admin_required)


@app.get("/splash")
def kharidino_splash():
    return render_template("kharidino_splash.html")


@app.before_request
def splash_gate():
    # Static assets, splash itself, and AI API calls must be reachable before
    # the splash cookie exists. The AI API routes still enforce admin access
    # through @admin_required inside kharidino_ai.py.
    if (
        request.path.startswith("/static/")
        or request.path.startswith("/splash")
        or request.path.startswith("/admin/kharidino-ai/api/")
    ):
        return None
    if request.cookies.get("kharidino_splash") != "1":
        return redirect("/splash")
    return None


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
