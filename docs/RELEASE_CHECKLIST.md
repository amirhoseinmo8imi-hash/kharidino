# Release checklist — 2026-09-08

## Automated gates

- [x] Python CI green on current head
- [x] Security CI green on current head
- [x] Ultimate smoke suite covered by CI
- [x] Checkout preflight regression coverage
- [x] Checkout replay/idempotency protection covered
- [x] Payment lifecycle and callback security contracts covered
- [x] Order lifecycle/state-machine contracts covered
- [x] Inventory atomicity and rollback contracts covered
- [x] IDOR/security hardening covered
- [x] Redirect hardening covered
- [x] Upload limits and security audits covered
- [x] Production secret policy covered by security checks

## Release-path audit

- [x] Login/register flow uses POST forms with CSRF protection
- [x] Product → cart flow remains presentation-compatible with the hardened cart endpoints
- [x] Checkout collects bounded customer name, phone, address and note fields
- [x] Checkout preflight validates authentication, cart contents, customer fields and request limits
- [x] Checkout → payment bridge binds the created order to the authenticated user
- [x] Payment start is POST-only for state change and protected by idempotency
- [x] Payment callback validates transaction ownership, amount, authority and callback state
- [x] Paid order transition is persisted only after gateway verification
- [x] Order detail is user-scoped and exposes status/history safely
- [x] Admin refund transition is role-gated and state-gated

## Production blockers / manual gates

- [ ] Real Iranian bank gateway adapter connected and provider credentials configured
- [ ] Production payment callback endpoint tested against the selected bank/provider
- [ ] Browser-based manual smoke: login → product → cart → checkout → payment → order history
- [ ] Browser-based mobile smoke on a real Android/iOS device
- [ ] Production environment variables/secrets installed outside Git
- [ ] Final merge only after the manual production gates above are complete

## Important

The current payment implementation intentionally uses `DisabledGateway` unless `PAYMENT_TEST_MODE=1`. `TestGateway` is suitable for deterministic automated flow testing, not for collecting real money. The project must not be advertised as having live bank payment until a real provider adapter is implemented and verified.
