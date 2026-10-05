        return url_for("static", filename=image)
    category = getattr(getattr(product, "category", None), "name", "") or ""
    return PRODUCT_FALLBACK_IMAGES.get(category, PRODUCT_FALLBACK_IMAGES["default"])


app.jinja_env.globals["product_image_url"] = product_image_url


# =========================================================
# CSRF PROTECTION
# =========================================================

def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
        session["_kharidino_csrf_token"] = token
    elif not session.get("_kharidino_csrf_token"):
        session["_kharidino_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def validate_csrf():
    # Every rendered page gets a token. Keeping one token for the browser session
    # prevents ordinary navigation and multi-tab use from invalidating open forms.
    csrf_token()

    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    submitted = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or ""
    )
    expected = session.get("csrf_token") or session.get("_kharidino_csrf_token") or ""

    # If an old/invalid development session cookie was discarded by Flask, allow
    # a public form carrying its own token to establish the fresh session token.
    # Authenticated sessions still require an exact token match.
    if not expected:
        if submitted and not session.get("user_id"):
            session["csrf_token"] = str(submitted)
            session["_kharidino_csrf_token"] = str(submitted)
            session.modified = True
            return None
        abort(403, description="CSRF token is missing or invalid.")

    if not submitted or not secrets.compare_digest(
        str(submitted), str(expected)
    ):
        # Public authentication/onboarding forms can legitimately remain open
        # across a session refresh (for example after restarting the dev server).
        # Rebind their anonymous session to the submitted form token instead of
        # returning a confusing 400. Authenticated mutations remain strict.
        public_recovery_endpoints = {
            "login",
            "register",
            "seller_register",
            "organization_request",
        }
        if not session.get("user_id") and request.endpoint in public_recovery_endpoints and submitted:
            session["csrf_token"] = str(submitted)
            session.modified = True
            return None
        abort(403, description="CSRF token is missing or invalid.")

    return None




@app.errorhandler(400)
def handle_bad_request(error):
    """Normalize malformed state-changing requests with missing CSRF to 403.

    Some Werkzeug/Flask request parsing paths can raise BadRequest before the
    route-level security layer gets a chance to emit its canonical CSRF status.
    Only convert the unambiguously CSRF-shaped case; ordinary 400 responses keep
    their original status and payload.
    """
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.headers.get("X-CSRF-Token")
        try:
            supplied = supplied or request.form.get("csrf_token")
        except Exception:
            supplied = supplied or ""
        if not supplied:
            description = getattr(error, "description", "") or ""
            if "CSRF" in description.upper() or not description:
                return "CSRF token is missing or invalid.", 403
    return error


def send_kharidino_email(to_email, subject, body):
    """Send SMTP email using either Kharidino or standard .env variable names."""
    to_email = (to_email or "").strip()
    smtp_host = (
        os.environ.get("KHARIDINO_SMTP_HOST", "").strip()
        or os.environ.get("SMTP_HOST", "").strip()
    )
    smtp_user = (
        os.environ.get("KHARIDINO_SMTP_USER", "").strip()