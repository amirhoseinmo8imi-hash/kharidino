"""Production security hardening for Kharidino.

This module is deliberately small and framework-level: it can be applied from
both the development launcher and a production WSGI entrypoint without
rewriting the existing route file.
"""
from __future__ import annotations

import os
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from flask import request, abort


_INSECURE_KEYS = {"", "change-this-secret-key", "dev-secret", "secret"}
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def _is_production() -> bool:
    return os.environ.get("FLASK_ENV", "").lower() == "production" or os.environ.get("KHAIDINO_PRODUCTION", "").lower() in {"1", "true", "yes"}


def apply_security(app):
    """Apply security defaults and request/response protections once."""
    if getattr(app, "_kharidino_security_applied", False):
        return app

    configured_key = os.environ.get("SECRET_KEY", "").strip()
    if configured_key in _INSECURE_KEYS:
        if _is_production():
            raise RuntimeError("SECRET_KEY must be set to a strong random value in production.")
        # Never use a known constant even in development.
        app.config["SECRET_KEY"] = secrets.token_urlsafe(48)
    else:
        app.config["SECRET_KEY"] = configured_key

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", _is_production())
    app.config.setdefault("SESSION_COOKIE_NAME", "kharidino_session")
    app.config.setdefault("MAX_FORM_MEMORY_SIZE", 2 * 1024 * 1024)
    app.config.setdefault("MAX_FORM_PARTS", 200)

    @app.before_request
    def _security_before_request():
        # Never trust a browser-supplied Host when constructing security policy.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            _check_same_origin()

        if request.path in {"/login", "/register"} and request.method == "POST":
            _rate_limit("auth", limit=10, window=300)

        if request.path.startswith("/admin/kharidino-ai/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            _rate_limit("ai", limit=30, window=60)

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.is_secure or _is_production():
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Keep CSP compatible with the existing inline UI while still blocking
        # plugins/objects and restricting unexpected network destinations.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https:; font-src 'self' data: https:; media-src 'self' blob: https:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'",
        )
        return response

    app._kharidino_security_applied = True
    return app


def _client_ip() -> str:
    # Do not trust X-Forwarded-For unless the deployment explicitly has a
    # trusted proxy layer configured. Remote address is the safe default.
    return request.remote_addr or "unknown"


def _rate_limit(name: str, *, limit: int, window: int) -> None:
    now = time.monotonic()
    bucket = _RATE_BUCKETS[f"{name}:{_client_ip()}"]
    cutoff = now - window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) >= limit:
        abort(429, description="Too many requests. Please try again later.")
    bucket.append(now)


def _check_same_origin() -> None:
    """Reject obvious cross-site state-changing requests.

    This is a defense-in-depth CSRF layer. Existing forms remain compatible;
    requests must originate from the same host when Origin/Referer is present.
    """
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    candidate = origin or referer
    if not candidate:
        if os.environ.get("KHAIDINO_ALLOW_ORIGINLESS_POST", "0").lower() in {"1", "true", "yes"}:
            return
        # Non-browser API clients can explicitly opt in with a bearer token
        # outside this module; normal browser forms should send Origin/Referer.
        if request.path.startswith("/api/") and request.is_json:
            return
        abort(403, description="Missing Origin/Referer on state-changing request.")

    parsed = urlparse(candidate)
    if not parsed.netloc:
        abort(403, description="Invalid request origin.")
    expected = request.host.lower()
    if parsed.netloc.lower() != expected:
        abort(403, description="Cross-site state-changing request blocked.")
