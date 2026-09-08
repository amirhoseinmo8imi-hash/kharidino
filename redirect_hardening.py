"""Final redirect safety net for browser navigation routes."""
from urllib.parse import urlparse

from flask import request, url_for


# Payment gateways intentionally return an external URL. Every other browser
# redirect produced by the application must remain same-site.
_EXTERNAL_REDIRECT_ENDPOINTS = {"payment_start"}


def _safe_local_target(target: str | None) -> bool:
    target = (target or "").strip()
    if not target or "\\" in target or any(ord(ch) < 32 for ch in target):
        return False
    if not target.startswith("/") or target.startswith("//"):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and not parsed.username and not parsed.password


def apply_redirect_hardening(app):
    """Prevent attacker-controlled Referer/Location values from becoming open redirects."""
    if getattr(app, "_kharidino_redirect_hardening", False):
        return app

    @app.after_request
    def _redirect_headers(response):
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        if request.endpoint in _EXTERNAL_REDIRECT_ENDPOINTS:
            return response
        location = response.headers.get("Location", "")
        if location and not _safe_local_target(location):
            response.headers["Location"] = url_for("home")
        return response

    app._kharidino_redirect_hardening = True
    return app
