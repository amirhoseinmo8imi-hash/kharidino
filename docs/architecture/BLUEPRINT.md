# Kharidino Super App — Architecture Blueprint

Status: Product and technical blueprint | Decision date: 2026-11-17
Clients: Responsive web + independent native Android application.

## 1. Confirmed product decisions
- Cinema: both licensed films/series and creator-published video. Licensed titles require documented distribution rights, territory and time-window rules. Creator uploads require moderation, copyright reporting, takedown and appeal workflows.
- Marketplace: both verified businesses/stores and individual sellers. Keep catalog products, seller-specific offers and classified listings as separate concepts.
- Clients: responsive web and native Android. Both use the same versioned backend API; business rules remain server-side.

## 2. Product domains
1. Identity and trust: accounts, profiles, sessions, roles/permissions, seller verification, reports, moderation and audit trail.
2. Marketplace: catalog, categories, brands, attributes, stores, seller offers, inventory, price history, comparison, cart, checkout, orders, returns, disputes and reviews.
3. Classifieds: person-to-person listings, condition, safe contact/messaging, expiry, fraud reports. Keep classified transactions separate from managed checkout until operational controls exist.
4. Cinema: titles, seasons, episodes, metadata, artwork, trailers, subtitles, playback entitlements, watch progress, watchlist and licensing windows.
5. Creator Studio: creator profiles, upload sessions, drafts, publishing, rights declarations, moderation queue, copyright claims, takedowns, appeals and analytics.
6. Future domains: learning, courses, local services, bookings, jobs and business profiles.
7. Shared platform: global search, recommendations, notifications, support, promotions, payment orchestration, wallet ledger and admin console.

## 3. Recommended architecture
Start with a modular monolith, not premature microservices. Flask is a practical starting point; progressively split the current single-file app into an application factory, domain packages, service layer and blueprints. Preserve explicit boundaries so high-load domains can be extracted later.

```text
Responsive Web       Native Android (Kotlin + Jetpack Compose)
       \                         /
        ------ Versioned API ------
                    |
             Flask application
                    |
  Identity | Marketplace | Classifieds | Cinema
  Creators | Payments    | Search      | Admin
                    |
       PostgreSQL  + Redis + Workers
                    |
       S3-compatible object storage
                    |
        FFmpeg processing + CDN
```

### Backend and data
- Keep Flask for the first migration; introduce an application factory, configuration profiles, domain modules, service layer and versioned `/api/v1` endpoints.
- Use PostgreSQL for production relational data and Alembic/Flask-Migrate for schema changes. SQLite is acceptable for local development and lightweight tests, not production multi-user workloads.
- Use Redis for cache, rate limits and task coordination. Use Celery or RQ workers for notifications, image processing, video transcoding, search indexing and analytics.
- Store media outside the app server in S3-compatible object storage. Use CDN for public media and short-lived signed URLs for private assets.
- Enforce HTTPS, secure cookies, CSRF for browser flows, API authentication, server-side authorization, rate limits, upload validation/scanning, structured logs and audit events. No development fallback secrets in production.

### API and Android
- Publish OpenAPI contracts under `/api/v1`; standardize pagination, filtering, errors, request IDs and idempotency keys for checkout/payment operations.
- Use secure browser sessions for web. Native Android should use short-lived access tokens with refresh-token rotation/revocation and Android Keystore-backed secure storage. Authorization always remains server-side.
- Build native Android in Kotlin with Jetpack Compose, Navigation, ViewModel, coroutines/Flow, Retrofit or Ktor, and Room for scoped offline cache.
- Suggested Android feature modules: core/design-system, auth, home, marketplace, cinema, creator, services, profile and notifications. Support RTL, Persian typography, accessibility, deep links and push notifications.
- Web and Android share API contracts and business rules, not necessarily UI code.

### Video pipeline
1. Client requests a scoped upload session; backend checks uploader permissions and returns a short-lived direct-upload URL.
2. Upload enters a private quarantine bucket; it is not public.
3. Worker validates media, scans where supported, extracts metadata and creates adaptive HLS renditions and thumbnails.
4. Rights and moderation checks run. Pending or rejected assets remain private.
5. Approved media is published and delivered through CDN/signed playback URLs; playback entitlements are checked server-side.
6. Licensed premium content may require DRM/provider integrations. Do not promise copy-proof playback.

### Commerce and payments
- Separate Product (shared catalog identity) from SellerOffer (seller-specific price, stock, condition and fulfillment); this is foundational for trustworthy price comparison.
- Model orders, payment attempts, refunds and wallet ledger entries as auditable records. A wallet must use immutable ledger entries, not just a mutable balance.
- Use a payment-provider adapter; never store raw card details. Seller onboarding, verification, commissions, payouts, invoices, taxes and disputes require explicit operational/legal decisions.

