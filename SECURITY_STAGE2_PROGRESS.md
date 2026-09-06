# Kharidino Security Stage 2

Branch: `security/audit-stage1-2026-09-06`

## Applied in this stage

- Central CSRF + same-origin enforcement remains active for POST/PUT/PATCH/DELETE.
- Unsafe login `next` values are rejected, including backslash/control-character tricks.
- Checkout validates that every cart item is active and has at least one active store offer with `in_stock=true` and a positive price.
- Checkout replay protection now fingerprints the authenticated user, cart and customer fields and rejects repeated submissions within a short window.
- Unexpected application exceptions are logged server-side and replaced with a generic 500 response.
- Upload content validation remains enforced by extension + MIME/content inspection.
- Mobile catalog API remains read-only and rate limited.
- Static security audit and dependency audit pass in CI.

## Verified CI

Workflow run `34051128668` completed successfully:

- Python compile: pass
- Static security audit: pass
- pip-audit: pass (`No known vulnerabilities found`)
- pytest: pass (`10 passed`)

## Still requires a dedicated follow-up

- The current product model has a boolean `Offer.in_stock`, not a numeric inventory quantity. Quantity-level inventory/atomic decrement requires a database/model migration.
- Checkout replay protection in this stage is process-local; a DB-backed idempotency key is the next hardening step for multi-worker deployments.
- Complete template-by-template XSS/`|safe` audit and explicit CSRF hidden-field coverage should continue. Base template JavaScript currently supplies CSRF fields dynamically.
- The admin sidebar contains a legacy GET logout link while `/logout` is POST-only; the template should be converted to a POST form in the next UI/security pass.
- Full end-to-end IDOR tests for every user-owned resource should be added to the test suite.
