# Kharidino 2026 — Full Code & Product Review

## Scope
Source-level review of the premium-design branch focused on Flask routes/models, initialization, security boundaries, templates, global CSS/JS loading, checkout/payment/marketplace structure, admin/seller/organization/invoice/vehicle surfaces, and mobile/PWA behavior.

This review is conservative: legacy CSS and commerce modules are not deleted blindly because the repository has accumulated page-specific dependencies.

## Fixed in this pass

### Global CSS overload
templates/base.html was loading 23 CSS files globally. Several are clearly page-specific and multiple 2026 polish layers overlap.

Action:
- Added static/css/kharidino-modern-shell-2026.css.
- Added design tokens, stable focus states, mobile shell improvements and dark-mode surfaces.
- Existing CSS remains for compatibility.

Next:
- Build a route-to-asset manifest.
- Move admin/invoice/vehicle/seller CSS out of the global shell.
- Delete legacy files only after page-level smoke/screenshot coverage.

### Dark mode
Added static/js/kharidino-theme.js and a persistent light/dark toggle. Manual choice is stored in localStorage; OS preference is used when no choice exists.

### Invalid document structure
The vehicle unread-notification script was after </html>. It is now placed before </body>.

### CSRF fetch scope
The global fetch wrapper previously attached X-CSRF-Token to every state-changing fetch. It now attaches the token only for same-origin targets.

### Security/session
Previous work unified the application CSRF session key and stopped security hardening from replacing the application's configured secret/session namespace.

## Product gaps compared with Iranian marketplace patterns

### Price intelligence
Emalls pages visibly provide price-change charts and seller-level price freshness. citeturn4search0turn4search1

Kharidino already has price alerts, but should add:
1. PriceHistory records for offer updates.
2. 7/30/90-day min/avg/max.
3. Price-history chart.
4. Last-update and stale-price badges.
5. Target-price and percentage-drop alerts.

### Seller trust
Iranian marketplace comparisons emphasize transaction safety, seller communication and buyer/seller interaction. citeturn0search0turn0search5

Add:
- seller verification levels;
- response rate/time;
- fulfilled-order count;
- cancellation rate;
- seller rating;
- dispute/report flow;
- verified-purchase review labels.

### Returns and disputes
Return policy and support/dispute resolution are major e-commerce quality dimensions. citeturn0search6

Add:
- return-request state machine;
- reason/evidence;
- seller response deadline;
- admin mediation queue;
- refund SLA;
- customer-visible timeline.

### Vehicle marketplace
Divar's public developer documentation exposes structured vehicle filters including brand/model, production year and usage. citeturn0search8turn0search10

Kharidino already has a separate vehicle surface and chat. Next:
- brand/model/year/mileage/price filters;
- city/location;
- verified listing badge;
- seller type;
- inspection status;
- saved searches;
- price-change notification.

### Store comparison and freshness
Emalls emphasizes seller comparison, credibility and freshness of price data. citeturn0search1

Improve the comparison table with:
- cheapest seller;
- delivery estimate;
- seller rating;
- stock state;
- last price update;
- warranty;
- shipping estimate;
- direct purchase CTA.

## Recommended architecture

A. Core storefront: Search, categories, product, offers, stores, compare, cart, checkout, orders.

B. Marketplace: seller onboarding/KYC, seller storefront, analytics, fulfillment, settlement.

C. Trust: reviews, verified purchase, seller reputation, returns, disputes, fraud/report queue.

D. Price intelligence: price history, alerts, stale-price detection, market min/avg/max, similar-product comparison.

E. Vehicle: dedicated navigation, search/filter, detail, chat, saved searches, verification, price intelligence.

F. Admin: KPI dashboard, orders, sellers, organization requests, invoices, returns/disputes, moderation, inventory, accounting, system health, audit log.

## Priority

1. P0: Run real CI and local smoke tests.
2. P0: Verify every url_for endpoint and remove dead links.
3. P1: Reduce global CSS through route-to-asset mapping.
4. P1: Add price history and freshness.
5. P1: Add seller trust/reputation and verified-purchase reviews.
6. P1: Add returns/dispute state machine.
7. P2: Upgrade vehicle filters and verification.
8. P2: Add richer admin moderation and audit views.
9. P2: Improve PWA/offline behavior and mobile performance.

## Verification
Source review does not replace a real browser run. Required commands:
python -m compileall -q .
python security_audit.py
python -m pytest -q

CI should confirm the same on Python 3.12.
