"""Final redirect safety net for browser navigation routes."""
from urllib.parse import urlparse

from flask import url_for


def _safe_local_target(target: str | None) -> bool:
    target = (target or "").strip()
    if not target or "\\" in target or any(ord(ch) < 32 for ch in target):
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and not parsed.username and not parsed.password


def apply_redirect_hardening(app):
    """Prevent a route from reflecting an attacker-controlled external Referer."""
    if getattr(app, "_kharidino_redirect_hardening", False):
        return app

    @app.after_request
    def _redirect_headers(response):
        if request_endpoint := getattr(__import__("flask"), "request", None):
            if request_endpoint.endpoint == "compare_remove" and response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location", "")
                if not _safe_local_target(location):
                    response.headers["Location"] = url_for("compare")
        return response

    app._kharidino_redirect_hardening = True
    return app