## 4. Conceptual data boundaries
- Identity: User, Profile, Role, Permission, Session, SellerVerification, Device.
- Marketplace: Category, Brand, Product, ProductAttribute, Store, SellerOffer, InventoryMovement, PriceSnapshot, Cart, CartItem, Order, OrderItem, Shipment, Return, Review, Favorite.
- Classifieds: Listing, ListingImage, ListingCategory, ListingConversation, ListingReport.
- Cinema: MediaTitle, Season, Episode, MediaAsset, SubtitleTrack, License, PlaybackEntitlement, SubscriptionPlan, WatchProgress, WatchlistItem.
- Creator: CreatorProfile, UploadSession, ModerationCase, CopyrightClaim, ContentReport.
- Shared: Payment, Refund, LedgerEntry, Notification, Promotion, SupportTicket, AuditEvent.
- Use foreign keys, uniqueness constraints, indexes, timestamps and tested migrations. Do not couple commerce products to cinema media records.

## 5. Delivery roadmap and exit criteria
### Phase 0 — Audit and foundation
- Inventory routes, templates, models, tests, mobile API and AI module. Add CI, environment validation, logging, migration/rollback strategy and architecture decision records.
- Exit: reproducible setup, automated tests, API baseline and safe migration plan.
### Phase 1 — Marketplace MVP
- Finish seller onboarding/storefronts, seller offers, catalog, search, comparison, inventory, cart, checkout and order lifecycle. Add PostgreSQL migrations and payment sandbox adapter.
- Exit: buyer compares offers and places a test order; seller/admin process it end-to-end.
### Phase 2 — Native Android and shared identity
- Stabilize `/api/v1`; build native auth, home, search, product, seller, cart, orders and profile. Add deep links and push notifications.
- Exit: web and Android share account and order state; API contract tests pass.
### Phase 3 — Cinema foundation
- Build catalog, title pages, watchlist, entitlements, private storage, HLS pipeline and CDN. Pilot a small rights-cleared catalog.
- Exit: reliable pilot playback with entitlement checks and monitoring.
### Phase 4 — Creator video
- Add creator onboarding, upload pipeline, moderation, copyright reports, takedown and appeals. Publish only after required checks.
- Exit: safe end-to-end creator upload and publication.
### Phase 5 — Classifieds and community
- Add person-to-person listings, contact/messaging, trust signals, reporting, anti-fraud controls, follows and moderated community features.
### Phase 6 — Learning, services and scale
- Add courses, bookings, jobs and local services as separate modules. Scale based on measured bottlenecks using cache, search, CDN and selective service extraction.

## 6. Non-functional requirements
- Privacy/security by design, least privilege, auditability and clear data retention rules.
- RTL, localization, responsive UI and accessibility.
- Structured logs, metrics, tracing, error monitoring and health checks.
- Backups with restore drills; define recovery objectives before production.
- Unit, integration, API contract, migration, permission, upload and critical end-to-end tests.
- Load tests for search, catalog, checkout and playback.
- Content safety, copyright compliance, user reporting and appeals.

## 7. Immediate engineering sequence
1. Complete source audit of the default branch: routes, models, templates, tests, mobile API and AI module.
2. Map current product/store/offer/order logic to the domain model; preserve compatibility.
3. Track implementation backlog and baseline automated tests.
4. Implement foundation changes on a feature branch, beginning with tests and migrations.
5. Do not deploy, change payment credentials, publish content or modify production data without an explicit release decision.


## Iran-first launch profile
- Initial launch market is Iran. Prioritize Persian RTL UX, Iranian mobile-number normalization, local address/postal-code forms, local delivery and customer support.
- All monetary records must carry an explicit currency. For the initial market, use integer rial (IRR) as the canonical backend/payment unit and display toman in customer UI (1 toman = 10 rial). Centralize conversion and formatting; verify each payment provider's exact amount unit before integration.
- Keep payment, SMS/OTP, shipping and invoicing providers behind adapters. Provider selection depends on merchant eligibility, contracts, fees, settlement and credentials; use sandbox mode first.
- Order creation and payment confirmation are separate states. Verify callbacks server-to-server, use idempotency and unique provider references, and never trust a client redirect as proof of payment.
- Before public launch, confirm applicable local requirements for e-commerce, privacy, consumer protection, tax/invoicing, seller identity, licensed media and payment processing with qualified local counsel/providers.

## 8. Assumptions still to confirm
- Initial launch country/market, currencies, payment providers, delivery partners and legal entity.
- Cinema licensing territories, rights windows and business model (subscription, rental, purchase, ads or mixed).
- Moderation policy, age restrictions, privacy/retention policy and seller verification rules.
- No production credentials, Android signing keys, private media or payment secrets belong in Git.
