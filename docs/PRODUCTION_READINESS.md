# Kharidino production-readiness checkpoint

This branch hardens the marketplace payment/fulfillment boundary.

- Return status cannot become `refunded` without a successful refund executor.
- Refunds are idempotent per payment transaction and fail closed for unsupported gateways.
- Seller shipment transitions are constrained by a state machine.
- Seller ledger availability is unlocked only after delivery.
- Checkout wallet use supports automatic full-balance use when requested without an explicit amount, while zero-value checkout is conservatively blocked from the external payment gateway until a dedicated free-order finalizer exists.
- Static regression coverage protects these invariants.
