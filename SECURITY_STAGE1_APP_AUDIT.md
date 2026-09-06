# Kharidino — Stage 1 `app.py` Security Audit

Date: 2026-09-06
Base: `main`
Scope: `app.py` core Flask application, authentication, session handling, redirects, uploads, cart/checkout/order logic, admin authorization, database access, and runtime configuration.

## Confirmed findings

### CRITICAL/HIGH

1. **`SECRET_KEY` insecure fallback remains in `app.py`.**
   - `app.config["SECRET_KEY"]` falls back to `change-this-secret-key`.
   - `security_hardening.py` replaces/rejects this when the production WSGI entrypoint is used, but direct execution of `app.py` does not apply that hardening.
   - Required fix: remove the known fallback from application configuration and make production fail closed.

2. **Development server starts with `debug=True`.**
   - `app.py` runs Flask with debug enabled.
   - Required fix: default to `False`; allow explicit local development opt-in only.

3. **Open redirect in compare flow.**
   - `/compare/add/<product_id>` redirects to `request.form.get("next")` without validating that it is same-origin.
   - Required fix: centralize `is_safe_redirect_target()` and only allow same-origin relative paths.

4. **Logout is state-changing but exposed as `GET`.**
   - `/logout` mutates the session while accepting GET.
   - The production hardening layer also expects CSRF protection for logout, which makes the current GET contract inconsistent with the intended security model.
   - Required fix: change logout to POST and add an explicit CSRF token in the browser UI.

5. **Default admin credentials are hard-coded in `seed()`.**
   - A fresh database creates `admin@kharidino.local` with password `admin12345`.
   - Required fix: never seed a known password; require an environment-provided bootstrap credential or create the first admin through a secure one-time setup flow.

### MEDIUM

6. **Upload validation in `app.py` is extension-only.**
   - `save_upload()` validates only the filename extension and then writes the file.
   - `security_hardening.py` performs stronger MIME/content validation when the hardened WSGI entrypoint is used, but direct app execution bypasses it.
   - Required fix: make upload validation part of the application path itself and keep content validation mandatory.

7. **External store/offer URLs are accepted from admin forms without scheme/host validation.**
   - `Store.website` and `Offer.url` are stored from raw form input.
   - Required fix: allow only `https`/`http` as appropriate, normalize URLs, and reject dangerous schemes such as `javascript:` and `data:`.

8. **Admin error message can expose internal exception text.**
   - `admin_background()` flashes the raw exception string.
   - Required fix: log the exception server-side and return a generic user-facing error.

9. **Checkout has no idempotency protection.**
   - Repeated POSTs can create multiple orders before the cart is cleared.
   - Required fix: add a one-time checkout nonce/idempotency key stored in session and consumed transactionally.

10. **Cart has no inventory/stock quantity model.**
    - Quantity is capped at 99, but there is no server-side inventory quantity to prevent ordering unavailable quantities.
    - Required fix: introduce authoritative inventory/availability checks before order creation.

## Positive findings

- Passwords use Werkzeug password hashing rather than plaintext storage.
- SQL access uses SQLAlchemy query APIs; no obvious raw SQL concatenation was found in `app.py`.
- Admin routes consistently use `@admin_required`.
- User order listing is scoped by `user_id`.
- Review deletion checks ownership or admin role.
- Cart prices are recalculated from server-side product/offer data rather than trusting client-submitted prices.
- Upload filenames are sanitized and generated filenames use UUIDs.
- `remove_upload()` resolves paths and verifies they remain under the static root.
- Production WSGI already wires `security_hardening.apply_security()`.

## Stage 1 decision

**Do not merge this branch yet.** The audit found real application-level issues that must be fixed before treating the security hardening as complete. Stage 2 should address redirects, logout/CSRF integration, bootstrap admin credentials, URL validation, error handling, and the direct-run security configuration before template-wide CSRF work proceeds.
