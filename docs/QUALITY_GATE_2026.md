# Kharidino 2026 Quality Gate

Before merging the ultimate storefront/admin branch:

- Python test suite must pass.
- Security hardening tests must pass.
- Ultimate CSS/JS assets must exist and be loaded globally.
- Product cards must have a real image or a deterministic candidate fallback.
- Product detail must not fabricate technical specifications; missing data is shown as missing.
- Checkout idempotency must be database-backed and safe across app instances.
- State-changing requests require same-origin and CSRF validation.
- Uploads are bounded and content-validated.
- Production must reject known/default secret keys.
