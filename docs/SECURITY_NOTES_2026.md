# Security notes

The checkout replay ledger is keyed by a normalized user/cart/customer fingerprint and stored in SQLite through SQLAlchemy. A duplicate request returns HTTP 409 before the checkout route can create a second order.

The checkout stock guard validates quantity and, when a product is present in the application's Product model, validates active status and at least one active in-stock positive-price offer. Product existence remains a business-layer responsibility so alternate checkout backends and isolated route tests are not blocked by this hardening layer.

Requests larger than the upload ceiling are rejected from `before_request` using `request.content_length`, while multipart file validation also enforces the same ceiling and checks real image/video content.
