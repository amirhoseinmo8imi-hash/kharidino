"""Early, safe route scaffolding for Kharidino's media discovery hubs.

These pages intentionally do not pretend to have a media pipeline or licensed
streaming catalog yet. They provide navigable product surfaces while the data,
moderation, upload and entitlement layers are developed.
"""
from flask import render_template


def register_media_hubs(app):
    if "kharidino_explore" not in app.view_functions:
        @app.route("/explore", endpoint="kharidino_explore")
        def kharidino_explore():
            return render_template("media_hub.html", hub="explore")

    if "kharidino_reels" not in app.view_functions:
        @app.route("/reels", endpoint="kharidino_reels")
        def kharidino_reels():
            return render_template("media_hub.html", hub="reels")

    if "kharidino_cinema" not in app.view_functions:
        @app.route("/cinema", endpoint="kharidino_cinema")
        def kharidino_cinema():
            return render_template("media_hub.html", hub="cinema")
