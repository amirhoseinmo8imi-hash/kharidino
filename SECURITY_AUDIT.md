# Kharidino Security Audit — 2026-09-06

## Findings addressed

### Critical
- Removed reliance on the known `change-this-secret-key` value in production by adding a fail-closed production check and a random development fallback.

### High
- Hardened Flask session cookie settings: HttpOnly, SameSite=Lax, Secure in production, dedicated cookie name.
- Added same-origin protection for state-changing requests as a CSRF defense-in-depth layer.
- Added login/register and AI API rate limiting.
- Added security response headers including CSP, HSTS in HTTPS/production, frame protection, MIME sniffing protection, Referrer-Policy, Permissions-Policy, COOP and CORP.
- Added request size/part limits through Flask configuration.

### Verification
- Added automated tests for headers, cookie flags, same-origin enforcement and production secret rejection.
- Added a production WSGI entrypoint that always applies the hardening layer.
- Launcher applies the same hardening for local runs.

## Remaining follow-up
- Add explicit hidden CSRF tokens to every browser form for stronger CSRF protection.
- Validate uploaded image/video content with Pillow/ffprobe and strip risky metadata where appropriate.
- Review every admin POST endpoint and ensure authorization is enforced.
- Run dependency vulnerability scanning in CI.
- Rotate any real credentials that may previously have been exposed outside the repository.
