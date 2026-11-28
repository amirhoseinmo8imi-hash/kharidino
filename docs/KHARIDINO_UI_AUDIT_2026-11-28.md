# Kharidino UI consistency audit — 2026-11-28

## Scope checked
The shared application shell and the main customer journeys were inspected on the current feature branch:
- Home and grouped category discovery
- Category listing and filters
- Product detail
- Compare
- Store directory and store detail
- Cart and checkout
- Profile
- Explore
- Cinema catalog, title detail and player

These customer-facing templates inherit `templates/base.html`, so the shared header, search, account/cart actions, footer and mobile bottom navigation are controlled from one shell.

## Findings

### 1. Global CSS cascade overlap
The base template was loading 24 global stylesheets. A static selector scan found repeated rules across multiple files, including:
- `body`, `.container`, `.product-body`, `.admin-layout`
- `.km-topbar`, `.km-header`, `.km-search`, `.km-search button`
- `.km-category-mega`, `.mobile-bottom-nav`
- `.kdg-product-image`, `.kdg-card-compare button`

The same shared selectors were being redefined by several successive "final"/"polish"/"unified" stylesheets. This creates a fragile cascade where appearance depends on stylesheet order and page-specific CSS.

### 2. Navigation duplication
The inner pages had a repeated global shortcut rail in addition to the top navigation and mobile navigation. This made the app feel like several separate menus competing for attention.

### 3. Category taxonomy
The database Category model has no parent-category field. The navigation now groups existing category records into presentation families without changing IDs or requiring a schema migration. Unmatched names remain visible in "سایر دسته‌بندی‌ها".

### 4. Category stock filter
The category template exposed available/unavailable options, but the route did not apply the selected stock state. The server-side filter is now implemented and respects an optional selected store.

## Changes implemented
- Added `category_navigation_groups` to the shared template context.
- Rebuilt the category mega-menu around grouped categories, related categories and quick shopping actions.
- Added a home-page category directory and category quick navigation on category pages.
- Removed the repeated global shortcut rail from inner pages.
- Limited the trust strip to the home page.
- Simplified the top navigation by moving specialist hubs under "همه خدمات" rather than repeating every hub in the primary row.
- Added one last-loaded responsive navigation/catalog stylesheet to normalize the shared shell and dark-mode category surfaces.
- Fixed malformed literal newline characters in the category stock-filter markup.
- Added regression tests for grouped navigation, the home category directory and server-side stock filtering.

## Compatibility decision
The legacy CSS files have **not** been deleted in this pass. Several pages (especially home, cart and checkout) still depend on rules distributed across those files. Removing them without migrating each page's component styles would risk breaking working flows. The new shared stylesheet currently stabilizes the common shell and catalog surfaces; the remaining work is a page-by-page migration to component-scoped styles followed by removal of obsolete global layers.

## Validation
- Python CI passed on the latest code branch head before the final CSS-only dark-mode adjustment.
- Security CI passed on that same code branch head before the final CSS-only dark-mode adjustment.
- Quality/template check passed on the branch head including the navigation/category templates.
- Android Debug build is running for the latest code including the final CSS adjustment.
- Real browser/device visual regression testing remains necessary; CI cannot replace testing at desktop, tablet and phone widths.
