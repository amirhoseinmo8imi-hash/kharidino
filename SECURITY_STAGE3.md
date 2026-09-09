# Security Stage 3

- Expanded runtime source audit is active.
- Local redirect validation has regression coverage for external URLs, protocol-relative URLs, backslashes, and control characters.
- Payment/order financial invariants remain covered by regression tests.
- CI must pass before this branch is considered release-ready.

Next hardening targets: payment callback concurrency, IDOR coverage, SSRF-safe seller URLs, upload/download path exposure, and migration-safe production schema changes.
