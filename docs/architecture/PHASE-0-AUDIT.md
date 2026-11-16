# Phase 0 — Initial Source Audit

**Repository:** `amirhoseinmo8imi-hash/kharidino`  
**Audited ref:** `main`  
**Date:** 2026-11-17  
**Scope:** Read-only inspection of selected source files. This is not a full repository or runtime audit.

## Confirmed from source

| Area | Evidence | Finding |
|---|---|---|
| Application entry | `app.py` | Flask application and SQLAlchemy models are defined in a large single module. |
| Database | `app.py` | Database URI is hard-coded to a local SQLite file. |
| Core catalog | `app.py` | Category, Product, Store and Offer models exist. |
| Seller marketplace | `app.py` | Store and Offer exist, but the inspected schema does not yet show independent seller accounts, seller ownership, stock ledger, fulfillment or payouts. |
| Commerce | `app.py` | User, Order and OrderItem exist. Checkout validates customer details and creates an order; inspected flow does not create a payment transaction or call a payment gateway. |
| Currency | `app.py` | Prices/totals are integers and the template money filter adds thousands separators only. No explicit currency code or conversion policy was found in inspected lines. |
| Mobile API | `mobile_app/api/mobile_api.py` | Existing prefix is `/api/mobile`; health, categories, products, product detail and search are GET endpoints. No authentication, checkout, account or order endpoints are present in this module. |
| Mobile bootstrap | `run_kharidino.py` | Registers the mobile API, AI module and security module. |
| Security | `security_hardening.py` | Includes session cookie flags, CSRF helpers, request size limits and other shared protections. Requires test and route-coverage review before production. |
| AI control plane | `kharidino_ai.py` | Describes itself as read-only and produces health snapshots/repair plans; no automatic code/database executor should be assumed. |
| Tests | `tests/test_kharidino_ai.py`, `tests/test_redirect_hardening.py` (observed in repository history) | A small set of targeted tests exists. Full test inventory and execution status have not yet been verified. |

## Iran-first product and technical decisions

1. **Launch market:** Iran. First release should focus on Persian language, RTL, Iranian phone numbers, local address/postal-code formats, local delivery workflows and support.
2. **Currency model:** Use an explicit currency field in all monetary records. For the initial Iranian market, define a single canonical integer amount in **rial (IRR)** in backend/payment records and display **toman** in customer-facing UI (1 toman = 10 rial). Conversion must happen in one tested money-formatting/payment adapter layer; never infer currency from an integer. Confirm each selected provider's exact amount unit before integration.
3. **Gateway abstraction:** Build a provider-neutral payment interface with create-payment, verify-payment, refund/status-query and webhook/callback handling. Start in sandbox/test mode. Do not choose or hard-code a provider until merchant eligibility, contracts, fees, settlement and required credentials are confirmed.
4. **Order/payment separation:** Order creation and payment confirmation must be separate states. Treat browser/app callback as untrusted until server-to-server verification succeeds. Use idempotency and unique provider references to prevent duplicate charges or duplicate order transitions.
5. **Local integrations:** Keep SMS/OTP, shipping, invoice and payment vendors behind adapters. Vendor choice is a business/legal decision; credentials stay in secret storage, never Git.
6. **Compliance gate:** Before public launch, confirm applicable Iranian e-commerce, privacy, consumer protection, tax/invoicing, seller identity, content licensing and payment-provider requirements with qualified local counsel and providers. This blueprint is engineering planning, not legal advice.

## Critical gaps before production

- No confirmed production PostgreSQL configuration or migration history in the inspected files.
- Existing API is a small read-only catalog API, not yet a complete authenticated versioned client API.
- No confirmed payment gateway integration; checkout currently records an order without charging or verifying payment.
- Product and Offer models need a reviewed migration toward Product + SellerOffer with seller ownership, condition, stock/fulfillment and currency.
- No confirmed classified-listing domain, cinema catalog, licensing/entitlement model, creator upload/moderation pipeline or media processing/CDN integration.
- Native Android source/build configuration has not yet been located or verified; the existence of a mobile API does not prove a native Android app is implemented.
- Full route inventory, template inventory, dependency/security review, automated test run, backup/restore test and deployment review remain outstanding.

## Recommended next actions

1. Inventory all tracked files and tests; run the existing test suite in a reproducible environment.
2. Add an explicit money/currency policy and tests before touching checkout.
3. Design PostgreSQL schema and reversible migrations; preserve existing SQLite data with a tested export/import plan.
4. Introduce `/api/v1` with authentication, authorization, validation, pagination and OpenAPI contract tests; keep old mobile routes temporarily for compatibility.
5. Design seller onboarding and SellerOffer ownership before multi-vendor checkout.
6. Build payment sandbox adapter and verified payment state machine before accepting real money.
7. Start native Android only after the API contract and identity flows are stable.

## Audit limitations

This document records only source facts directly inspected on the audited ref. It does not claim that uninspected files or external services are absent, nor that the application has passed runtime, load, security or legal review.
